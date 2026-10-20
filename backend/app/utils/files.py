"""Upload validation: extension, size and content (magic bytes)."""
import io
import re
import unicodedata
import zipfile

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def sanitize_display_name(name: str | None) -> str:
    """Make a user-supplied filename safe to store and display.

    Only used for display — files on disk/S3 use server-generated names.
    """
    name = unicodedata.normalize("NFKC", name or "document")
    name = name.replace("\\", "/").split("/")[-1]  # drop any directory parts
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name).strip(" .")
    return (name or "document")[:200]


def get_extension(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def content_matches_type(data: bytes, ext: str) -> bool:
    """Check the bytes really are what the extension claims."""
    if ext == "pdf":
        return data[:1024].lstrip().startswith(b"%PDF-")
    if ext == "docx":
        if not data.startswith(b"PK\x03\x04"):
            return False
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                return "word/document.xml" in zf.namelist()
        except zipfile.BadZipFile:
            return False
    if ext == "txt":
        if b"\x00" in data[:8192]:  # binary file renamed to .txt
            return False
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            try:
                data.decode("cp1252")
                return True
            except UnicodeDecodeError:
                return False
    return False
