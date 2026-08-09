"""
MongoDB persistence for:
  - admin user IDs (owner can add/remove)
  - global watermark override (set via /watermark)

Single settings document keyed by _id="config" holds admins[] and watermark.
"""

from motor.motor_asyncio import AsyncIOMotorClient

import config

_client = AsyncIOMotorClient(config.MONGO_URI)
_db = _client[config.DB_NAME]
_settings = _db["settings"]

DEFAULT_WATERMARK = "@Ongoing_english_dub"
_DOC_ID = "config"


async def _get_doc() -> dict:
    doc = await _settings.find_one({"_id": _DOC_ID})
    if not doc:
        doc = {"_id": _DOC_ID, "admins": [], "watermark": None}
        await _settings.insert_one(doc)
    return doc


async def get_admins() -> list[int]:
    doc = await _get_doc()
    return doc.get("admins", [])


async def add_admin(user_id: int) -> bool:
    doc = await _get_doc()
    if user_id in doc.get("admins", []):
        return False
    await _settings.update_one({"_id": _DOC_ID}, {"$addToSet": {"admins": user_id}})
    return True


async def remove_admin(user_id: int) -> bool:
    doc = await _get_doc()
    if user_id not in doc.get("admins", []):
        return False
    await _settings.update_one({"_id": _DOC_ID}, {"$pull": {"admins": user_id}})
    return True


async def is_admin_or_owner(user_id: int) -> bool:
    if user_id == config.OWNER_ID:
        return True
    admins = await get_admins()
    return user_id in admins


async def get_watermark() -> str:
    doc = await _get_doc()
    return doc.get("watermark") or DEFAULT_WATERMARK


async def set_watermark(text: str):
    await _settings.update_one({"_id": _DOC_ID}, {"$set": {"watermark": text}}, upsert=True)
