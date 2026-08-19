# -*- coding: utf-8 -*-
import base64
import io
import json
import math
import os
import traceback
import uuid
from collections import deque

from flask import Flask, jsonify, request, send_file, send_from_directory
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, "files")
SEALS_DIR = os.path.join(BASE_DIR, "seals")
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(SEALS_DIR, exist_ok=True)

# 印章标准尺寸：宽 4cm
WORK_DPI = 150
SEAL_WIDTH_CM = 4.0
SEAL_WIDTH_PX = int(round(SEAL_WIDTH_CM / 2.54 * WORK_DPI))       # 236 px
SEAL_WIDTH_PT = SEAL_WIDTH_PX / WORK_DPI * 72                     # ~113.3 pt = 4cm

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024


def cn_font(size):
    for p in (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _is_bg(px, threshold):
    r, g, b, a = px
    return a > 0 and r >= threshold and g >= threshold and b >= threshold


def remove_white_bg(img, threshold=244):
    """从边缘泛洪，去除与边界相连的白色背景，保留文字/图案内部白色"""
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    seen = set()
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if (x, y) not in seen and _is_bg(px[x, y], threshold):
                seen.add((x, y))
                dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if (x, y) not in seen and _is_bg(px[x, y], threshold):
                seen.add((x, y))
                dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        px[x, y] = (255, 255, 255, 0)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and _is_bg(px[nx, ny], threshold):
                    seen.add((nx, ny))
                    dq.append((nx, ny))
    return img


def _star(cx, cy, r_out, r_in, n=5):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def process_seal(img, remove_bg=True):
    if remove_bg:
        img = remove_white_bg(img)
    img = img.convert("RGBA")
    box = img.getbbox()
    if box:
        img = img.crop(box)
    ratio = img.height / img.width
    img = img.resize((SEAL_WIDTH_PX, max(2, int(round(SEAL_WIDTH_PX * ratio)))), Image.LANCZOS)
    return img


def seal_to_dict(sid, img, name):
    path = os.path.join(SEALS_DIR, sid + ".png")
    img.save(path, "PNG")
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    return {
        "id": sid,
        "url": "/seals/%s.png?t=%d" % (sid, 0),
        "name": name or "seal",
        "wPx": img.size[0],
        "hPx": img.size[1],
        "wCm": round(img.size[0] / WORK_DPI * 2.54, 3),
        "hCm": round(img.size[1] / WORK_DPI * 2.54, 3),
        "ratio": round(img.size[1] / img.size[0], 4),
        "dataUrl": "data:image/png;base64," + b64,
    }


@app.get("/")
def index():
    return send_from_directory(os.path.join(BASE_DIR, "templates"), "index.html")


@app.get("/seals/<path:name>")
def seal_file(name):
    return send_from_directory(SEALS_DIR, name)


@app.get("/files/<path:name>")
def file_get(name):
    return send_from_directory(FILES_DIR, name)


@app.get("/api/files/<path:name>")
def api_file_get(name):
    return send_from_directory(FILES_DIR, name)


def save_upload(file_storage, suffix):
    fid = uuid.uuid4().hex[:12]
    path = os.path.join(FILES_DIR, fid + suffix)
    file_storage.save(path)
    return fid, path


@app.post("/api/pdf")
def upload_pdf():
    f = request.files.get("file")
    if not f:
        return jsonify(error="未收到文件"), 400
    data = f.read()
    if data[:5] != b"%PDF-":
        return jsonify(error="不是有效的 PDF 文件"), 400
    try:
        from pypdf import PdfReader
        probe = PdfReader(io.BytesIO(data))
        if not probe.pages:
            raise ValueError("PDF 没有页面")
    except Exception as e:
        return jsonify(error="PDF 文件损坏或无法解析：%s" % e), 400
    fid = uuid.uuid4().hex[:12]
    f2 = io.BytesIO(data)
    from werkzeug.datastructures import FileStorage
    f = FileStorage(stream=f2, filename=f.filename or "contract.pdf")
    f.save(os.path.join(FILES_DIR, fid + ".pdf"))
    return jsonify(id=fid, name=f.filename or "contract.pdf")


@app.post("/api/seal")
def upload_seal():
    f = request.files.get("file")
    if not f:
        return jsonify(error="未收到印章图片"), 400
    try:
        img = Image.open(io.BytesIO(f.read()))
    except Exception:
        return jsonify(error="图片无法识别，请上传 png/jpg 格式印章"), 400
    remove_bg = request.form.get("removeBg") == "1"
    try:
        img = process_seal(img, remove_bg)
    except Exception as e:
        return jsonify(error="印章处理失败：%s" % e), 500
    sid = uuid.uuid4().hex[:12]
    return jsonify(seal_to_dict(sid, img, f.filename or "seal"))


@app.post("/api/sample-seal")
def sample_seal():
    size = SEAL_WIDTH_PX * 3
    img = Image.new("RGBA", (size, size), (250, 250, 250, 255))
    d = ImageDraw.Draw(img)
    red = (206, 17, 26, 255)
    m = int(size * 0.04)
    d.ellipse([m, m, size - m, size - m], outline=red, width=int(size * 0.035))
    cx, cy = size / 2, size * 0.36
    d.polygon(_star(cx, cy, size * 0.13, size * 0.055), fill=red)
    f1 = cn_font(int(size * 0.10))
    t1 = "电子印章示例"
    d.text((size / 2 - d.textlength(t1, font=f1) / 2, size * 0.54), t1, font=f1, fill=red)
    f2 = cn_font(int(size * 0.065))
    t2 = "四厘米标准尺寸"
    d.text((size / 2 - d.textlength(t2, font=f2) / 2, size * 0.70), t2, font=f2, fill=red)
    img = process_seal(img, remove_bg=True)
    sid = uuid.uuid4().hex[:12]
    return jsonify(seal_to_dict(sid, img, "sample_seal"))


def make_sample_contract(path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font_path = r"C:\Windows\Fonts\simhei.ttf"
    if not os.path.exists(font_path):
        font_path = r"C:\Windows\Fonts\msyh.ttc"
    pdfmetrics.registerFont(TTFont("CN", font_path))

    w, h = A4
    c = canvas.Canvas(path)
    x = 60
    maxw = w - 120

    clauses = [
        "服务内容与范围：乙方按照甲方提交的任务书，向甲方提供系统开发、技术咨询及相关技术服务，并保证服务质量符合任务书要求。",
        "服务方式：乙方采取现场服务与远程服务相结合的方式提供服务，重要节点由双方共同确认并留存书面记录。",
        "服务期限：自本合同生效之日起十二个月，如需延长服务期限，由双方另行书面确认后执行。",
        "合同金额：本合同总金额为人民币壹拾贰万元整（¥120,000.00），该价格为完成全部服务内容的含税价格。",
        "付款方式：合同生效后十五日内甲方向乙方支付合同总额的百分之三十；全部服务验收合格后三十日内支付剩余百分之七十款项。",
        "甲方义务：甲方应及时提供必要的资料、数据及工作条件，按约定时间支付服务费用，并指定专人负责项目联络。",
        "乙方义务：乙方应严格按照约定的时间和质量要求完成服务内容，对服务过程中知悉的甲方信息承担保密义务。",
        "知识产权：本项目最终交付成果的知识产权归甲方所有，乙方保留通用工具与方法在后续项目中的复用权利。",
        "验收标准：以任务书及双方共同签署的验收单为准，验收不合格的，乙方应在十个工作日内完成整改并重新提交验收。",
        "违约责任：任何一方违反本合同约定的，应向守约方支付合同总额百分之五的违约金；违约金不足以弥补损失的，仍应据实赔偿。",
        "保密条款：双方对因履行本合同而知悉的对方商业秘密与技术秘密均负有保密义务，未经对方书面同意不得向任何第三方披露。",
        "争议解决：因本合同引起的或与本合同有关的争议，双方应友好协商解决；协商不成的，任何一方均可向甲方所在地人民法院提起诉讼。",
    ]

    y = h - 70

    def new_page():
        nonlocal y
        c.showPage()
        y = h - 70

    def draw_wrapped(text, size):
        nonlocal y
        c.setFont("CN", size)
        buf = ""
        for ch in text:
            if c.stringWidth(buf + ch, "CN", size) > maxw:
                c.drawString(x, y, buf)
                y -= 24
                if y < 70:
                    new_page()
                buf = ch
            else:
                buf += ch
        if buf:
            c.drawString(x, y, buf)
            y -= 24
        if y < 70:
            new_page()

    # 标题
    c.setFont("CN", 20)
    title = "技 术 服 务 合 同"
    c.drawString((w - c.stringWidth(title, "CN", 20)) / 2, y, title)
    y -= 46

    head = [
        "合同编号：ETS-2026-0819-001",
        "签订地点：北京市海淀区",
        "甲方（委托方）：北京某某科技有限公司",
        "乙方（受托方）：某某信息技术有限公司",
        "",
        "甲乙双方本着平等自愿、诚实信用的原则，经友好协商，就技术开发与技术服务事宜达成如下协议，以资共同遵守。",
    ]
    for t in head:
        if t:
            draw_wrapped(t, 11)
        else:
            y -= 12
            if y < 70:
                c.showPage()
                y = h - 70

    for i, t in enumerate(clauses, 1):
        draw_wrapped("第%d条　%s" % (i, t), 11)
        y -= 6
        if y < 90:
            c.showPage()
            y = h - 70

    for i in range(1, 13):
        draw_wrapped("附则%d：本合同未尽事宜，由双方另行协商并签订书面补充协议，补充协议与本合同具有同等法律效力。本合同一式两份，甲乙双方各执一份，自双方盖章之日起生效。" % i, 11)
        y -= 6
        if y < 90:
            c.showPage()
            y = h - 70

    y -= 10
    if y < 140:
        c.showPage()
        y = h - 70
    draw_wrapped("甲方（盖章）：", 12)
    y -= 8
    draw_wrapped("法定代表人或授权代表：", 11)
    y -= 8
    draw_wrapped("日期：　　　　　　年　　月　　日", 11)
    y -= 18
    draw_wrapped("乙方（盖章）：", 12)
    y -= 8
    draw_wrapped("法定代表人或授权代表：", 11)
    y -= 8
    draw_wrapped("日期：　　　　　　年　　月　　日", 11)
    c.save()


@app.post("/api/sample")
def sample_contract():
    fid = uuid.uuid4().hex[:12]
    path = os.path.join(FILES_DIR, fid + ".pdf")
    try:
        make_sample_contract(path)
    except Exception as e:
        traceback.print_exc()
        return jsonify(error="生成示例合同失败：%s" % e), 500
    return jsonify(id=fid, name="示例技术服务合同.pdf")


def office_to_pdf(src, dst):
    try:
        import comtypes.client
    except ImportError:
        raise RuntimeError("缺少 comtypes 库，请先执行 pip install comtypes")
    win_word = r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
    if os.path.exists(win_word):
        word = comtypes.client.CreateObject("{000209FF-0000-0000-C000-000000000046}")
    else:
        raise RuntimeError("未检测到 Microsoft Word，请安装 Office 后重试")
    try:
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(os.path.abspath(str(src)), ReadOnly=True)
        try:
            word.Documents.ActiveDocument.Close(False) if False else None
            doc.SaveAs(os.path.abspath(str(dst)), FileFormat=17)
        finally:
            doc.Close(False)
    finally:
        try:
            word.Quit()
        except Exception:
            pass


@app.post("/api/word2pdf")
def word2pdf():
    f = request.files.get("file")
    if not f:
        return jsonify(error="未收到文件"), 400
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in (".docx", ".doc"):
        return jsonify(error="仅支持 .docx / .doc 格式"), 400
    data = f.read()
    fid = uuid.uuid4().hex[:12]
    tmp = os.path.join(FILES_DIR, fid + ext)
    out = os.path.join(FILES_DIR, fid + ".pdf")
    with open(tmp, "wb") as fh:
        fh.write(data)
    try:
        office_to_pdf(tmp, out)
    except Exception as e:
        return jsonify(error="Word 转换失败（%s）。请确认本机已安装 Microsoft Word。" % e), 500
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    name = os.path.splitext(f.filename or "document.docx")[0] + ".pdf"
    return jsonify(id=fid, name=name)


def render_stamps(src, stamps, out):
    """按页生成叠加层 merge 到原合同。stamp 字段：
    page(1起), x,y(中心点占页面比例 y从上往下), scale(1.0=标准4cm宽),
    骑缝章: sliceCount(N片), sliceIdx(该片序号)
    """
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas as _canvas

    reader = PdfReader(src)
    writer = PdfWriter(clone_from=reader)
    dims = [(float(p.mediabox.width), float(p.mediabox.height)) for p in reader.pages]

    by_page = {}
    for s in stamps:
        try:
            pid = int(s.get("page", 1))
        except Exception:
            continue
        by_page.setdefault(pid - 1, []).append(s)

    PT_4CM = 4.0 / 2.54 * 72.0
    for idx, ss in by_page.items():
        if idx < 0 or idx >= len(writer.pages):
            continue
        W, H = dims[idx]
        buf = io.BytesIO()
        cv = _canvas.Canvas(buf, pagesize=(W, H))
        cv.setLineWidth(0)
        for s in ss:
            seal_id = str(s.get("sealId") or "")
            if not seal_id:
                continue
            sp = os.path.join(SEALS_DIR, seal_id + ".png")
            if not os.path.exists(sp):
                continue
            pil = Image.open(sp).convert("RGBA")
            w_px, h_px = pil.size
            ratio = h_px / w_px
            scale = max(0.05, min(5.0, float(s.get("scale", 1.0))))
            w_full = PT_4CM * scale
            h_full = w_full * ratio
            yC = float(s.get("y", 0.5))
            cy_pt = (1.0 - yC) * H
            try:
                rot = float(s.get("rot", 0) or 0)
            except Exception:
                rot = 0
            try:
                opacity = float(s.get("opacity", 1) or 1)
            except Exception:
                opacity = 1.0
            tmp = os.path.join(SEALS_DIR, "tmp_%s.png" % uuid.uuid4().hex[:8])
            try:
                try:
                    n = int(s.get("sliceCount") or 0)
                except Exception:
                    n = 0
                if n > 1:
                    i = max(0, min(int(s.get("sliceIdx", 0)), n - 1))
                    frag = pil.crop([
                        int(w_px * i / n),
                        0,
                        min(w_px, int(math.ceil(w_px * (i + 1) / n))),
                        h_px,
                    ])
                    frag = frag.convert("RGBA")
                    if opacity < 1.0:
                        a = frag.getchannel("A").point(lambda v: int(v * opacity))
                        frag.putalpha(a)
                    frag.save(tmp, "PNG")
                    w_vis = w_full / n
                    h_vis = h_full
                    x0 = W - w_vis
                    y0 = cy_pt - h_full / 2.0
                else:
                    rad = math.radians(rot % 360)
                    rw = abs(w_full * math.cos(rad)) + abs(h_full * math.sin(rad))
                    rh = abs(w_full * math.sin(rad)) + abs(h_full * math.cos(rad))
                    if rot:
                        ang = -int(round(rot / 45) * 45) % 360
                        if ang:
                            pil = pil.rotate(ang, expand=True, resample=Image.BICUBIC)
                    if opacity < 1.0:
                        a = pil.getchannel("A").point(lambda v: int(v * opacity))
                        pil.putalpha(a)
                    pil.save(tmp, "PNG")
                    w_vis = rw
                    h_vis = rh
                    xC = float(s.get("x", 0.5))
                    x0 = xC * W - rw / 2.0
                    y0 = cy_pt - rh / 2.0
                cv.drawImage(tmp, x0, y0, width=w_vis, height=h_vis, preserveAspectRatio=False, mask="auto")
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        cv.save()
        buf.seek(0)
        writer.pages[idx].merge_page(PdfReader(buf).pages[0])

    with open(out, "wb") as fh:
        writer.write(fh)


@app.post("/api/export")
def export_pdf():
    fid = request.form.get("fileId")
    seals_raw = request.form.get("seals", "[]")
    src = os.path.join(FILES_DIR, fid + ".pdf") if fid else ""
    if not fid or not os.path.exists(src):
        return jsonify(error="找不到源 PDF 文件，请重新上传合同"), 400
    try:
        stamps = json.loads(seals_raw)
    except Exception:
        return jsonify(error="seals 参数不是合法 JSON"), 400
    if not isinstance(stamps, list) or not stamps:
        return jsonify(error="还没有添加任何印章"), 400
    out = os.path.join(FILES_DIR, "out-" + uuid.uuid4().hex[:10] + ".pdf")
    try:
        render_stamps(src, stamps, out)
    except Exception as e:
        traceback.print_exc()
        return jsonify(error="盖章失败：%s" % e), 500
    name = request.form.get("outName") or "已盖章合同.pdf"
    return send_file(out, mimetype="application/pdf", as_attachment=True, download_name=name)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    print("电子印章服务已启动: http://127.0.0.1:%d" % port)
    app.run(host="127.0.0.1", port=port, debug=False)
