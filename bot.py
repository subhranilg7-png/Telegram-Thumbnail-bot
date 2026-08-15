"""Telegram thumbnail bot for the Ongoing English Dub anime card design."""
import os, logging, uuid, threading
import uvicorn
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from PIL import Image
import config, db, anilist
from renderer import render, accent_from_image
from project_store import new_project
from webapp_server import app as web_app

logging.basicConfig(level=logging.INFO)
log=logging.getLogger('thumbnail-bot')
app=Client('thumbnail-bot',api_id=config.API_ID,api_hash=config.API_HASH,bot_token=config.BOT_TOKEN)
TEMP_DIR=os.path.join(os.path.dirname(__file__),'temp'); os.makedirs(TEMP_DIR,exist_ok=True)
sessions={}; WEBAPP_URL=os.environ.get('WEBAPP_URL','').rstrip('/')

def reset(uid): sessions.pop(uid,None)
async def require_admin(obj):
    if await db.is_admin_or_owner(obj.from_user.id): return True
    if isinstance(obj,Message): await obj.reply('This bot is restricted to admins and the owner.')
    else: await obj.answer('Admins only.',show_alert=True)
    return False

@app.on_message(filters.command('start') & filters.private)
async def start(_,m):
    if await db.is_admin_or_owner(m.from_user.id):
        await m.reply('**Thumbnail Bot**\n\n`/thumb <anime name>` — generate a thumbnail\n`/watermark [text|reset]` — set the branding\n`/admins` — list admins\n`/cancel` — abort')
    else: await m.reply(f'This bot is restricted to admins and the owner.\nYour Telegram user ID is `{m.from_user.id}`.')

@app.on_message(filters.command('thumb') & filters.private)
async def thumb(_,m):
    if not await require_admin(m): return
    q=' '.join(m.command[1:]).strip(); uid=m.from_user.id
    if not q:
        sessions[uid]={'step':'await_name'}; return await m.reply('Send me the anime name.')
    await search(m,q)

@app.on_message(filters.command('cancel') & filters.private)
async def cancel(_,m): reset(m.from_user.id); await m.reply('Cancelled.')

@app.on_message(filters.command('watermark') & filters.private)
async def watermark(_,m):
    if not await require_admin(m): return
    arg=' '.join(m.command[1:]).strip()
    if not arg: return await m.reply(f'Current watermark: `{await db.get_watermark()}`')
    if arg.lower()=='reset': await db.set_watermark(db.DEFAULT_WATERMARK); return await m.reply(f'Watermark reset to `{db.DEFAULT_WATERMARK}`.')
    await db.set_watermark(arg); await m.reply(f'Watermark set to `{arg}`.')

@app.on_message(filters.command('addadmin') & filters.private)
async def addadmin(_,m):
    if m.from_user.id!=config.OWNER_ID: return await m.reply('Only the owner can add admins.')
    if len(m.command)<2 or not m.command[1].isdigit(): return await m.reply('Usage: `/addadmin <user_id>`')
    uid=int(m.command[1]); ok=await db.add_admin(uid); await m.reply(f'Added `{uid}` as admin.' if ok else f'`{uid}` is already an admin.')

@app.on_message(filters.command('removeadmin') & filters.private)
async def removeadmin(_,m):
    if m.from_user.id!=config.OWNER_ID: return await m.reply('Only the owner can remove admins.')
    if len(m.command)<2 or not m.command[1].isdigit(): return await m.reply('Usage: `/removeadmin <user_id>`')
    uid=int(m.command[1]); ok=await db.remove_admin(uid); await m.reply(f'Removed `{uid}`.' if ok else f'`{uid}` was not an admin.')

@app.on_message(filters.command('admins') & filters.private)
async def admins(_,m):
    if not await require_admin(m): return
    a=await db.get_admins(); await m.reply('\n'.join([f'Owner: `{config.OWNER_ID}`']+[f'Admin: `{x}`' for x in a] or ['(no additional admins)']))

async def search(message,q):
    uid=message.from_user.id; status=await message.reply(f'Searching AniList for **{q}**...')
    try: results=await anilist.search_anime(q)
    except anilist.AniListError as e: return await status.edit(f'AniList error: {e}')
    if not results: return await status.edit('No matches found.')
    sessions[uid]={'step':'await_match','candidates':{m['id']:m for m in results}}
    buttons=[]
    for m in results:
        label=f"{anilist.best_title(m)} ({anilist.season_label(m) or '?'})"
        buttons.append([InlineKeyboardButton(label,callback_data=f"pick:{m['id']}")])
    buttons.append([InlineKeyboardButton('Cancel',callback_data='cancel')])
    await status.edit('Pick the correct match:',reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.text & filters.private & ~filters.command(['thumb','cancel','watermark','addadmin','removeadmin','admins']))
async def text(_,m):
    s=sessions.get(m.from_user.id)
    if not s: return
    if s.get('step')=='await_name':
        if await require_admin(m): await search(m,m.text.strip())

@app.on_callback_query(filters.regex(r'^pick:(\d+)$'))
async def pick(_,cq):
    if not await require_admin(cq): return
    uid=cq.from_user.id; s=sessions.get(uid)
    if not s or s.get('step')!='await_match': return await cq.answer('Expired.',show_alert=True)
    media=s['candidates'].get(int(cq.matches[0].group(1)))
    if not media: return await cq.answer('Not found.',show_alert=True)
    s.update({
        'step':'await_source','title':anilist.best_title(media),'subtitle':anilist.subtitle(media),
        'synopsis':anilist.clean_synopsis(media.get('description','')),
        'rating':media.get('averageScore'),'genres':media.get('genres') or [],
        'season_text':anilist.season_label(media),'cover_url':media.get('coverImage',{}).get('extraLarge') or media.get('coverImage',{}).get('large'),
        'banner_url':media.get('bannerImage')
    })
    buttons=InlineKeyboardMarkup([[InlineKeyboardButton('Auto-fetch from AniList',callback_data='src:auto')],[InlineKeyboardButton("I'll provide 4 images",callback_data='src:manual')],[InlineKeyboardButton('Cancel',callback_data='cancel')]])
    await cq.message.edit(f"**{s['title']}** selected.\nSeason: `{s['season_text'] or 'N/A'}`\n\nChoose artwork source:",reply_markup=buttons); await cq.answer()

@app.on_callback_query(filters.regex(r'^cancel$'))
async def cancel_cb(_,cq): reset(cq.from_user.id); await cq.message.edit('Cancelled.'); await cq.answer()

@app.on_callback_query(filters.regex(r'^src:(auto|manual)$'))
async def source(_,cq):
    if not await require_admin(cq): return
    uid=cq.from_user.id; s=sessions.get(uid)
    if not s or s.get('step')!='await_source': return await cq.answer('Expired.',show_alert=True)
    choice=cq.matches[0].group(1)
    if choice=='manual':
        s['step']='await_bg'; s['manual']={}
        return await cq.message.edit('Send **image 1 — main background**.');
    await cq.message.edit('Fetching artwork from AniList...')
    tag=uuid.uuid4().hex[:8]
    paths={k:os.path.join(TEMP_DIR,f'{tag}_{k}.jpg') for k in ['cover','banner']}
    cover_ok=await anilist.download_image(s.get('cover_url'),paths['cover'])
    banner_ok=await anilist.download_image(s.get('banner_url'),paths['banner'])
    if not cover_ok: return await cq.message.edit("Couldn't download AniList artwork.")
    cover=Image.open(paths['cover']).convert('RGB'); banner=Image.open(paths['banner']).convert('RGB') if banner_ok else cover
    s['auto']={'background':banner,'top':cover,'card1':cover,'card2':banner}
    await render_and_send(cq.message,uid,'auto'); await cq.answer()

@app.on_message(filters.photo & filters.private)
async def photo(_,m):
    uid=m.from_user.id; s=sessions.get(uid)
    if not s or s.get('step') not in ('await_bg','await_top','await_card1','await_card2'): return
    if not await require_admin(m): return
    path=await m.download(file_name=os.path.join(TEMP_DIR,f'{uuid.uuid4().hex[:8]}.jpg')); img=Image.open(path).convert('RGB')
    step=s['step']
    if step=='await_bg': s['manual']['background']=img; s['step']='await_top'; return await m.reply('Got it. Now send **image 2 — top horizontal image**.')
    if step=='await_top': s['manual']['top']=img; s['step']='await_card1'; return await m.reply('Now send **image 3 — small card 1**.')
    if step=='await_card1': s['manual']['card1']=img; s['step']='await_card2'; return await m.reply('Now send **image 4 — small card 2**.')
    s['manual']['card2']=img; status=await m.reply('Generating thumbnail...'); await render_and_send(status,uid,'manual')

async def render_and_send(status,uid,source):
    s=sessions.get(uid)
    if not s: return await status.edit('Session expired. Run /thumb again.')
    imgs=s['auto'] if source=='auto' else s['manual']
    watermark=await db.get_watermark(); pid=uuid.uuid4().hex[:12]; pdir=os.path.join(TEMP_DIR,'projects',pid); os.makedirs(pdir,exist_ok=True)
    paths={}
    for k,img in imgs.items():
        paths[k]=os.path.join(pdir,f'{k}.jpg'); img.convert('RGB').save(paths[k],'JPEG',quality=95)
    accent=accent_from_image(imgs['background'])
    layout={
      'background_zoom':1.0,'background_focal':[.5,.5],
      'top_image':{'x':18,'y':142,'w':610,'h':300,'zoom':1.0,'focal':[.5,.5]},
      'synopsis':{'x':38,'y':468,'width':610,'heading_size':28,'body_size':14,'max_lines':5},
      'card1':{'x':690,'y':490,'w':128,'h':130,'zoom':1.0,'focal':[.5,.5]},
      'card2':{'x':690,'y':605,'w':128,'h':105,'zoom':1.0,'focal':[.5,.5]},
      'info_panel':{'x':825,'y':425,'w':430,'h':270}
    }
    project={'title':s['title'],'subtitle':s.get('subtitle',''),'romaji_title':s.get('subtitle',''),'synopsis':s.get('synopsis',''),'rating':s.get('rating'),'genres':s.get('genres',[]),'season_text':s.get('season_text'),'watermark':watermark,'accent_color':accent,'files':paths,'layout':layout,'default_layout':layout,'owner_id':uid,'id':pid}
    new_project(project)
    out=os.path.join(pdir,'preview.png'); render(project).save(out,'PNG')
    try: await status.delete()
    except Exception: pass
    buttons=[]
    if WEBAPP_URL: buttons.append([InlineKeyboardButton('✏️ Edit thumbnail',web_app=WebAppInfo(url=f'{WEBAPP_URL}/?project={pid}'))])
    buttons.append([InlineKeyboardButton('📥 Export / download',callback_data=f'export:{pid}')])
    await app.send_photo(uid,out,caption=f"**{s['title']}**\n\nEdit it with the button below.",reply_markup=InlineKeyboardMarkup(buttons))
    reset(uid)

@app.on_callback_query(filters.regex(r'^export:([a-z0-9]+)$'))
async def export(_,cq):
    if not await require_admin(cq): return
    await cq.answer('Open Edit thumbnail to export PNG, PDF or PPTX.',show_alert=True)

def run_web_server():
    uvicorn.run(web_app,host=os.environ.get('WEBAPP_HOST','0.0.0.0'),port=int(os.environ.get('WEBAPP_PORT','8080')),log_level='info')

if __name__=='__main__':
    if WEBAPP_URL:
        threading.Thread(target=run_web_server,daemon=True).start(); log.info('Web editor enabled at %s',WEBAPP_URL)
    else: log.warning('WEBAPP_URL is not set; the Edit button will not be shown.')
    app.run()
