from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageStat
import colorsys, math

W, H = 1280, 720
FONT_DIR = Path(__file__).resolve().parent / 'fonts'
EXTRA = str(FONT_DIR / 'Poppins-ExtraBold.ttf')
BOLD = str(FONT_DIR / 'Poppins-Bold.ttf')
SEMI = str(FONT_DIR / 'Poppins-SemiBold.ttf')
WHITE=(248,248,248)


def font(path,size): return ImageFont.truetype(path,size)


def fit_crop(img,size,focal=(.5,.5),zoom=1.0):
    img=img.convert('RGB'); tw,th=size; sw,sh=img.size
    scale=max(tw/sw,th/sh)*max(.01,zoom)
    nw,nh=round(sw*scale),round(sh*scale); img=img.resize((nw,nh),Image.LANCZOS)
    mx,my=max(0,nw-tw),max(0,nh-th)
    left=int(mx*min(1,max(0,focal[0]))); top=int(my*min(1,max(0,focal[1])))
    return img.crop((left,top,left+tw,top+th))


def rounded_image(img,size,radius):
    img=img.convert('RGB').resize(size,Image.LANCZOS).convert('RGBA')
    mask=Image.new('L',size,0); ImageDraw.Draw(mask).rounded_rectangle((0,0,size[0]-1,size[1]-1),radius=radius,fill=255)
    out=Image.new('RGBA',size,(0,0,0,0)); out.paste(img,(0,0),mask); return out


def wrap(draw,text,fnt,width,max_lines):
    words=(text or '').split(); lines=[]; cur=''
    for word in words:
        trial=(cur+' '+word).strip()
        if draw.textlength(trial,font=fnt)<=width: cur=trial
        else:
            if cur: lines.append(cur)
            cur=word
            if len(lines)>=max_lines: break
    if cur and len(lines)<max_lines: lines.append(cur)
    if len(lines)==max_lines and sum(len(x.split()) for x in lines)<len(words):
        last=lines[-1]
        while draw.textlength(last+'...',font=fnt)>width and ' ' in last: last=last.rsplit(' ',1)[0]
        lines[-1]=last+'...'
    return lines


def fit_title(draw,text,width,start=64,minimum=30,max_lines=2):
    for s in range(start,minimum-1,-2):
        f=font(EXTRA,s); ls=wrap(draw,text,f,width,max_lines)
        if len(ls)<=max_lines and not ls[-1].endswith('...'): return f,ls
    f=font(EXTRA,minimum); return f,wrap(draw,text,f,width,max_lines)


def shadow(draw,xy,text,fnt,fill=WHITE,anchor=None,offset=2):
    x,y=xy; draw.text((x+offset,y+offset),text,font=fnt,fill=(0,0,0,170),anchor=anchor); draw.text((x,y),text,font=fnt,fill=fill,anchor=anchor)


def extract_accent(img):
    # Dominant saturated mid-tone colour. Falls back to AniList cover colour if present upstream.
    small=img.convert('RGB').resize((96,96))
    q=small.quantize(colors=24,method=Image.Quantize.MEDIANCUT)
    pal=q.getpalette(); counts=q.getcolors() or []
    candidates=[]
    for n,idx in counts:
        r,g,b=pal[idx*3:idx*3+3]
        h,s,v=colorsys.rgb_to_hsv(r/255,g/255,b/255)
        if s<.28 or v<.18 or v>.98: continue
        score=n*(0.25+s)*(0.65+abs(v-.55)*-0.2 if v else .65)
        candidates.append((score,n,(r,g,b),s,v,h))
    if not candidates: return (235,54,61)
    _,_,rgb,_,_,_=max(candidates,key=lambda x:x[0])
    r,g,b=rgb
    # Slightly strengthen colour for readable UI accents.
    h,s,v=colorsys.rgb_to_hsv(r/255,g/255,b/255)
    s=min(1,max(.55,s*1.12)); v=min(.92,max(.72,v*1.08))
    return tuple(round(x*255) for x in colorsys.hsv_to_rgb(h,s,v))


def dark_panel(draw,box,accent,alpha=170,radius=34):
    draw.rounded_rectangle(box,radius=radius,fill=(12,13,17,alpha),outline=(*accent,115),width=1)


def draw_header_decor(draw,accent):
    # Crescent/glow
    draw.arc((22,18,112,108),205,335,fill=(245,245,245,235),width=3)
    draw.arc((30,25,106,100),210,315,fill=(255,255,255,90),width=2)
    # abstract triangles
    for pts in [[(135,12),(175,43),(127,51)],[(185,28),(226,8),(211,62)],[(236,2),(266,42),(222,55)]]:
        draw.line(pts+[pts[0]],fill=(*accent,100),width=2)
    # stylised branch + small bird-like silhouettes
    branch=(118,118,122,220)
    draw.line((520,0,520,80),fill=(230,230,230,150),width=4)
    draw.line((520,70,500,91),fill=(230,230,230,150),width=3)
    draw.line((520,65,543,88),fill=(230,230,230,150),width=3)
    draw.ellipse((549,18,571,48),fill=(220,220,220,190))
    draw.polygon([(550,48),(532,74),(566,72)],fill=(220,220,220,170))
    draw.line((555,62,582,48),fill=(220,220,220,170),width=3)
    draw.line((540,61,516,46),fill=(220,220,220,170),width=3)


def draw_divider(draw,y,accent):
    x1,x2=18,620
    for x in range(x1,x2,12): draw.rectangle((x,y,x+7,y+5),fill=(*accent,225))
    # three chevrons
    for off in (0,24,48):
        draw.line((548+off,y-7,560+off,y+5),fill=WHITE,width=3)
        draw.line((560+off,y+5,548+off,y+17),fill=WHITE,width=3)


def draw_genre_pill(draw,box,text,active,accent):
    x1,y1,x2,y2=box
    fill=(*accent,235) if active else (20,21,26,125)
    outline=(*accent,220) if active else (220,220,220,170)
    draw.rounded_rectangle(box,radius=20,fill=fill,outline=outline,width=1)
    f=font(SEMI,14); draw.text(((x1+x2)/2,(y1+y2)/2),text,font=f,fill=(255,255,255,235),anchor='mm')


def render(project):
    files=project['files']; p=project.get('layout',{})
    bg=Image.open(files['background']).convert('RGB')
    top=Image.open(files.get('top',files.get('poster'))).convert('RGB')
    card1=Image.open(files.get('card1',files.get('circle'))).convert('RGB')
    card2=Image.open(files.get('card2',files.get('circle'))).convert('RGB')

    accent=tuple(project.get('accent') or extract_accent(bg))
    canvas=fit_crop(bg,(W,H),tuple(p.get('background_focal',[.5,.5])),p.get('background_zoom',1.0)).convert('RGBA')

    # Dark editorial treatment on the left, matching the selected reference.
    grad=Image.new('RGBA',(W,H),(0,0,0,0)); gd=ImageDraw.Draw(grad,'RGBA')
    for x in range(0,650):
        a=int(175*(1-x/700))
        gd.line((x,0,x,H),fill=(0,0,0,max(0,a)))
    canvas.alpha_composite(grad)
    d=ImageDraw.Draw(canvas,'RGBA')

    # ------------------------------ header / decorations
    draw_header_decor(d,accent)
    wm=project.get('watermark','@Ongoing_english_dub')
    wf=font(EXTRA,23)
    shadow(d,(42,48),wm,wf,fill=(*accent,255),offset=2)
    d.text((96,78),'•  THE BEST POSSIBLE ONGOING ANIME EXPERIENCE',font=font(SEMI,9),fill=WHITE)

    # ------------------------------ image 2: top horizontal artwork
    top_box=(18,109,635,344)
    d.rounded_rectangle(top_box,radius=30,fill=(8,8,12,35),outline=(*accent,245),width=3)
    ti=fit_crop(top,(610,228),tuple(p.get('top_focal',[.5,.5])),p.get('top_zoom',1.0)).convert('RGBA')
    mask=Image.new('L',(610,228),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,609,227),radius=27,fill=255)
    canvas.alpha_composite(Image.composite(ti,Image.new('RGBA',(610,228),(0,0,0,0)),mask),(21,112))
    d=ImageDraw.Draw(canvas,'RGBA')
    d.rounded_rectangle(top_box,radius=30,outline=(*accent,245),width=3)

    # ------------------------------ synopsis
    sh=font(EXTRA,25)
    d.text((255,380),'✦  SYNOPSIS  ✦',font=sh,fill=WHITE,anchor='ma',stroke_width=1,stroke_fill=(0,0,0,120))
    body=font(BOLD,14)
    lines=wrap(d,project.get('synopsis',''),body,360,7)
    y=408
    for line in lines:
        d.text((255,y),line,font=body,fill=WHITE,anchor='ma',stroke_width=1,stroke_fill=(0,0,0,120)); y+=19

    # Divider: dense accent ticks + white chevrons.
    for x in range(18,444,10): d.rectangle((x,539,x+6,544),fill=(*accent,235))
    for off in (0,24,48):
        d.line((428+off,533,439+off,544),fill=WHITE,width=3)
        d.line((439+off,544,428+off,555),fill=WHITE,width=3)

    # ------------------------------ rating
    rating=project.get('rating')
    if rating is None: rating=(project.get('averageScore') or 0)/10
    try: rating=float(rating)
    except: rating=0.0
    rf=font(EXTRA,30)
    d.text((255,607),f'RATING: {rating:.1f}/10',font=rf,fill=WHITE,anchor='ma')
    rsmall=font(SEMI,10)
    d.text((255,646),'The ratings are sourced from a trusted anime',font=rsmall,fill=WHITE,anchor='ma')
    d.text((255,665),'information website called AniList',font=rsmall,fill=WHITE,anchor='ma')

    # ------------------------------ vertical tool rail decoration
    d.rounded_rectangle((17,568,58,708),radius=20,fill=(2,3,5,225))
    for i,yy in enumerate((584,624,664)):
        d.ellipse((29,yy,47,yy+18),outline=(245,245,245,210),width=2)
        if i<2: d.line((27,yy+27,49,yy+27),fill=(245,245,245,150),width=1)

    # ------------------------------ cards (images 3 & 4)
    for idx,img in enumerate((card1,card2)):
        x,y0=623,394+idx*147
        box=(x,y0,x+139,y0+137)
        d.rounded_rectangle(box,radius=17,fill=(8,8,12,180),outline=(*accent,245),width=3)
        ci=fit_crop(img,(119,117),tuple(p.get('card_focal',[.5,.5])),p.get('card_zoom',1.0)).convert('RGBA')
        mask=Image.new('L',(119,117),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,118,116),radius=13,fill=255)
        canvas.alpha_composite(Image.composite(ci,Image.new('RGBA',(119,117),(0,0,0,0)),mask),(633,y0+10))
        d=ImageDraw.Draw(canvas,'RGBA'); d.rounded_rectangle(box,radius=17,outline=(*accent,245),width=3)

    # ------------------------------ season badge above info panel
    season=project.get('season_text')
    if season:
        sf=font(SEMI,15); sw=d.textlength(season.upper(),font=sf)+46
        x1=1000-sw/2; y1=355
        d.rounded_rectangle((x1,y1,x1+sw,y1+34),radius=18,fill=(8,8,12,165),outline=(*accent,240),width=2)
        d.text((1000,y1+17),season.upper(),font=sf,fill=(*accent,255),anchor='mm')

    # ------------------------------ right information glass panel
    panel=(797,398,1248,690)
    d.rounded_rectangle(panel,radius=30,fill=(38,39,44,182),outline=(190,190,195,105),width=1)
    d.ellipse((1197,414,1228,445),fill=(*accent,245))
    d.ellipse((1197,661,1228,692),fill=(*accent,245))

    title=project.get('title','').upper()
    tf,tls=fit_title(d,title,390,42,26,2)
    yy=431
    for line in tls:
        d.text((1022,yy),line,font=tf,fill=WHITE,anchor='ma',stroke_width=1,stroke_fill=(0,0,0,130)); yy+=int(tf.size*1.0)
    subtitle=project.get('subtitle') or ''
    if subtitle:
        subf=font(SEMI,14)
        d.text((1022,yy+3),subtitle,font=subf,fill=(*accent,255),anchor='ma')
    d.line((915,509,1130,509),fill=(*accent,230),width=2)
    if season:
        d.text((1022,528),season.upper().replace('  ',' '),font=font(SEMI,15),fill=WHITE,anchor='ma')

    genres=project.get('genres') or []
    pill_specs=[(845,552,942,581),(948,552,1065,581),(1072,552,1189,581),
                (845,594,942,623),(948,594,1065,623),(1072,594,1210,623)]
    for i,g in enumerate(genres[:6]): draw_genre_pill(d,pill_specs[i],g,i==0,accent)
    d.line((1000,645,1044,645),fill=(*accent,230),width=2)
    d.text((1022,665),wm,font=font(SEMI,13),fill=(*accent,255),anchor='ma')

    # Decorative accent stars/chevrons around the season line.
    for x in (1100,1125,1150):
        d.polygon([(x,364),(x+4,370),(x,376),(x-4,370)],fill=(*accent,230))
    d.line((1169,374,1247,374),fill=(*accent,200),width=2)

    # Intentionally no FRIDAY label and no duplicate bottom-right title.
    return canvas.convert('RGB')
