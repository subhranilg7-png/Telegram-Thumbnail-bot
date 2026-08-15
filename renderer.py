from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont

W, H = 1280, 720
FONT_DIR = Path(__file__).resolve().parent / 'fonts'
EXTRA = str(FONT_DIR / 'Poppins-ExtraBold.ttf')
BOLD = str(FONT_DIR / 'Poppins-Bold.ttf')
SEMI = str(FONT_DIR / 'Poppins-SemiBold.ttf')
ACCENT = (77, 217, 232)
WHITE = (255, 255, 255)


def font(path, size):
    return ImageFont.truetype(path, size)


def fit_crop(img, size, focal=(0.5, 0.5), zoom=1.0):
    img = img.convert('RGB')
    tw, th = size
    sw, sh = img.size
    scale = max(tw / sw, th / sh) * max(zoom, 0.01)
    nw, nh = round(sw * scale), round(sh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    max_x, max_y = max(0, nw - tw), max(0, nh - th)
    left = int(max_x * min(max(focal[0], 0), 1))
    top = int(max_y * min(max(focal[1], 0), 1))
    return img.crop((left, top, left + tw, top + th))


def circle_image(img, diameter, zoom=1.0, focal=(0.5, 0.5)):
    base = fit_crop(img, (diameter, diameter), focal, zoom).convert('RGBA')
    mask = Image.new('L', (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter-1, diameter-1), fill=255)
    out = Image.new('RGBA', (diameter, diameter), (0,0,0,0))
    out.paste(base, (0,0), mask)
    return out


def wrap(draw, text, fnt, width, max_lines=9):
    words = (text or '').split()
    lines=[]; cur=''
    for word in words:
        t = (cur + ' ' + word).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur=t
        else:
            if cur: lines.append(cur)
            cur=word
            if len(lines) >= max_lines:
                break
    if cur and len(lines)<max_lines: lines.append(cur)
    if len(lines)==max_lines and sum(len(x.split()) for x in lines)<len(words):
        last=lines[-1]
        while draw.textlength(last+'...', font=fnt)>width and ' ' in last:
            last=last.rsplit(' ',1)[0]
        lines[-1]=last+'...'
    return lines


def title_lines(draw, text, width, start=48, minimum=28):
    for s in range(start, minimum-1, -2):
        f=font(EXTRA,s)
        ls=wrap(draw,text,f,width,2)
        if len(ls)<=2 and not ls[-1].endswith('...'):
            return f,ls
    f=font(EXTRA,minimum)
    return f,wrap(draw,text,f,width,2)


def shadow_text(draw, xy, text, fnt, fill=WHITE, anchor=None, offset=2):
    x,y=xy
    draw.text((x+offset,y+offset),text,font=fnt,fill=(0,0,0,180),anchor=anchor)
    draw.text((x,y),text,font=fnt,fill=fill,anchor=anchor)


def render(project):
    bg = Image.open(project['files']['background']).convert('RGB')
    poster = Image.open(project['files']['poster']).convert('RGB')
    circle = Image.open(project['files']['circle']).convert('RGB')
    p = project['layout']

    canvas = fit_crop(bg,(W,H), tuple(p.get('background_focal',[0.5,0.5])), p.get('background_zoom',1.0)).convert('RGBA')

    # Full-bleed poster on the right, blended into the composition.
    px = int(p.get('poster_x',850)); py=int(p.get('poster_y',0))
    pw=int(p.get('poster_w',430)); ph=int(p.get('poster_h',720))
    pi=fit_crop(poster,(pw,ph),tuple(p.get('poster_focal',[0.5,0.5])),p.get('poster_zoom',1.0)).convert('RGBA')
    canvas.alpha_composite(pi,(px,py))

    # Dark translucent left treatment; opacity is adjustable.
    overlay = Image.new('RGBA',(W,H),(18,18,24,int(p.get('overlay_opacity',120))))
    mask = Image.new('L',(W,H),0)
    md=ImageDraw.Draw(mask)
    fade=int(p.get('overlay_width',760))
    for x in range(W):
        if x <= fade: a=255
        else: a=max(0,int(255*(1-(x-fade)/(W-fade))))
        md.line((x,0,x,H),fill=a)
    overlay.putalpha(Image.eval(mask, lambda v: v*overlay.getchannel('A').getextrema()[1]//255))
    canvas.alpha_composite(overlay,(0,0))

    d=ImageDraw.Draw(canvas,'RGBA')
    # Optional panel, kept subtle like the Canva examples.
    panel=p.get('panel') or {}
    if panel.get('enabled',True):
        # Canva-like panel: wide enough for the title/body, but never a giant
        # dark card covering the whole left half. Height adapts to the text.
        x=int(panel.get('x',0)); y=int(panel.get('y',48)); w=int(panel.get('width',610))
        approx_h=int(panel.get('height',500))
        fill=tuple(panel.get('fill',[35,35,42,105]))
        d.rounded_rectangle((x,y,x+w,y+approx_h),radius=int(panel.get('radius',34)),fill=fill)

    title=p.get('title',{})
    tf, tls=title_lines(d,project['title'],int(title.get('max_width',650)),int(title.get('size',48)),26)
    tx,ty=int(title.get('x',58)),int(title.get('y',58))
    lh=int(tf.size*1.16)
    for line in tls:
        shadow_text(d,(tx,ty),line,tf)
        ty+=lh

    if project.get('season_text'):
        sf=font(SEMI,int(p.get('season_size',23)))
        d.text((tx,ty+2),project['season_text'].upper(),font=sf,fill=WHITE,stroke_width=1,stroke_fill=(0,0,0,170))
        ty+=38

    syn=p.get('synopsis',{})
    heading=font(SEMI,int(syn.get('heading_size',21)))
    body=font(BOLD,int(syn.get('body_size',19)))
    sx,sy=int(syn.get('x',60)),int(syn.get('y',250))
    sw=int(syn.get('width',600))
    d.text((sx+sw//2,sy),'SYNOPSIS',font=heading,fill=ACCENT,anchor='ma',stroke_width=1,stroke_fill=(0,0,0,100))
    sy+=42
    lines=wrap(d,project.get('synopsis',''),body,sw,int(syn.get('max_lines',9)))
    align=syn.get('align','center')
    for line in lines:
        if align=='left': xx=sx
        elif align=='right': xx=sx+sw; 
        else: xx=sx+sw/2
        shadow_text(d,(xx,sy),line,body,anchor='ra' if align=='right' else ('ma' if align=='center' else 'la'),offset=1)
        sy+=29

    # Decorative dot grids.
    def dots(x,y,rows,cols,spacing=21):
        for r in range(rows):
            for c in range(cols):
                d.ellipse((x+c*spacing-2,y+r*spacing-2,x+c*spacing+2,y+r*spacing+2),fill=(255,255,255,125))
    dots(875,22,2,16)
    dots(34,675,2,16)

    c=p.get('circle',{})
    size=int(c.get('size',420)); cx=int(c.get('x',850)); cy=int(c.get('y',370))
    ring=int(c.get('border',8))
    d.ellipse((cx-size//2-ring,cy-size//2-ring,cx+size//2+ring,cy+size//2+ring),fill=WHITE)
    ci=circle_image(circle,size,c.get('zoom',1.0),tuple(c.get('focal',[0.5,0.5])))
    canvas.alpha_composite(ci,(cx-size//2,cy-size//2))
    d=ImageDraw.Draw(canvas,'RGBA')

    # Sparkle near circle.
    sx0,sy0=int(c.get('sparkle_x',720)),int(c.get('sparkle_y',555))
    d.line((sx0-10,sy0,sx0+10,sy0),fill=WHITE,width=2); d.line((sx0,sy0-10,sx0,sy0+10),fill=WHITE,width=2)

    wm=project.get('watermark','@Ongoing_english_dub')
    wf=font(BOLD,24)
    ww=int(d.textlength(wm,font=wf)+46)
    d.rectangle((0,H-55,ww,H),fill=ACCENT)
    d.text((23,H-44),wm,font=wf,fill=(20,20,20))

    br=p.get('bottom_title',{})
    bf, bl=title_lines(d,project['title'],int(br.get('max_width',360)),int(br.get('size',30)),18)
    y=int(br.get('y',630)); right=int(br.get('right',28))
    for line in bl:
        tw=d.textlength(line,font=bf)
        shadow_text(d,(W-right-tw,y),line,bf,offset=2)
        y+=int(bf.size*1.15)
    if project.get('season_text'):
        sf=font(SEMI,16); text=project['season_text'].upper(); tw=d.textlength(text,font=sf)
        d.text((W-right-tw,y+2),text,font=sf,fill=WHITE,stroke_width=1,stroke_fill=(0,0,0,150))

    return canvas.convert('RGB')
