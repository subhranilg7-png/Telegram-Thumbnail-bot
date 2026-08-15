"""Renderer for the Ongoing English Dub anime card design.

Design target: 1280x720. The main image drives the accent colour.
Four image slots are supported:
  1. main background
  2. top horizontal image
  3. small card 1
  4. small card 2

All anime metadata (title, synopsis, rating, season/year, genres) is supplied
by AniList through the bot project state.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont, ImageOps

W, H = 1280, 720
FONT_DIR = Path(__file__).resolve().parent / 'fonts'
EXTRA = str(FONT_DIR / 'Poppins-ExtraBold.ttf')
BOLD = str(FONT_DIR / 'Poppins-Bold.ttf')
SEMI = str(FONT_DIR / 'Poppins-SemiBold.ttf')
WHITE = (255,255,255)


def font(path, size):
    return ImageFont.truetype(path, max(8, int(size)))


def fit_crop(img, size, focal=(0.5,0.5), zoom=1.0):
    img = img.convert('RGB')
    tw, th = size
    sw, sh = img.size
    scale = max(tw/sw, th/sh) * max(float(zoom), 0.01)
    nw, nh = max(tw, round(sw*scale)), max(th, round(sh*scale))
    img = img.resize((nw,nh), Image.LANCZOS)
    max_x, max_y = nw-tw, nh-th
    left = int(max_x * min(max(float(focal[0]),0),1))
    top = int(max_y * min(max(float(focal[1]),0),1))
    return img.crop((left,top,left+tw,top+th))


def rounded_image(img, size, radius, focal=(0.5,0.5), zoom=1.0, border=0, border_color=(255,255,255)):
    base = fit_crop(img, size, focal, zoom).convert('RGBA')
    w,h=size
    mask=Image.new('L',(w,h),0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),radius=radius,fill=255)
    out=Image.new('RGBA',(w,h),(0,0,0,0)); out.paste(base,(0,0),mask)
    if border:
        b=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(b)
        d.rounded_rectangle((1,1,w-2,h-2),radius=radius,outline=border_color,width=border)
        out=Image.alpha_composite(out,b)
    return out


def wrap(draw, text, fnt, width, max_lines=8):
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
        while draw.textlength(last+'...',font=fnt)>width and ' ' in last:
            last=last.rsplit(' ',1)[0]
        lines[-1]=last+'...'
    return lines


def title_fit(draw, text, width, start=54, minimum=25, max_lines=2):
    for s in range(start, minimum-1, -2):
        f=font(EXTRA,s); ls=wrap(draw,text,f,width,max_lines)
        if len(ls)<=max_lines and not (ls and ls[-1].endswith('...')):
            return f,ls
    f=font(EXTRA,minimum); return f,wrap(draw,text,f,width,max_lines)


def shadow_text(draw, xy, text, fnt, fill=WHITE, anchor=None, offset=2, stroke=0):
    x,y=xy
    draw.text((x+offset,y+offset),text,font=fnt,fill=(0,0,0,190),anchor=anchor,stroke_width=stroke,stroke_fill=(0,0,0,190))
    draw.text((x,y),text,font=fnt,fill=fill,anchor=anchor,stroke_width=stroke,stroke_fill=(0,0,0,120))


def accent_from_image(img):
    """Extract a vivid representative colour using PIL quantization."""
    small=fit_crop(img,(160,90),zoom=1.0).convert('RGB')
    # Avoid black/white dominating the palette.
    q=small.quantize(colors=20,method=Image.Quantize.MEDIANCUT).convert('RGB')
    colors=q.getcolors(maxcolors=100000) or []
    candidates=[]
    for count,rgb in colors:
        r,g,b=rgb
        mx=max(rgb); mn=min(rgb)
        if mx < 35 or mn > 235: continue
        # saturation proxy and brightness
        sat=(mx-mn)/max(mx,1)
        val=mx/255
        score=count*(0.35+sat*1.7)*(0.5+val)
        candidates.append((score,rgb))
    if not candidates:
        return (220,55,65)
    rgb=max(candidates,key=lambda x:x[0])[1]
    # Push toward a readable vivid accent.
    r,g,b=rgb
    mx=max(rgb); mn=min(rgb)
    if mx-mn < 35:
        # Neutral images get a restrained warm accent.
        return (210,70,80)
    factor=1.12
    rr=int(max(0,min(255,128+(r-128)*factor)))
    gg=int(max(0,min(255,128+(g-128)*factor)))
    bb=int(max(0,min(255,128+(b-128)*factor)))
    return (rr,gg,bb)


def darken(rgb, amount=0.38):
    return tuple(int(c*amount) for c in rgb)


def with_alpha(rgb,a): return (rgb[0],rgb[1],rgb[2],int(a))


def draw_decorations(d, accent):
    # Header geometric triangles/lines.
    ar=with_alpha(accent,150)
    for ox,oy,s in [(70,25,42),(128,12,55),(190,38,38),(250,18,46)]:
        d.line((ox,oy,ox+s,oy+10,ox+s-14,oy+s,ox,oy),fill=ar,width=2)
    # Crescent/arc at top-left.
    d.arc((22,10,120,105),190,350,fill=(255,255,255,220),width=3)
    d.arc((30,18,108,94),205,315,fill=with_alpha(accent,130),width=2)
    # Simple branch + perched-bird silhouette.
    branch=(190,190,190,150)
    d.line((430,95,480,62,530,74,570,48),fill=branch,width=3)
    d.line((480,62,462,30),fill=branch,width=3)
    d.ellipse((485,30,507,55),fill=branch)
    d.polygon([(480,55),(500,58),(520,83),(488,78)],fill=branch)
    # Right decorative stars/diamonds.
    for cx,cy in [(1130,75),(1160,72),(1190,77)]:
        d.polygon([(cx,cy-8),(cx+7,cy),(cx,cy+8),(cx-7,cy)],fill=with_alpha(accent,220))
    # Small red/colour ticks under synopsis.
    for i in range(52):
        x=18+i*9.4
        h=14 if i<40 else 8
        d.rectangle((x,684,x+4,684+h),fill=with_alpha(accent,235))
    # Three white chevrons.
    for i in range(3):
        x=555+i*22
        d.line((x,686,x+13,699,x,712),fill=(255,255,255,245),width=4)


def render(project, scale=1):
    bg=Image.open(project['files']['background']).convert('RGB')
    top=Image.open(project['files']['top']).convert('RGB')
    card1=Image.open(project['files']['card1']).convert('RGB')
    card2=Image.open(project['files']['card2']).convert('RGB')
    p=project.get('layout',{})
    accent=tuple(project.get('accent_color') or accent_from_image(bg))

    canvas=fit_crop(bg,(W,H),tuple(p.get('background_focal',[0.5,0.5])),p.get('background_zoom',1.0)).convert('RGBA')
    # Gentle dark gradient for readability while preserving artwork.
    shade=Image.new('RGBA',(W,H),(0,0,0,0)); sd=ImageDraw.Draw(shade,'RGBA')
    for x in range(W):
        a=int(135*(1-min(x/W,1)*0.48))
        sd.line((x,0,x,H),fill=(0,0,0,a))
    canvas=Image.alpha_composite(canvas,shade)
    d=ImageDraw.Draw(canvas,'RGBA')
    draw_decorations(d,accent)

    # Header.
    wf=font(BOLD,24)
    shadow_text(d,(45,48),project.get('watermark','@Ongoing_english_dub'),wf,fill=accent,offset=2)
    tag=font(SEMI,11); d.text((96,91),'•  THE BEST POSSIBLE ONGOING ANIME EXPERIENCE',font=tag,fill=WHITE)

    # Top horizontal image.
    t=p.get('top_image',{}); tx,ty,tw,th=[int(t.get(k,v)) for k,v in [('x',18),('y',142),('w',610),('h',300)]]
    ti=rounded_image(top,(tw,th),34,tuple(t.get('focal',[0.5,0.5])),t.get('zoom',1.0),3,accent)
    canvas.alpha_composite(ti,(tx,ty)); d=ImageDraw.Draw(canvas,'RGBA')

    # Synopsis.
    syn=p.get('synopsis',{}); sx,sy,sw=[int(syn.get(k,v)) for k,v in [('x',40),('y',468),('width',610)]]
    hf=font(SEMI,int(syn.get('heading_size',28))); bf=font(SEMI,int(syn.get('body_size',14)))
    d.text((sx+sw/2,sy),'✦  SYNOPSIS  ✦',font=hf,fill=WHITE,anchor='ma')
    lines=wrap(d,project.get('synopsis',''),bf,sw,int(syn.get('max_lines',5)))
    yy=sy+43
    for line in lines:
        d.text((sx+sw/2,yy),line,font=bf,fill=WHITE,anchor='ma')
        yy+=21

    # Rating.
    rating=project.get('rating')
    rating_text='N/A' if rating in (None,'') else f'{float(rating):.1f}/10'
    rf=font(BOLD,28); d.text((150,615),'RATING:',font=rf,fill=WHITE)
    rw=d.textlength('RATING:',font=rf); d.text((150+rw+10,615),rating_text,font=rf,fill=accent)
    small=font(SEMI,12); d.text((150,658),'The ratings are sourced from a trusted anime',font=small,fill=WHITE)
    d.text((150,676),'information website called AniList',font=small,fill=WHITE)

    # Small cards.
    c1=p.get('card1',{}); c2=p.get('card2',{})
    for im,c in [(card1,c1),(card2,c2)]:
        x,y,w,h=[int(c.get(k,v)) for k,v in [('x',690),('y',490),('w',128),('h',130)]]
        ci=rounded_image(im,(w,h),20,tuple(c.get('focal',[0.5,0.5])),c.get('zoom',1.0),4,accent)
        canvas.alpha_composite(ci,(x,y)); d=ImageDraw.Draw(canvas,'RGBA')

    # Season/year badge. No Friday label.
    season_text=project.get('season_text')
    if season_text:
        sf=font(SEMI,17); sw=d.textlength(season_text.upper(),font=sf)+42
        x=1000; y=390
        d.rounded_rectangle((x,y,x+sw,y+38),radius=18,fill=(15,15,20,120),outline=accent,width=2)
        d.text((x+sw/2,y+19),season_text.upper(),font=sf,fill=accent,anchor='mm')
        d.line((x+sw+12,y+19,1250,y+19),fill=with_alpha(accent,180),width=2)

    # Right glass info panel.
    pan=p.get('info_panel',{}); x,y,w,h=[int(pan.get(k,v)) for k,v in [('x',825),('y',425),('w',430),('h',270)]]
    # Frosted effect: subtle blur of background underneath.
    under=canvas.crop((x,y,x+w,y+h)).filter(ImageFilter.GaussianBlur(4))
    canvas.alpha_composite(under,(x,y))
    d=ImageDraw.Draw(canvas,'RGBA')
    d.rounded_rectangle((x,y,x+w,y+h),radius=30,fill=(22,22,28,155),outline=(130,130,135,150),width=2)
    d.ellipse((x+w-48,y+20,x+w-16,y+52),fill=with_alpha(accent,225))
    d.ellipse((x+w-48,y+h-52,x+w-16,y+h-20),fill=with_alpha(accent,225))

    title=project.get('title','Untitled')
    subtitle=project.get('subtitle') or project.get('romaji_title') or ''
    tf,tls=title_fit(d,title,w-85,48,25,2)
    yy=y+27
    for line in tls:
        d.text((x+w/2,yy),line,font=tf,fill=WHITE,anchor='ma')
        yy+=int(tf.size*1.0)
    if subtitle and subtitle.lower()!=title.lower():
        sf2=font(SEMI,17); d.text((x+w/2,yy+2),subtitle,font=sf2,fill=accent,anchor='ma')
        yy+=28
    d.line((x+90,yy+8,x+w-90,yy+8),fill=with_alpha(accent,230),width=2); yy+=35
    if season_text:
        d.text((x+w/2,yy),season_text.upper().replace('  ',' '),font=font(SEMI,18),fill=WHITE,anchor='ma'); yy+=35
    genres=project.get('genres') or []
    # pills, up to 6
    pill_y=yy
    rows=[genres[:3],genres[3:6]]
    for ri,row in enumerate(rows):
        if not row: continue
        widths=[]
        pf=font(SEMI,12)
        for g in row:
            widths.append(max(80,int(d.textlength(g.upper(),font=pf)+32)))
        gap=10; total=sum(widths)+gap*(len(widths)-1); xx=x+(w-total)/2
        for gi,g in enumerate(row):
            pw=widths[gi]; active=(ri==0 and gi==0)
            d.rounded_rectangle((xx,pill_y,xx+pw,pill_y+32),radius=16,
                                fill=with_alpha(accent,235) if active else (25,25,30,90),
                                outline=accent if not active else with_alpha(accent,235),width=1)
            d.text((xx+pw/2,pill_y+16),g.upper(),font=pf,fill=WHITE,anchor='mm')
            xx+=pw+gap
        pill_y+=42
    d.line((x+w/2-32,pill_y+4,x+w/2+32,pill_y+4),fill=with_alpha(accent,235),width=2)
    d.text((x+w/2,pill_y+30),project.get('watermark','@Ongoing_english_dub'),font=font(SEMI,14),fill=accent,anchor='ma')

    if scale != 1:
        canvas=canvas.resize((W*scale,H*scale),Image.Resampling.LANCZOS)
    return canvas.convert('RGB')
