import os
import requests
from datetime import date
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

SUPABASE_URL = os.getenv("SUPABASE_URL").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "recipe-images")

assert TG_BOT_TOKEN and TG_CHAT_ID, "TG_BOT_TOKEN/TG_CHAT_ID missing"
assert SUPABASE_URL and SUPABASE_SERVICE_KEY, "SUPABASE_URL/SUPABASE_SERVICE_KEY missing"

SB_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
}

def get_next_recipe():
    """
    Берём 'следующий' рецепт:
    1) status=ready
    2) те, что ещё не постились — первыми (last_posted_at is null)
    3) потом по дате, потом по created_at
    """
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
    if not data:
        return None
    return data[0]

def mark_posted(recipe_id: str):
    url = f"{SUPABASE_URL}/rest/v1/recipes?id=eq.{recipe_id}"
    payload = {"last_posted_at": str(date.today())}
    r = requests.patch(url, headers={**SB_HEADERS, "Content-Type": "application/json"},
                       json=payload, timeout=30)
    r.raise_for_status()

def public_image_url(image_path: str) -> str:
    """
    Если bucket Public, можно брать напрямую:
    /storage/v1/object/public/<bucket>/<path>
    """
    # image_path может содержать / и пробелы — кодируем аккуратно
    safe_path = "/".join(quote(part) for part in image_path.split("/"))
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{safe_path}"

def tg_send_photo(photo_url: str, caption: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TG_CHAT_ID,
        "photo": photo_url,
        "caption": caption[:1024],  # лимит caption у Telegram
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=60)
    r.raise_for_status()
    resp = r.json()
    if not resp.get("ok"):
        raise RuntimeError(resp)
    return resp

def main():
    recipe = get_next_recipe()
    if not recipe:
        print("No ready recipes found.")
        return

    title = recipe["title"].strip()
    body = recipe["body"].strip()

    caption = f"<b>{title}</b>\n\n{body}"

    photo_url = None
    if recipe.get("image_url"):
        photo_url = recipe["image_url"].strip()
    elif recipe.get("image_path"):
        photo_url = public_image_url(recipe["image_path"].strip())

    if not photo_url:
        raise RuntimeError("Recipe has no image_url or image_path")

    tg_send_photo(photo_url, caption)
    mark_posted(recipe["id"])
    print(f"Posted: {recipe['id']}")

if __name__ == "__main__":
    main()
