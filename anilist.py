"""
AniList GraphQL client.
Docs: https://docs.anilist.co/
No API key needed for public queries.
"""

import re
import aiohttp

ANILIST_URL = "https://graphql.anilist.co"

SEARCH_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 5) {
    media(search: $search, type: ANIME) {
      id
      title {
        romaji
        english
        native
      }
      description(asHtml: false)
      genres
      averageScore
      episodes
      status
      studios(isMain: true) {
        nodes {
          name
        }
      }
      coverImage {
        extraLarge
        large
        color
      }
      bannerImage
      season
      seasonYear
    }
  }
}
"""

BY_ID_QUERY = """
query ($id: Int) {
  Page(page: 1, perPage: 1) {
    media(id: $id, type: ANIME) {
      id
      title { romaji english native }
      description(asHtml: false)
      genres
      averageScore
      episodes
      status
      studios(isMain: true) { nodes { name } }
      coverImage { extraLarge large color }
      bannerImage
      season
      seasonYear
    }
  }
}
"""


def clean_synopsis(raw: str) -> str:
    """Strip AniList's HTML-ish markup (e.g. <br>, <i>) and bracketed source tags."""
    if not raw:
        return ""
    text = re.sub(r"<br\s*/?>", " ", raw)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\(Source:.*?\)", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class AniListError(Exception):
    pass


async def search_anime(query: str) -> list[dict]:
    """Return up to 5 candidate matches for a text search."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            ANILIST_URL,
            json={"query": SEARCH_QUERY, "variables": {"search": query}},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise AniListError(f"AniList returned status {resp.status}")
            data = await resp.json()
            if "errors" in data:
                raise AniListError(data["errors"][0].get("message", "Unknown AniList error"))
            return data["data"]["Page"]["media"]


async def get_anime_by_id(anilist_id: int) -> dict | None:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            ANILIST_URL,
            json={"query": BY_ID_QUERY, "variables": {"id": anilist_id}},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
            results = data.get("data", {}).get("Page", {}).get("media", [])
            return results[0] if results else None


def best_title(media: dict) -> str:
    t = media["title"]
    return t.get("english") or t.get("romaji") or t.get("native") or "Unknown Title"


async def download_image(url: str, dest_path: str) -> str | None:
    """Download an image (e.g. coverImage/bannerImage) to dest_path. Returns path or None."""
    if not url:
        return None
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return None
            with open(dest_path, "wb") as f:
                f.write(await resp.read())
    return dest_path
