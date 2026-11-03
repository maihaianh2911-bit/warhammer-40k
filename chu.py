"""Chữ nhấn (kinetic typography) kiểu video lore: 1–3 từ khóa to giữa màn hình, bật lên đúng lúc giọng đọc tới.

Trong y.json, mỗi ý:
    "chu_nhan": [
      {"tu_chu": "Perpetual", "chu": "ein sogenannter|*PERPETUAL*"},
      {"tu_chu": "Tod", "chu": "*TOD*", "y": 0.38}
    ]
- `chu`: các dòng ngăn bằng `|`. Dòng VIẾT HOA = chữ to, dòng thường = chữ nhỏ. `*…*` = màu nhấn (xanh ngọc).
  Một dòng trộn được: "HÀNG *CHỤC*".
- `tu_chu`: hiện khi giọng đọc tới từ đó (bỏ trống = đầu ý). Giữ tới chữ nhấn kế tiếp hoặc hết ý (`den_chu` = tắt ở từ đó).
- `y`: vị trí giữa khối chữ theo chiều cao (mặc định 0.45).
Toàn video: "mau_nhan": [40, 230, 200] · "co_chu": 1.0 (to/nhỏ cả khối).
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = Path(__file__).resolve().parent / 'font' / 'Montserrat-Italic.ttf'
_cache = {}


def _font(size, weight):
    key = (size, weight)
    if key not in _cache:
        f = ImageFont.truetype(str(FONT), size)
        f.set_variation_by_name(weight)
        _cache[key] = f
    return _cache[key]


def _ease(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def _segments(line):
    parts = line.split('*')
    return [(p, i % 2 == 1) for i, p in enumerate(parts) if p]


def render_line(line, W, accent, scale):
    segs = _segments(line)
    plain = ''.join(p for p, _ in segs)
    big = plain.strip() and plain.upper() == plain and any(c.isalpha() for c in plain)
    size = int(W * (0.135 if big else 0.064) * scale)
    weight = 'Black Italic'
    f = _font(size, weight)
    while big and f.getlength(plain) > W * 0.9 and size > 20:
        size = int(size * 0.92)
        f = _font(size, weight)
    pad = int(size * 0.35)
    tw = int(f.getlength(plain)) + pad * 2
    th = int(size * 1.25) + pad * 2
    txt = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    x = pad
    for p, acc in segs:
        d.text((x, pad), p, font=f, fill=accent + (255,) if acc else (248, 248, 248, 255))
        x += f.getlength(p)
    sh = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    a = txt.getchannel('A').filter(ImageFilter.GaussianBlur(max(2, size // 10)))
    sh.putalpha(a.point(lambda v: int(v * 0.8)))
    out = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    out.alpha_composite(sh, (0, max(2, size // 18)))
    out.alpha_composite(txt)
    return out, big


class Block:
    def __init__(self, text, t0, t1, W, H, y, accent, scale):
        self.t0, self.t1, self.W, self.H = t0, t1, W, H
        self.lines = [render_line(l, W, accent, scale) for l in text.split('|') if l.strip()]
        total = sum(im.height * 0.78 for im, _ in self.lines)
        self.pos = []
        cy = H * y - total / 2
        nbig = sum(1 for _, b in self.lines if b)
        k = 0
        for im, big in self.lines:
            dx = 0
            if big and nbig >= 2:  # hai dòng to so le trái/phải như video mẫu
                dx = int(W * 0.045) * (-1 if k % 2 == 0 else 1)
                k += 1
            self.pos.append(((W - im.width) // 2 + dx, int(cy)))
            cy += im.height * 0.78

    def draw(self, frame, t):
        if not (self.t0 <= t < self.t1):
            return
        out_a = min(1.0, (self.t1 - t) / 0.12)
        for i, ((im, _big), (x, y)) in enumerate(zip(self.lines, self.pos)):
            u = (t - self.t0 - i * 0.09) / 0.2
            if u <= 0:
                continue
            e = _ease(u)
            alpha = e * out_a
            sc = 1.3 - 0.3 * e
            if abs(sc - 1) > 0.005:
                w, h = max(1, int(im.width * sc)), max(1, int(im.height * sc))
                img = im.resize((w, h), Image.BILINEAR)
                xx, yy = x - (w - im.width) // 2, y - (h - im.height) // 2 + int((1 - e) * self.H * 0.015)
            else:
                img, xx, yy = im, x, y
            if alpha < 0.999:
                img = img.copy()
                img.putalpha(img.getchannel('A').point(lambda v, a=alpha: int(v * a)))
            frame.alpha_composite(img, (xx, yy))


def build(beats, timing, W, H, plan, cut_at, word_times):
    tmap = {t['so']: t for t in timing['y']}
    accent = tuple(plan.get('mau_nhan', [40, 230, 200]))
    scale = float(plan.get('co_chu', 1.0)) * (W / 1080) / (W / 1080)
    blocks = []
    for b in beats:
        items = b.get('chu_nhan') or []
        t = tmap.get(b['so'])
        if not items or not t:
            continue
        words = word_times(timing, b['so'])
        starts, prev = [], t['bat_dau'] - 1
        for it in items:
            st = t['bat_dau'] if not it.get('tu_chu') else cut_at(words, it['tu_chu'], prev, t['bat_dau'], t['ket_thuc'] - 0.3)
            st = t['bat_dau'] if st is None else st + 0.04
            starts.append(st)
            prev = st
        for i, it in enumerate(items):
            end = starts[i + 1] if i + 1 < len(items) else t['ket_thuc']
            if it.get('den_chu'):
                e2 = cut_at(words, it['den_chu'], starts[i], starts[i], end)
                end = e2 if e2 else end
            blocks.append(Block(it['chu'], starts[i], max(end, starts[i] + 0.6), W, H, float(it.get('y', 0.45)), accent, scale))
    return blocks


def draw_all(blocks, frame, t):
    act = [b for b in blocks if b.t0 <= t < b.t1]
    if not act:
        return frame
    fr = frame.convert('RGBA')
    for b in act:
        b.draw(fr, t)
    return fr.convert('RGB')
