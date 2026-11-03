"""Tiêu đề mở đầu: chữ kim loại (hoặc logo của bạn) đập vào màn hình, trôi chậm, rồi vụt ra.

y.json:
    "tieu_de_mo": {"chu": "WARHAMMER|40K", "phu": "IST DER IMPERATOR TOT?", "den": 3.6, "y": 0.42}
- `chu`: chữ kim loại, `|` xuống dòng (dòng đầu to nhất). `phu`: dòng phụ màu vàng (không bắt buộc).
- Có file `du-an/<ten>/logo.png` (tải lên trên trang) → dùng logo đó thay cho chữ.
- `den`: giây tiêu đề vụt đi (mặc định 3.6, không quá hết ý 1). `y`: vị trí theo chiều cao. `co`: cỡ (1.0).
Trong lúc tiêu đề hiện, chữ nhấn của ý 1 tạm ẩn.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = Path(__file__).resolve().parent / 'font' / 'Montserrat.ttf'
LAND = 0.32   # giây bay vào
OUT = 0.28    # giây vụt ra


def _font(size, weight='Black'):
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_name(weight)
    return f


def _metal_text(text, size):
    f = _font(size)
    stroke = max(3, size // 13)
    pad = stroke * 3
    w, h = int(f.getlength(text)) + pad * 2, int(size * 1.2) + pad * 2
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).text((pad, pad), text, font=f, fill=255)
    outline = Image.new('L', (w, h), 0)
    ImageDraw.Draw(outline).text((pad, pad), text, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    # thép: sáng – tối – sáng theo chiều dọc, có vệt phản chiếu
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    g = 0.78 + 0.22 * np.cos((yy - 0.18) * math.pi * 2.2)
    g = np.clip(g - 0.22 * (np.abs(yy - 0.55) < 0.02), 0, 1)
    steel = np.dstack([g * 236, g * 241, g * 248]).repeat(w, axis=1).astype(np.uint8)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    edge = Image.new('RGBA', (w, h), (18, 22, 32, 255))
    out.paste(edge, (0, 0), outline)
    face = Image.fromarray(steel, 'RGB').convert('RGBA')
    out.paste(face, (0, 0), mask)
    return out


def _gold_text(text, size):
    f = _font(size, 'ExtraBold')
    stroke = max(2, size // 12)
    pad = stroke * 3
    w, h = int(f.getlength(text)) + pad * 2, int(size * 1.25) + pad * 2
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad, pad), text, font=f, fill=(238, 196, 96, 255), stroke_width=stroke, stroke_fill=(24, 18, 10, 255))
    return im


def make_title(cfg, W, logo=None):
    if logo is not None:
        im = logo.convert('RGBA')
        s = min(W * 0.9 / im.width, W * 0.55 / im.height)
        return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    lines = [l for l in cfg.get('chu', 'WARHAMMER|40K').split('|') if l.strip()]
    co = float(cfg.get('co', 1.0))
    parts = []
    size = None
    for i, main in enumerate(lines):
        sz = int(W * (0.2 if i == 0 else 0.15) * co)
        m = _metal_text(main, sz)
        while m.width > W * 0.92 and sz > 30:
            sz = int(sz * 0.93)
            m = _metal_text(main, sz)
        size = size or sz
        parts.append(m)
    if cfg.get('phu'):
        ps = int(W * 0.055 * co)
        p = _gold_text(cfg['phu'], ps)
        while p.width > W * 0.92 and ps > 16:
            ps = int(ps * 0.92)
            p = _gold_text(cfg['phu'], ps)
        line = Image.new('RGBA', (int(parts[0].width * 0.8), max(3, size // 22)), (238, 196, 96, 235))
        parts += [line, p]
    w = max(p.width for p in parts)
    gap = int(size * 0.2)
    h = sum(p.height for p in parts) - gap * (len(lines))
    out = Image.new('RGBA', (w, h + size // 6), (0, 0, 0, 0))
    y = 0
    for i, p in enumerate(parts):
        out.alpha_composite(p, ((w - p.width) // 2, y))
        y += p.height - (gap if i < len(lines) else 0)
    sh = Image.new('RGBA', out.size, (0, 0, 0, 0))
    sh.putalpha(out.getchannel('A').filter(ImageFilter.GaussianBlur(size // 8)).point(lambda v: int(v * 0.85)))
    # dải nền tối viền vàng phía sau cho chữ nổi trên mọi ảnh
    bw, bh = int(W * 1.04), out.height + size // 2
    yy = np.linspace(0, 1, bh, dtype=np.float32)[:, None]
    alpha = (0.82 - 0.25 * np.abs(yy - 0.5) * 2) * 255
    band = np.zeros((bh, bw, 4), np.uint8)
    band[..., 0], band[..., 1], band[..., 2] = 12, 16, 26
    band[..., 3] = alpha.astype(np.uint8).repeat(bw, axis=1)
    edge = max(3, size // 26)
    band[:edge, :, :3] = (226, 184, 86)
    band[:edge, :, 3] = 255
    band[-edge:, :, :3] = (226, 184, 86)
    band[-edge:, :, 3] = 255
    final = Image.fromarray(band, 'RGBA')
    final.alpha_composite(sh, ((bw - sh.width) // 2, (bh - sh.height) // 2 + size // 14))
    final.alpha_composite(out, ((bw - out.width) // 2, (bh - out.height) // 2))
    return final


class Title:
    def __init__(self, img, t_end, W, H, y):
        self.img, self.t_end, self.W, self.H, self.y = img, t_end, W, H, y

    def active(self, t):
        return t < self.t_end

    def draw(self, frame, t):
        if t >= self.t_end:
            return frame
        if t < LAND:  # đập vào: to → nhỏ, vượt một chút rồi về
            u = t / LAND
            sc = 2.4 - 1.46 * (1 - (1 - u) ** 3)
            alpha = min(1.0, u * 2.2)
            blur = (1 - u) * 6
        else:
            k = t - LAND
            bounce = 0.06 * math.exp(-k * 9) * math.cos(k * 26)
            sc = 0.94 + 0.06 * min(1.0, k / 0.12) + bounce + 0.025 * k  # trôi to dần chậm
            alpha, blur = 1.0, 0
        if t > self.t_end - OUT:
            v = (t - (self.t_end - OUT)) / OUT
            sc *= 1 + 0.9 * v * v
            alpha *= 1 - v
            blur = v * 8
        w, h = max(1, int(self.img.width * sc)), max(1, int(self.img.height * sc))
        im = self.img.resize((w, h), Image.BILINEAR)
        if blur > 0.5:
            im = im.filter(ImageFilter.GaussianBlur(blur))
        if alpha < 0.999:
            im.putalpha(im.getchannel('A').point(lambda a, al=alpha: int(a * al)))
        shake = 0
        if LAND <= t < LAND + 0.25:
            shake = int(self.W * 0.012 * (1 - (t - LAND) / 0.25) * math.sin(t * 90))
        fr = frame.convert('RGBA')
        fr.alpha_composite(im, ((self.W - w) // 2 + shake, int(self.H * self.y - h / 2) + shake // 2))
        if LAND <= t < LAND + 0.1:  # chớp sáng lúc chạm
            fl = Image.new('RGBA', fr.size, (255, 245, 225, int(70 * (1 - (t - LAND) / 0.1))))
            fr.alpha_composite(fl)
        return fr.convert('RGB')


def build(d, plan, timing, W, H):
    cfg = plan.get('tieu_de_mo')
    if not cfg:
        return None
    logo = None
    for name in ('logo.png', 'logo.webp', 'logo.jpg'):
        if (d / name).exists():
            logo = Image.open(d / name)
            break
    first_end = timing['y'][0]['ket_thuc'] if timing.get('y') else 4.0
    t_end = min(float(cfg.get('den', 3.6)), first_end)
    return Title(make_title(cfg, W, logo), t_end, W, H, float(cfg.get('y', 0.42)))
