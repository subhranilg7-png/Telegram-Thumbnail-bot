"""AniList GraphQL client."""
import re
import aiohttp
ANILIST_URL='https://graphql.anilist.co'

SEARCH_QUERY='''
query ($search: String) {
  Page(page: 1, perPage: 5) {
    media(search: $search, type: ANIME) {
      id
      title { romaji english native }
      description(asHtml: false)
      genres
      averageScore
      episodes
      status
      season
      seasonYear
      studios(isMain: true) { nodes { name } }
      coverImage { extraLarge large color }
      bannerImage
    }
  }
}
'''
BY_ID_QUERY='''
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id title { romaji english native } description(asHtml: false) genres averageScore episodes status season seasonYear
    studios(isMain: true) { nodes { name } } coverImage { extraLarge large color } bannerImage
  }
}
'''

class AniListError(Exception): pass

def clean_synopsis(raw):
    if not raw: return ''
    text=re.sub(r'<br\s*/?>',' ',raw); text=re.sub(r'<[^>]+>','',text)
    text=re.sub(r'\(Source:.*?\)','',text,flags=re.I|re.S)
    return re.sub(r'\s+',' ',text).strip()

async def _query(query, variables):
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_URL,json={'query':query,'variables':variables},timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status!=200: raise AniListError(f'AniList returned status {resp.status}')
            data=await resp.json()
            if 'errors' in data: raise AniListError(data['errors'][0].get('message','Unknown AniList error'))
            return data

async def search_anime(query):
    data=await _query(SEARCH_QUERY,{'search':query})
    return data['data']['Page']['media']

async def get_anime_by_id(anilist_id):
    data=await _query(BY_ID_QUERY,{'id':anilist_id})
    media=data.get('data',{}).get('Media')
    results=[media] if media else []
    return results[0] if results else None

def best_title(media):
    t=media.get('title',{}); return t.get('english') or t.get('romaji') or t.get('native') or 'Unknown Title'

def subtitle(media):
    t=media.get('title',{}); return t.get('romaji') or t.get('native') or ''

def season_label(media):
    season=media.get('season'); year=media.get('seasonYear')
    if season and year: return f'{season} {year}'
    return str(year) if year else (season or '')

async def download_image(url,dest_path):
    if not url: return None
    async with aiohttp.ClientSession() as session:
        async with session.get(url,timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status!=200: return None
            with open(dest_path,'wb') as f: f.write(await resp.read())
    return dest_path
