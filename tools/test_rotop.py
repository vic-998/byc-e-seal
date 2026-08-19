# -*- coding: utf-8 -*-
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from PIL import Image

# 1) make a simple seal
size = 300
img = Image.new("RGBA", (size, size), (255,255,255,255))
from PIL import ImageDraw
d = ImageDraw.Draw(img)
d.ellipse([20,20,size-20,size-20], outline=(200,20,30,255), width=12)
d.ellipse([80,80,size-80,size-80], outline=(200,20,30,255), width=6)
img = A.process_seal(img, remove_bg=True)
sid = "testseal"
A.seal_to_dict(sid, img, "testseal")
print("seal saved", os.path.exists(os.path.join(A.SEALS_DIR, sid+".png")), img.size)

# 2) a tiny blank A4 pdf via reportlab
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
pdf = os.path.join(A.FILES_DIR, "testsrc.pdf")
c = canvas.Canvas(pdf, pagesize=A4)
c.drawString(80, 700, "Hello contract")
c.showPage(); c.save()

out = os.path.join(A.FILES_DIR, "testout.pdf")

cases = [
    {"page":1,"sealId":sid,"x":0.5,"y":0.5,"scale":1.0,"rot":0,"opacity":1.0,"sliceCount":0,"sliceIdx":0},
    {"page":1,"sealId":sid,"x":0.25,"y":0.3,"scale":1.0,"rot":45,"opacity":0.6,"sliceCount":0,"sliceIdx":0},
    {"page":1,"sealId":sid,"x":0.7,"y":0.2,"scale":1.2,"rot":-90,"opacity":1.0,"sliceCount":0,"sliceIdx":0},
    {"page":1,"sealId":sid,"x":0.5,"y":0.7,"scale":1.0,"rot":30,"opacity":0.7,"sliceCount":0,"sliceIdx":0},
    # cross seal
    {"page":1,"sealId":sid,"x":1.0,"y":0.5,"scale":1.0,"rot":0,"opacity":0.8,"sliceCount":3,"sliceIdx":0},
    {"page":1,"sealId":sid,"x":1.0,"y":0.5,"scale":1.0,"rot":0,"opacity":0.8,"sliceCount":3,"sliceIdx":1},
    {"page":1,"sealId":sid,"x":1.0,"y":0.5,"scale":1.0,"rot":0,"opacity":0.8,"sliceCount":3,"sliceIdx":2},
]
A.render_stamps(pdf, cases, out)
from pypdf import PdfReader
r = PdfReader(out)
print("pages", len(r.pages), "size", r.pages[0].mediabox)
print("OK export wrote", os.path.getsize(out), "bytes")

# check tmp leftovers
left = [f for f in os.listdir(A.SEALS_DIR) if f.startswith("tmp_")]
print("leftover tmp files:", left)
