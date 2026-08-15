from pathlib import Path
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from renderer import W,H,fit_crop,circle_image,render


def export_png(project, out):
    render(project).save(out, 'PNG')


def export_pdf(project, out):
    # PDF is a high-quality export. PDF itself is not a Canva-style native
    # design format; the artwork is rendered as a page image for fidelity.
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    img=render(project)
    c=canvas.Canvas(out,pagesize=(W,H))
    c.drawImage(ImageReader(img),0,0,width=W,height=H)
    c.save()


def _add_text(slide,text,x,y,w,h,size,bold=True,align=PP_ALIGN.LEFT,color=(255,255,255)):
    s=slide.shapes.add_textbox(Inches(x/W*13.333333),Inches(y/H*7.5),Inches(w/W*13.333333),Inches(h/H*7.5))
    tf=s.text_frame; tf.clear(); tf.word_wrap=True
    p=tf.paragraphs[0]; p.alignment=align
    r=p.add_run(); r.text=text; r.font.name='Poppins'; r.font.size=Pt(size*0.75); r.font.bold=bold; r.font.color.rgb=RGBColor(*color)
    return s


def _add_panel(slide,x,y,w,h,radius,rgba):
    shape=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x/W*13.333333), Inches(y/H*7.5), Inches(w/W*13.333333), Inches(h/H*7.5))
    shape.fill.solid(); shape.fill.fore_color.rgb=RGBColor(rgba[0],rgba[1],rgba[2]); shape.fill.transparency=max(0,min(100,100-rgba[3]/255*100))
    shape.line.fill.background(); return shape


def export_pptx(project,out):
    prs=Presentation(); prs.slide_width=Inches(13.333333); prs.slide_height=Inches(7.5)
    slide=prs.slides.add_slide(prs.slide_layouts[6]); p=project['layout']
    # Editable image layers.
    bg=Image.open(project['files']['background']).convert('RGB')
    poster=Image.open(project['files']['poster']).convert('RGB')
    bg_layer=fit_crop(bg,(W,H),tuple(p.get('background_focal',[.5,.5])),p.get('background_zoom',1.0))
    slide.shapes.add_picture(_temp_png(bg_layer,out,'_bg'),0,0,width=prs.slide_width,height=prs.slide_height)
    px,py,pw,ph=[int(p[k]) for k in ('poster_x','poster_y','poster_w','poster_h')]
    pl=fit_crop(poster,(pw,ph),tuple(p.get('poster_focal',[.5,.5])),p.get('poster_zoom',1.0))
    slide.shapes.add_picture(_temp_png(pl,out,'_poster'), Inches(px/W*13.333333), Inches(py/H*7.5), width=Inches(pw/W*13.333333), height=Inches(ph/H*7.5))
    # Editable-ish overlay/panel shapes.
    _add_panel(slide,0,0,int(p.get('overlay_width',720)),H,0,(18,18,24,p.get('overlay_opacity',115)))
    pan=p.get('panel',{})
    if pan.get('enabled',True):
        x,y,w,h=map(int,pan.get('box',[24,32,680,650])); _add_panel(slide,x,y,w,h,int(pan.get('radius',34)),tuple(pan.get('fill',[25,25,32,118])))
    # Circle as transparent PNG image plus editable white border.
    c=p['circle']; size=int(c['size']); ci=circle_image(Image.open(project['files']['circle']),size,c.get('zoom',1.0),tuple(c.get('focal',[.5,.5])))
    cp=_temp_png(ci,out,'_circle')
    cx,cy=int(c['x']),int(c['y']); ring=int(c.get('border',8))
    border=slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches((cx-size/2-ring)/W*13.333333), Inches((cy-size/2-ring)/H*7.5), Inches((size+2*ring)/W*13.333333), Inches((size+2*ring)/H*7.5))
    border.fill.solid(); border.fill.fore_color.rgb=RGBColor(255,255,255); border.line.fill.background()
    slide.shapes.add_picture(cp, Inches((cx-size/2)/W*13.333333), Inches((cy-size/2)/H*7.5), width=Inches(size/W*13.333333), height=Inches(size/H*7.5))
    # Editable text.
    t=p['title']; _add_text(slide,project['title'],t['x'],t['y'],t.get('max_width',650),130,t.get('size',48),True)
    if project.get('season_text'): _add_text(slide,project['season_text'].upper(),t['x'],t['y']+105,420,38,p.get('season_size',23),True)
    s=p['synopsis']; _add_text(slide,'SYNOPSIS',s['x'],s['y'],s['width'],35,s.get('heading_size',21),True,PP_ALIGN.CENTER,(77,217,232)); _add_text(slide,project['synopsis'],s['x'],s['y']+38,s['width'],280,s.get('body_size',19),True,PP_ALIGN.CENTER)
    _add_text(slide,project.get('watermark','@Ongoing_english_dub'),0,H-55,500,55,24,True,PP_ALIGN.LEFT,(20,20,20))
    b=p['bottom_title']; _add_text(slide,project['title'],W-b.get('right',28)-b.get('max_width',360),b.get('y',630),b.get('max_width',360),80,b.get('size',30),True,PP_ALIGN.RIGHT)
    if project.get('season_text'): _add_text(slide,project['season_text'].upper(),W-b.get('right',28)-b.get('max_width',360),690,b.get('max_width',360),25,16,True,PP_ALIGN.RIGHT)
    prs.save(out)
    for tmp in Path(out).parent.glob(Path(out).stem+'_*tmp.png'):
        try: tmp.unlink()
        except OSError: pass


def _temp_png(img,out,suffix):
    p=Path(out).with_name(Path(out).stem+suffix+'tmp.png'); img.save(p,'PNG'); return str(p)
