import os
import requests
from datetime import date
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "recipe-images")

SB_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
}

def _assert_env():
    assert SUPABASE_URL and SUPABASE_SERVICE_KEY, "SUPABASE_URL/SUPABASE_SERVICE_KEY missing"

def get_next_recipe():
    _assert_env()
    url = f"{SUPABASE_URL}/rest/v1/recipes"
    params = {
        "select": "id,title,body,image_path,image_url,last_posted_at,created_at",
        "status": "eq.ready",
        "order": "last_posted_at.asc.nullsfirst,created_at.asc",
        "limit": "1",
    }
    r = requests.get(url, headers=SB_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data[0] if data else None

def mark_posted(recipe_id: str):
    _assert_env()
    url = f"{SUPABASE_URL}/rest/v1/recipes?id=eq.{recipe_id}"
    payload = {"last_posted_at": str(date.today())}
    r = requests.patch(
        url,
        headers={**SB_HEADERS, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()

def public_image_url(image_path: str) -> str:
    safe_path = "/".join(quote(part) for part in image_path.split("/"))
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{safe_path}"

from typing import Optional

def get_image_url(recipe: dict) -> Optional[str]:
    if recipe.get("image_url"):
        return recipe["image_url"].strip() or None
    if recipe.get("image_path"):
        return public_image_url(recipe["image_path"].strip())
    return None
    
def count_rows(where: Optional[str] = None) -> int:
    _assert_env()
    url = f"{SUPABASE_URL}/rest/v1/recipes"
    params = {"select": "id"}
    if where:
        for part in where.split("&"):
            k, v = part.split("=", 1)
            params[k] = v

    headers = {**SB_HEADERS, "Prefer": "count=exact"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()

    content_range = r.headers.get("Content-Range", "")
    # формат: 0-9/30
    total = content_range.split("/")[-1]
    return int(total) if total.isdigit() else 0

def stats():
    total = count_rows()
    ready = count_rows("status=eq.ready")
    posted = count_rows("last_posted_at=not.is.null")
    remaining = max(ready - 0, 0)
    return {"total": total, "ready": ready, "posted": posted, "remaining_ready": remaining}