def test_invite_and_accept_member(client, org_a):
    member_headers = org_a.invite_member("emp@acme.com")
    me = client.get("/auth/me", headers=member_headers).json()
    assert me["org_id"] == org_a.org_id and me["role"] == "member"
    members = client.get("/organizations/me/members", headers=org_a.headers).json()
    assert {m["email"] for m in members} == {"admin@acme.com", "emp@acme.com"}
    assert client.get("/organizations/me", headers=org_a.headers).json()["members_count"] == 2


def test_invitation_token_single_use(client, org_a):
    r = client.post("/organizations/me/invitations", headers=org_a.headers, json={"email": "x@acme.com"})
    token = r.json()["invite_url"].split("token=")[1]
    body = {"token": token, "password": "Passw0rd123", "full_name": "X"}
    assert client.post("/auth/accept-invite", json=body).status_code == 201
    assert client.post("/auth/accept-invite", json=body).status_code == 422


def test_revoked_invitation_cannot_be_used(client, org_a):
    r = client.post("/organizations/me/invitations", headers=org_a.headers, json={"email": "y@acme.com"})
    inv_id, token = r.json()["id"], r.json()["invite_url"].split("token=")[1]
    assert client.delete(f"/organizations/me/invitations/{inv_id}", headers=org_a.headers).status_code == 204
    r = client.post("/auth/accept-invite", json={"token": token, "password": "Passw0rd123", "full_name": "Y"})
    assert r.status_code == 422


def test_member_cannot_perform_admin_actions(client, org_a):
    m = org_a.invite_member("emp@acme.com")
    assert client.post("/organizations/me/invitations", headers=m, json={"email": "z@acme.com"}).status_code == 403
    assert client.patch("/organizations/me", headers=m, json={"name": "Hacked"}).status_code == 403
    assert client.put("/organizations/me/plan", headers=m, json={"plan": "enterprise"}).status_code == 403
    assert client.get("/dashboard", headers=m).status_code == 403
    assert client.get("/api-keys", headers=m).status_code == 403
    assert client.get("/admin/organizations", headers=m).status_code == 403


def test_admin_cannot_access_platform_admin(client, org_a):
    assert client.get("/admin/organizations", headers=org_a.headers).status_code == 403


def test_free_plan_member_limit(client, org_a):
    # Free = 3 members. Admin + 2 invites (pending invites reserve seats).
    org_a.invite_member("m1@acme.com")
    assert client.post("/organizations/me/invitations", headers=org_a.headers, json={"email": "m2@acme.com"}).status_code == 201
    r = client.post("/organizations/me/invitations", headers=org_a.headers, json={"email": "m3@acme.com"})
    assert r.status_code == 402 and r.json()["code"] == "plan_limit_reached"
    # Upgrading lifts the limit
    assert client.put("/organizations/me/plan", headers=org_a.headers, json={"plan": "pro"}).status_code == 200
    assert client.post("/organizations/me/invitations", headers=org_a.headers, json={"email": "m3@acme.com"}).status_code == 201


def test_role_change_and_last_admin_protection(client, org_a):
    member_headers = org_a.invite_member("emp@acme.com")
    emp_id = client.get("/auth/me", headers=member_headers).json()["id"]
    r = client.patch(f"/organizations/me/members/{emp_id}", headers=org_a.headers, json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    # Can't demote the last admin
    r = client.patch(f"/organizations/me/members/{emp_id}", headers=org_a.headers, json={"role": "member"})
    assert r.status_code == 200
    r = client.patch(f"/organizations/me/members/{org_a.me['id']}", headers=org_a.headers, json={"role": "member"})
    assert r.status_code == 422
    # Can't promote to super admin
    r = client.patch(f"/organizations/me/members/{emp_id}", headers=org_a.headers, json={"role": "super_admin"})
    assert r.status_code == 422


def test_remove_member(client, org_a):
    member_headers = org_a.invite_member("emp@acme.com")
    emp_id = client.get("/auth/me", headers=member_headers).json()["id"]
    assert client.delete(f"/organizations/me/members/{emp_id}", headers=org_a.headers).status_code == 204
    assert client.get("/auth/me", headers=member_headers).status_code == 401
    assert client.delete(f"/organizations/me/members/{org_a.me['id']}", headers=org_a.headers).status_code == 422


def test_cross_tenant_member_management_blocked(client, org_a, org_b):
    b_member = org_b.invite_member("emp@globex.com")
    b_member_id = client.get("/auth/me", headers=b_member).json()["id"]
    # Org A admin can't see, change or remove Org B's member.
    assert client.patch(f"/organizations/me/members/{b_member_id}", headers=org_a.headers, json={"role": "admin"}).status_code == 404
    assert client.delete(f"/organizations/me/members/{b_member_id}", headers=org_a.headers).status_code == 404
    emails = {m["email"] for m in client.get("/organizations/me/members", headers=org_a.headers).json()}
    assert "emp@globex.com" not in emails


def test_update_organization(client, org_a):
    r = client.patch("/organizations/me", headers=org_a.headers, json={"name": "Acme Corporation", "logo_url": "https://acme.com/logo.png"})
    assert r.status_code == 200 and r.json()["name"] == "Acme Corporation"
    assert client.patch("/organizations/me", headers=org_a.headers, json={"logo_url": "javascript:alert(1)"}).status_code == 422


def test_super_admin_platform_endpoints(client, org_a, org_b):
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models import User

    db = SessionLocal()
    db.add(User(email="root@knowbot.io", hashed_password=hash_password("Sup3rSecret!"), full_name="Root", role="super_admin"))
    db.commit()
    db.close()
    tok = client.post("/auth/login", json={"email": "root@knowbot.io", "password": "Sup3rSecret!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    orgs = client.get("/admin/organizations", headers=h).json()
    assert {o["name"] for o in orgs} == {"Acme Corp", "Globex Inc"}
    assert client.put(f"/admin/organizations/{org_b.org_id}/plan", headers=h, json={"plan": "pro"}).json()["plan"] == "pro"
    # A super admin has no tenant, so tenant endpoints refuse them.
    assert client.get("/documents/", headers=h).status_code == 403
