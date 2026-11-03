#!/usr/bin/env python3
"""Nhân vật kênh: chuẩn bị ảnh biểu cảm (tự cắt + xóa nền) và vẽ nhân vật vào video.

Ảnh gốc: kenh/nhan-vat/goc/ (tải trên trang). Một ảnh có 6 tư thế xếp lưới (nền một màu, tốt nhất xanh lá)
→ tự cắt theo thứ tự trái→phải, trên→dưới thành 6 biểu cảm. Hoặc nhiều ảnh, mỗi ảnh một biểu cảm (theo tên file
nếu tên có chữ biểu cảm, không thì theo thứ tự tên).
    python3 nhan_vat.py           → kenh/nhan-vat/<bieu_cam>.png (nền trong suốt)

Biểu cảm: binh_thuong · ngac_nhien · cuoi · so · suy_nghi · chi_tay

Trong y.json, mỗi ý (không bắt buộc):
    "nhan_vat": [{"bieu_cam": "ngac_nhien", "tu_chu": "Tod", "giay": 2.2, "ben": "phai"}]
- hiện khi giọng đọc tới `tu_chu` (bỏ trống = đầu ý), giữ `giay` giây (mặc định 2.4), `ben`: trai / phai (mặc định phai).
Toàn video: "co_nhan_vat": 0.30 (chiều cao so với khung) · "nhan_vat": false (tắt).
"""
import math, re, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent
DIR = ROOT / 'kenh' / 'nhan-vat'
GOC = DIR / 'goc'
NAMES = ['binh_thuong', 'ngac_nhien', 'cuoi', 'so', 'suy_nghi', 'chi_tay']
ALIAS = {'binh_thuong': ['binh', 'neutral', 'normal', 'thuong'], 'ngac_nhien': ['ngac', 'shock', 'surprise', 'wow'],
         'cuoi': ['cuoi', 'laugh', 'smile', 'happy'], 'so': ['so', 'scared', 'fear', 'afraid'],
         'suy_nghi': ['suy', 'think', 'nghi'], 'chi_tay': ['chi', 'point']}
IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp')


# ───────────────────────── xóa nền + cắt ─────────────────────────

def key_out(im):
    """Nền một màu (lấy theo viền ảnh) → trong suốt. Ảnh đã có alpha thì giữ."""
    im = im.convert('RGBA')
    a = np.asarray(im).astype(np.float32)
    if a[..., 3].min() < 250:  # đã trong suốt sẵn
        return im
    rgb = a[..., :3]
    border = np.concatenate([rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3), rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    alpha = np.clip((dist - 40) / 50, 0, 1)
    m = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5))
    m = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    alpha = np.asarray(m, dtype=np.float32) / 255
    if bg[1] > bg[0] + 40 and bg[1] > bg[2] + 40:  # nền xanh lá → khử viền xanh
        g = rgb[..., 1]
        lim = np.maximum(rgb[..., 0], rgb[..., 2])
        rgb[..., 1] = np.where(g > lim, lim + (g - lim) * 0.25, g)
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def _runs(profile, min_gap):
    """Các đoạn có nội dung, tách nhau bởi khe trống dài ≥ min_gap."""
    on = profile > 0
    runs, start, gap = [], None, 0
    for i, v in enumerate(on):
        if v:
            if start is None:
                start = i
            gap = 0
            end = i
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                runs.append((start, end + 1))
                start, gap = None, 0
    if start is not None:
        runs.append((start, end + 1))
    return runs


def split_sheet(im):
    """Ảnh nhiều tư thế (nền đã trong suốt) → danh sách ảnh, trái→phải, trên→dưới."""
    a = np.asarray(im.getchannel('A')) > 60
    h, w = a.shape
    rows = _runs(a.sum(axis=1) > w * 0.004, max(4, h // 60))
    parts = []
    for y0, y1 in rows:
        band = a[y0:y1]
        cols = _runs(band.sum(axis=0) > (y1 - y0) * 0.01, max(4, w // 60))
        for x0, x1 in cols:
            if (x1 - x0) * (y1 - y0) < w * h * 0.01:
                continue
            parts.append(im.crop((x0, y0, x1, y1)))
    return parts


def trim(im, pad=6):
    box = im.getchannel('A').point(lambda v: 255 if v > 30 else 0).getbbox()
    if not box:
        return im
    x0, y0, x1, y1 = box
    return im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))


def chuan_bi():
    if not GOC.is_dir():
        print('Chưa có ảnh nhân vật (kenh/nhan-vat/goc/).')
        return []
    files = sorted(f for f in GOC.iterdir() if f.suffix.lower() in IMG_EXT)
    if not files:
        print('Chưa có ảnh nhân vật.')
        return []
    out = {}
    if len(files) == 1:
        parts = [trim(p) for p in split_sheet(key_out(Image.open(files[0])))]
        if len(parts) < 2:
            parts = [trim(key_out(Image.open(files[0])))]
        for name, p in zip(NAMES, parts):
            out[name] = p
    else:
        rest = []
        for f in files:
            stem = re.sub(r'[^a-z_]', '', f.stem.lower().replace('-', '_'))
            hit = next((n for n in NAMES if n in stem or any(al in stem for al in ALIAS[n])), None)
            im = trim(key_out(Image.open(f)))
            if hit and hit not in out:
                out[hit] = im
            else:
                rest.append(im)
        for n in NAMES:
            if n not in out and rest:
                out[n] = rest.pop(0)
    DIR.mkdir(parents=True, exist_ok=True)
    for n in NAMES:
        (DIR / f'{n}.png').unlink(missing_ok=True)
    for n, im in out.items():
        if im.height > 1400:
            s = 1400 / im.height
            im = im.resize((max(1, int(im.width * s)), 1400), Image.LANCZOS)
        im.save(DIR / f'{n}.png', optimize=True)
    print('Biểu cảm: ' + ', '.join(f'{n} {out[n].size}' for n in NAMES if n in out))
    return list(out)


# ───────────────────────── vẽ vào video ─────────────────────────

def voice_env(voice, fps, total):
    """Độ to giọng đọc theo từng khung hình (0–1) để nhân vật “nói”."""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(voice), '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    n = int(math.ceil(total * fps))
    step = 16000 / fps
    env = np.zeros(n, np.float32)
    for i in range(n):
        seg = x[int(i * step):int((i + 1) * step)]
        env[i] = math.sqrt(float((seg * seg).mean())) if len(seg) else 0
    if env.max() > 0:
        env = np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
    return env


class Appearance:
    def __init__(self, img, t0, t1, W, H, ben):
        self.img, self.t0, self.t1, self.W, self.H, self.ben = img, t0, t1, W, H, ben

    def draw(self, frame, t, env):
        if not (self.t0 <= t < self.t1):
            return
        dt, rest = t - self.t0, self.t1 - t
        y_off = 0.0
        if dt < 0.3:  # nhảy lên, vượt một chút
            u = dt / 0.3
            y_off = (1 - u) ** 2 * 1.05 - 0.08 * math.sin(u * math.pi)
        if rest < 0.22:
            v = 1 - rest / 0.22
            y_off = v * v * 1.05
        talk = env * 0.035
        bob = math.sin(t * 3.1) * 0.012
        sx, sy = 1 - talk * 0.5, 1 + talk
        w, h = max(1, int(self.img.width * sx)), max(1, int(self.img.height * sy))
        im = self.img.resize((w, h), Image.BILINEAR)
        tilt = math.sin(t * 2.3) * 2.0 + talk * 40 * (1 if self.ben == 'phai' else -1)
        im = im.rotate(tilt, resample=Image.BILINEAR, expand=True)
        margin = int(self.W * 0.015)
        x = margin if self.ben == 'trai' else self.W - im.width - margin
        y = int(self.H - im.height + self.H * 0.012 + (y_off + bob) * self.img.height)
        frame.alpha_composite(im, (x, y))


def build(beats, timing, W, H, plan, cut_at, word_times):
    if plan.get('nhan_vat') is False:
        return []
    imgs = {}
    for n in NAMES:
        p = DIR / f'{n}.png'
        if p.exists():
            imgs[n] = Image.open(p).convert('RGBA')
    if not imgs:
        return []
    hh = int(H * float(plan.get('co_nhan_vat', 0.30)))
    scaled = {n: im.resize((max(1, int(im.width * hh / im.height)), hh), Image.LANCZOS) for n, im in imgs.items()}
    tmap = {t['so']: t for t in timing['y']}
    out = []
    for b in beats:
        t = tmap.get(b['so'])
        if not t:
            continue
        words = word_times(timing, b['so'])
        for a in b.get('nhan_vat') or []:
            st = t['bat_dau']
            if a.get('tu_chu'):
                c = cut_at(words, a['tu_chu'], t['bat_dau'] - 1, t['bat_dau'], t['ket_thuc'])
                st = c if c is not None else st
            name = a.get('bieu_cam', 'binh_thuong')
            img = scaled.get(name) or scaled.get('binh_thuong') or next(iter(scaled.values()))
            out.append(Appearance(img, st, min(st + float(a.get('giay', 2.4)), timing['tong']), W, H, a.get('ben', 'phai')))
    return out


def draw_all(apps, frame, t, env):
    act = [a for a in apps if a.t0 <= t < a.t1]
    if not act:
        return frame
    fr = frame.convert('RGBA')
    for a in act:
        a.draw(fr, t, env)
    return fr.convert('RGB')


if __name__ == '__main__':
    chuan_bi()
