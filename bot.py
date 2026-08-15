"""
Thumbnail Bot
-------------
Restricted to the owner and approved admins.

Commands:
  /thumb <anime name>   Start the thumbnail flow.
  /cancel                Abort the current flow.
  /watermark <text>      Set the bottom-left tag (admin/owner). Use
                          "/watermark reset" to go back to the default.
  /addadmin <user_id>    Owner only.
  /removeadmin <user_id> Owner only.

Flow: search AniList -> pick match -> enter season text (or "skip") ->
choose Auto-fetch vs provide 3 images -> generated thumbnail is sent back.
"""

import os
import logging
import uuid
import threading
import uvicorn

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from PIL import Image

import config
import db
import anilist
from renderer import render
from project_store import new_project, load_project
from webapp_server import app as web_app

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("thumbnail-bot")

app = Client(
    "thumbnail-bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# --- In-memory per-user session state ---
sessions: dict[int, dict] = {}
WEBAPP_URL = os.environ.get("WEBAPP_URL", "").rstrip("/")


def reset(user_id: int):
    sessions.pop(user_id, None)


async def require_admin(message_or_cq) -> bool:
    user_id = message_or_cq.from_user.id
    if await db.is_admin_or_owner(user_id):
        return True
    if isinstance(message_or_cq, Message):
        await message_or_cq.reply("This bot is restricted to admins and the owner.")
    else:
        await message_or_cq.answer("Admins only.", show_alert=True)
    return False


# ---------------------------------------------------------------- /start ---
@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message):
    is_allowed = await db.is_admin_or_owner(message.from_user.id)
    if is_allowed:
        await message.reply(
            "**Thumbnail Bot**\n\n"
            "`/thumb <anime name>` — generate a thumbnail\n"
            "`/watermark [text|reset]` — view/set the tag\n"
            "`/admins` — list admins\n"
            "`/cancel` — abort the current flow"
        )
    else:
        await message.reply(
            f"This bot is restricted to admins and the owner.\n\n"
            f"Your Telegram user ID is `{message.from_user.id}` "
            f"— send this to the owner if you need access."
        )


# ---------------------------------------------------------------- /thumb ---
@app.on_message(filters.command("thumb") & filters.private)
async def cmd_thumb(client: Client, message: Message):
    if not await require_admin(message):
        return

    query = " ".join(message.command[1:]).strip()
    user_id = message.from_user.id

    if not query:
        sessions[user_id] = {"step": "await_name"}
        return await message.reply("Send me the anime name (or `/cancel` to abort).")

    await do_search(message, query)


@app.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(client: Client, message: Message):
    reset(message.from_user.id)
    await message.reply("Cancelled.")


# ---------------------------------------------------------- /watermark ---
@app.on_message(filters.command("watermark") & filters.private)
async def cmd_watermark(client: Client, message: Message):
    if not await require_admin(message):
        return

    arg = " ".join(message.command[1:]).strip()
    if not arg:
        current = await db.get_watermark()
        return await message.reply(
            f"Current watermark: `{current}`\n\n"
            "Usage: `/watermark <text>` or `/watermark reset`"
        )

    if arg.lower() == "reset":
        await db.set_watermark(db.DEFAULT_WATERMARK)
        return await message.reply(f"Watermark reset to `{db.DEFAULT_WATERMARK}`.")

    await db.set_watermark(arg)
    await message.reply(f"Watermark set to `{arg}`.")


# ------------------------------------------------------- admin management ---
@app.on_message(filters.command("addadmin") & filters.private)
async def cmd_add_admin(client: Client, message: Message):
    if message.from_user.id != config.OWNER_ID:
        return await message.reply("Only the owner can add admins.")

    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply("Usage: `/addadmin <user_id>`")

    target = int(message.command[1])
    added = await db.add_admin(target)
    await message.reply(f"Added `{target}` as admin." if added else f"`{target}` is already an admin.")


@app.on_message(filters.command("removeadmin") & filters.private)
async def cmd_remove_admin(client: Client, message: Message):
    if message.from_user.id != config.OWNER_ID:
        return await message.reply("Only the owner can remove admins.")

    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply("Usage: `/removeadmin <user_id>`")

    target = int(message.command[1])
    removed = await db.remove_admin(target)
    await message.reply(f"Removed `{target}` from admins." if removed else f"`{target}` wasn't an admin.")


@app.on_message(filters.command("admins") & filters.private)
async def cmd_list_admins(client: Client, message: Message):
    if not await require_admin(message):
        return
    admins = await db.get_admins()
    lines = [f"Owner: `{config.OWNER_ID}`"]
    lines += [f"Admin: `{a}`" for a in admins] or ["(no additional admins)"]
    await message.reply("\n".join(lines))


# ------------------------------------------------------------- searching ---
async def do_search(message: Message, query: str):
    user_id = message.from_user.id
    status = await message.reply(f"Searching AniList for **{query}**...")

    try:
        results = await anilist.search_anime(query)
    except anilist.AniListError as e:
        return await status.edit(f"AniList error: {e}")

    if not results:
        return await status.edit("No matches found. Try `/thumb <another name>`.")

    sessions[user_id] = {"step": "await_match", "candidates": {m["id"]: m for m in results}}

    buttons = []
    for m in results:
        label = f"{anilist.best_title(m)} ({m.get('seasonYear') or '?'})"
        buttons.append([InlineKeyboardButton(label, callback_data=f"pick:{m['id']}")])
    buttons.append([InlineKeyboardButton("Cancel", callback_data="cancel")])

    await status.edit("Pick the correct match:", reply_markup=InlineKeyboardMarkup(buttons))


@app.on_message(filters.text & filters.private & ~filters.command(
    ["thumb", "cancel", "watermark", "addadmin", "removeadmin", "admins"]
))
async def on_text(client: Client, message: Message):
    user_id = message.from_user.id
    session = sessions.get(user_id)
    if not session:
        return

    step = session.get("step")

    if step == "await_name":
        if not await require_admin(message):
            return
        return await do_search(message, message.text.strip())

    if step == "await_season":
        text = message.text.strip()
        session["season_text"] = None if text.lower() == "skip" else text
        session["step"] = "await_source"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Auto-fetch from AniList", callback_data="src:auto")],
            [InlineKeyboardButton("I'll provide 3 images", callback_data="src:manual")],
            [InlineKeyboardButton("Cancel", callback_data="cancel")],
        ])
        return await message.reply("How should I source the artwork?", reply_markup=buttons)


# ------------------------------------------------------- match selection ---
@app.on_callback_query(filters.regex(r"^pick:(\d+)$"))
async def on_pick(client: Client, cq: CallbackQuery):
    if not await require_admin(cq):
        return

    user_id = cq.from_user.id
    session = sessions.get(user_id)
    if not session or session.get("step") != "await_match":
        return await cq.answer("This selection expired, run /thumb again.", show_alert=True)

    anilist_id = int(cq.matches[0].group(1))
    media = session["candidates"].get(anilist_id)
    if not media:
        return await cq.answer("Not found, run /thumb again.", show_alert=True)

    session["step"] = "await_season"
    session["title"] = anilist.best_title(media)
    session["synopsis"] = anilist.clean_synopsis(media.get("description", ""))
    session["cover_url"] = media["coverImage"].get("extraLarge") or media["coverImage"].get("large")
    session["banner_url"] = media.get("bannerImage")

    await cq.message.edit(
        f"**{session['title']}** selected.\n\n"
        "Send the season text (e.g. `Season 2`), or type `skip` if there's none."
    )
    await cq.answer()


@app.on_callback_query(filters.regex(r"^cancel$"))
async def on_cancel_cb(client: Client, cq: CallbackQuery):
    reset(cq.from_user.id)
    await cq.message.edit("Cancelled.")
    await cq.answer()


# -------------------------------------------------------- source choice ---
@app.on_callback_query(filters.regex(r"^src:(auto|manual)$"))
async def on_source_choice(client: Client, cq: CallbackQuery):
    if not await require_admin(cq):
        return

    user_id = cq.from_user.id
    session = sessions.get(user_id)
    if not session or session.get("step") != "await_source":
        return await cq.answer("Expired, run /thumb again.", show_alert=True)

    choice = cq.matches[0].group(1)

    if choice == "manual":
        session["step"] = "await_bg"
        session["manual"] = {}
        await cq.message.edit("Send the **background** image (left panel).")
        return await cq.answer()

    await cq.message.edit("Fetching artwork from AniList...")
    uid_tag = uuid.uuid4().hex[:8]
    cover_path = os.path.join(TEMP_DIR, f"{uid_tag}_cover.jpg")
    banner_path = os.path.join(TEMP_DIR, f"{uid_tag}_banner.jpg")

    cover_ok = await anilist.download_image(session["cover_url"], cover_path)
    banner_ok = await anilist.download_image(session.get("banner_url"), banner_path)

    if not cover_ok:
        return await cq.message.edit("Couldn't download cover art from AniList. Try `/thumb` again.")

    cover_img = Image.open(cover_path)
    banner_img = Image.open(banner_path) if banner_ok else cover_img

    session["auto_bg"] = cover_img
    session["auto_poster"] = cover_img
    session["auto_circle"] = banner_img

    await render_and_send(cq.message, user_id, source="auto")
    await cq.answer()


# ------------------------------------------------------- manual uploads ---
@app.on_message(filters.photo & filters.private)
async def on_photo(client: Client, message: Message):
    user_id = message.from_user.id
    session = sessions.get(user_id)
    if not session or session.get("step") not in ("await_bg", "await_poster", "await_circle"):
        return

    if not await require_admin(message):
        return

    path = await message.download(file_name=os.path.join(TEMP_DIR, f"{uuid.uuid4().hex[:8]}.jpg"))
    img = Image.open(path)

    step = session["step"]
    if step == "await_bg":
        session["manual"]["bg"] = img
        session["step"] = "await_poster"
        return await message.reply("Got it. Now send the **poster** image (right panel).")

    if step == "await_poster":
        session["manual"]["poster"] = img
        session["step"] = "await_circle"
        return await message.reply("Now send the **circle inset** image.")

    if step == "await_circle":
        session["manual"]["circle"] = img
        status = await message.reply("Generating thumbnail...")
        await render_and_send(status, user_id, source="manual")


# --------------------------------------------------------------- render ---
async def render_and_send(status_message: Message, user_id: int, source: str):
    session = sessions.get(user_id)
    if not session:
        return await status_message.edit("Session expired, run /thumb again.")

    if source == "auto":
        bg, poster, circle = session["auto_bg"], session["auto_poster"], session["auto_circle"]
    else:
        m = session["manual"]
        bg, poster, circle = m["bg"], m["poster"], m["circle"]

    watermark = await db.get_watermark()
    uid = uuid.uuid4().hex[:10]
    pdir = os.path.join(TEMP_DIR, "projects", uid)
    os.makedirs(pdir, exist_ok=True)
    bg_path = os.path.join(pdir, "background.jpg")
    poster_path = os.path.join(pdir, "poster.jpg")
    circle_path = os.path.join(pdir, "circle.jpg")
    bg.convert("RGB").save(bg_path, "JPEG", quality=94)
    poster.convert("RGB").save(poster_path, "JPEG", quality=94)
    circle.convert("RGB").save(circle_path, "JPEG", quality=94)

    default_layout = {
        "background_zoom": 1.0,
        "background_focal": [0.5, 0.5],
        "poster_x": 850, "poster_y": 0, "poster_w": 430, "poster_h": 720,
        "poster_zoom": 1.0, "poster_focal": [0.5, 0.5],
        "overlay_opacity": 115, "overlay_width": 720,
        "panel": {"enabled": True, "x": 0, "y": 48, "width": 610, "height": 500, "radius": 34, "fill": [35,35,42,105]},
        "title": {"x": 58, "y": 58, "max_width": 650, "size": 48},
        "season_size": 23,
        "synopsis": {"x": 60, "y": 250, "width": 600, "heading_size": 21, "body_size": 19, "max_lines": 9, "align": "center"},
        "circle": {"x": 850, "y": 370, "size": 420, "border": 8, "zoom": 1.0, "focal": [0.5,0.5], "sparkle_x": 720, "sparkle_y": 555},
        "bottom_title": {"y": 630, "right": 28, "max_width": 360, "size": 30}
    }
    project = {
        "title": session["title"],
        "synopsis": session["synopsis"],
        "season_text": session.get("season_text"),
        "watermark": watermark,
        "files": {"background": bg_path, "poster": poster_path, "circle": circle_path},
        "layout": default_layout,
        "default_layout": default_layout,
        "owner_id": user_id,
    }
    pid = new_project(project)
    project["id"] = pid
    out_path = os.path.join(TEMP_DIR, f"{pid}_thumb.png")
    render(project).save(out_path, "PNG")

    try:
        await status_message.delete()
    except Exception:
        pass

    buttons=[]
    if WEBAPP_URL:
        buttons.append([InlineKeyboardButton("✏️ Edit thumbnail", web_app=WebAppInfo(url=f"{WEBAPP_URL}/?project={pid}"))])
    buttons.append([InlineKeyboardButton("📥 Export / download", callback_data=f"export:{pid}")])
    await app.send_photo(user_id, out_path, caption=f"**{session['title']}**\n\nEdit it with the button below.", reply_markup=InlineKeyboardMarkup(buttons))
    reset(user_id)

    try: os.remove(out_path)
    except OSError: pass


@app.on_callback_query(filters.regex(r"^export:([a-z0-9]+)$"))
async def on_export(client: Client, cq: CallbackQuery):
    if not await require_admin(cq): return
    pid=cq.matches[0].group(1)
    project=load_project(pid)
    if not project: return await cq.answer("Project expired.", show_alert=True)
    await cq.answer("Use the Edit button to export PNG/PDF/PPTX.")


def run_web_server():
    uvicorn.run(web_app, host=os.environ.get("WEBAPP_HOST", "0.0.0.0"), port=int(os.environ.get("WEBAPP_PORT", "8080")), log_level="info")


if __name__ == "__main__":
    if WEBAPP_URL:
        threading.Thread(target=run_web_server, daemon=True).start()
        log.info("Web editor enabled at %s", WEBAPP_URL)
    else:
        log.warning("WEBAPP_URL is not set; the Edit Thumbnail button will not be shown.")
    log.info("Starting thumbnail bot...")
    app.run()
