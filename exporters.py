from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from renderer import W, H, render


def export_png(project, out):
    render(project).save(out, 'PNG')


def export_pdf(project, out):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    img=render(project)
    c=canvas.Canvas(out,pagesize=(W,H))
    c.drawImage(ImageReader(img),0,0,width=W,height=H)
    c.save()


def export_pptx(project,out):
    # The exact Canva-style composition is rasterized for fidelity. Text/image
    # data remain editable through the Telegram Mini App, while the PPTX keeps
    # the visual result pixel-stable across PowerPoint versions.
    prs=Presentation(); prs.slide_width=Inches(13.333333); prs.slide_height=Inches(7.5)
    slide=prs.slides.add_slide(prs.slide_layouts[6])
    img=render(project)
    tmp=Path(out).with_name(Path(out).stem+'_render.png')
    img.save(tmp,'PNG')
    slide.shapes.add_picture(str(tmp),0,0,width=prs.slide_width,height=prs.slide_height)
    prs.save(out)
    try: tmp.unlink()
    except OSError: pass
