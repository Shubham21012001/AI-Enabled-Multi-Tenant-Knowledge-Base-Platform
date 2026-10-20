# Deploying KnowBot to AWS (EC2 + S3 + HTTPS)

Target: one EC2 instance running the production Docker Compose stack:

```
Internet ─▶ Caddy :80/:443 (Let's Encrypt) ─▶ nginx (React + /api proxy) ─▶ FastAPI ─▶ Postgres+pgvector, Redis
                                                                               └──────▶ S3 (documents), OpenAI
```

The stack in `docker-compose.prod.yml` was verified locally with `DOMAIN=localhost`: all containers healthy, HTTP→HTTPS redirect, security headers, upload → processing → ready, and SSE streaming through both proxies.

## 1. AWS resources

1. **S3 bucket** (e.g. `knowbot-documents-prod`, region `ap-south-1`)
   - Block *all* public access (default) and enable default encryption (SSE-S3).
2. **IAM role for EC2** (`knowbot-ec2-role`) with only this policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
       "Resource": "arn:aws:s3:::knowbot-documents-prod/*"
     }]
   }
   ```
   With an instance role, boto3 gets temporary credentials automatically, so no AWS keys go in `.env`.
3. **EC2 instance:** Ubuntu 24.04, `t3.small` or larger (2 GB+ RAM), 20 GB gp3. Attach the IAM role.
4. **Security group:** inbound 80 and 443 from anywhere, and 22 **from your IP only**. Nothing else (Postgres and Redis are not exposed).
5. **Elastic IP** attached to the instance, and a DNS **A record** `knowbot.yourdomain.com → Elastic IP`.

## 2. Server setup

```bash
ssh ubuntu@<elastic-ip>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && newgrp docker

git clone <your-repo-url> knowbot && cd knowbot
cp deploy/.env.production.example .env.production
nano .env.production
```

Fill in `.env.production`:

- `DOMAIN`, `FRONTEND_URL`, `CORS_ORIGINS`: your domain with `https://`
- `POSTGRES_PASSWORD`, `REDIS_PASSWORD`: long random values (`openssl rand -hex 24`)
- `JWT_SECRET_KEY`: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `OPENAI_API_KEY`
- `STORAGE_BACKEND=s3`, `S3_BUCKET`, `AWS_REGION`
- SMTP settings (e.g. Amazon SES SMTP credentials) or `EMAIL_PROVIDER=console`

```bash
chmod 600 .env.production
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml ps        # all healthy
curl https://knowbot.yourdomain.com/api/health      # {"status":"ok",...}
```

Caddy obtains the TLS certificate on first request (DNS must already point at the instance). The API container runs `alembic upgrade head` on every start.

Optional: create a platform super admin:

```bash
docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-superadmin --email you@yourdomain.com
```

## 3. Updating

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 4. Backups

```bash
# Nightly Postgres dump (add to crontab), copied to S3
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U knowbot knowbot | gzip > backup-$(date +%F).sql.gz
aws s3 cp backup-$(date +%F).sql.gz s3://knowbot-backups/
```

Enable S3 versioning on the documents bucket to protect against accidental deletes.

## 5. Monitoring & logs

- **Health:** `GET /api/health` returns 200 only if Postgres and Redis respond. Point an uptime monitor at it (e.g. UptimeRobot or Route 53 health checks). Docker healthchecks restart unhealthy containers.
- **Logs:** `docker compose -f docker-compose.prod.yml logs -f backend`. Each request is logged with method, path, status, duration and a request ID (also returned as the `X-Request-ID` header). Log files rotate (20 MB × 5).
- **Instance metrics:** CloudWatch default EC2 metrics (CPU, network, status checks). Add the CloudWatch agent for memory/disk.
- **Cost:** set an OpenAI usage limit in the OpenAI dashboard. KnowBot's plan limits and rate limits cap per-org usage.

## 6. Production checklist

- [ ] DNS points to the Elastic IP; HTTPS works; HTTP redirects
- [ ] `.env.production` has strong unique secrets and `chmod 600`
- [ ] S3 bucket private and encrypted; EC2 uses an IAM role (no access keys)
- [ ] Security group allows only 80/443 (+22 from your IP)
- [ ] `ENVIRONMENT=production` (set by the compose file), so `/docs` is disabled
- [ ] Backups scheduled and a restore tested
- [ ] Uptime monitor on `/api/health`
