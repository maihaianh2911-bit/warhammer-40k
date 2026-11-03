"""Biên tập: biến các ý + ảnh/video thành danh sách CẢNH (shot) rồi vẽ từng khung hình.

Mỗi ý trong y.json có thể có `canh` — danh sách cảnh do Claude biên tập sau khi xem hình:

    "canh": [
      {"tu": [0.5, 0.5, 1.0], "den": [0.5, 0.45, 1.08]},                       # cảnh đầu: bắt đầu cùng ý
      {"tu_chu": "spricht", "tu": [0.5, 0.42, 1.4], "den": [0.5, 0.4, 1.5], "vao": "giat"},
      {"tu_chu": "Nahrung", "file": 2, "vao": "flash", "rung": 0.6}
    ]

- `tu` / `den`: khung hình lúc đầu / cuối cảnh = [x, y, zoom]. x, y (0–1) là điểm nhìn trên ẢNH GỐC
  (0,0 = góc trên trái); zoom 1 = ảnh vừa lấp đầy khung, 2 = phóng gấp đôi. Máy tự giữ khung không lòi mép.
- `tu_chu`: cắt sang cảnh này ngay trước khi giọng đọc tới từ đó (lần xuất hiện đầu tiên sau cảnh trước).
  Hoặc `luc`: giây tính từ đầu ý.
- `file`: file thứ mấy trong ô của ý (1 = đầu tiên). `tu_giay`: video bắt đầu lấy từ giây nào.
- `vao`: cách vào cảnh: `cat` (cắt thẳng, mặc định) · `mo` (hòa hình) · `flash` (chớp trắng) ·
  `giat` (giật zoom) · `lia` (lia nhanh) · `toi` (từ đen ra).
- `rung`: rung máy 0–1. `vua`: `cover` (lấp đầy) / `contain` (giữ trọn ảnh trên nền mờ). `muot`: true = chậm dần.

Kiểu dựng cả video (`kieu_edit` trong y.json, đè lên `canh`):
- `lia_xen_ke`: mỗi ảnh lấp đầy khung, ảnh lẻ dịch từ trái sang phải, ảnh chẵn từ phải sang trái, đồng thời zoom
  dần vào chủ thể (video giữ nguyên, không zoom/lia). Chủ thể từng ý: `chu_the: [x, y]` (hoặc danh sách, một điểm cho mỗi file). Chỉnh:
  `zoom_dau` (1.22), `zoom_cuoi` (1.48), `do_lia` (0.16 — quãng dịch, tính theo bề ngang ảnh).

Không có `canh` → máy tự biên tập (ý dài chia 2 cảnh toàn → cận, ảnh ngang thì lia ngang, chuyển động đều).
"""
import json, math, re, subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

VID_EXT = ('.mp4', '.mov', '.webm', '.mkv', '.m4v', '.avi')


def _norm(w):
    import unicodedata
    w = unicodedata.normalize('NFD', w.lower().replace('ß', 'ss').replace('đ', 'd'))
    return re.sub(r'[^0-9a-z]+', '', ''.join(c for c in w if unicodedata.category(c) != 'Mn'))


def _is_video(p):
    return isinstance(p, Path) and p.suffix.lower() in VID_EXT


def _ease(x):
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def video_info(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height:stream_side_data=rotation:stream_tags=rotate:format=duration',
                          '-of', 'json', str(path)], capture_output=True, text=True)
    j = json.loads(out.stdout or '{}')
    st = (j.get('streams') or [{}])[0]
    w, h = int(st.get('width', 0)), int(st.get('height', 0))
    rot = 0
    for sd in st.get('side_data_list', []) or []:
        rot = int(float(sd.get('rotation', 0) or 0))
    rot = rot or int(float((st.get('tags') or {}).get('rotate', 0) or 0))
    if abs(rot) % 180 == 90:
        w, h = h, w
    return w, h, float((j.get('format') or {}).get('duration', 0) or 0)


# ───────────────────────── nguồn hình ─────────────────────────

def contain_canvas(im, W, H):
    """Ảnh giữ trọn trên nền mờ của chính nó, kích thước W×H."""
    bg = ImageOps.fit(im, (max(8, W // 6), max(8, H // 6)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6))
    bg = bg.resize((W, H), Image.BILINEAR).point(lambda v: int(v * 0.5))
    s = min(W / im.width, H / im.height)
    fg = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    return bg


class StillSource:
    """Ảnh tĩnh, phóng sẵn đủ lớn cho mức zoom lớn nhất mà các cảnh dùng."""

    def __init__(self, im, W, H, zmax, fit):
        self.orig = im.size
        if fit == 'contain':
            k = max(1.0, zmax)
            im = contain_canvas(im, round(W * k), round(H * k))
        iw, ih = im.size
        cover = max(W / iw, H / ih)
        s = cover * max(1.0, zmax)
        if abs(s - 1) > 0.01:
            im = im.resize((max(W, round(iw * s)), max(H, round(ih * s))), Image.LANCZOS)
            if s > 1.6:  # ảnh nhỏ bị phóng to nhiều → làm nét lại một chút
                im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
        self.img = im
        self.zmax = max(1.0, zmax)

    def get(self, _t):
        return self.img

    def close(self):
        pass


class VideoSource:
    """Video tắt tiếng, phóng sẵn (lấp đầy khung × zoom lớn nhất), lặp lại nếu ngắn hơn cảnh."""

    def __init__(self, path, W, H, fps, zmax, fit, tu_giay, dur):
        self.zmax = max(1.0, zmax)
        w0, h0, _ = video_info(path)
        if not w0 or not h0:
            raise ValueError(f'không đọc được video {path}')
        cw, ch = round(W * self.zmax) // 2 * 2, round(H * self.zmax) // 2 * 2
        if fit == 'contain':
            bw, bh = cw // 6 // 2 * 2, ch // 6 // 2 * 2
            vf = (f'split[a][b];[a]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},'
                  f'boxblur=6:2,scale={cw}:{ch},eq=brightness=-0.2[bg];'
                  f'[b]scale={cw}:{ch}:force_original_aspect_ratio=decrease[fg];'
                  f'[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={fps},format=rgb24')
        else:
            vf = f'scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},fps={fps},format=rgb24'
        self.size = (cw, ch)
        self.fps = fps
        self.proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-stream_loop', '-1', '-ss', f'{tu_giay:.3f}', '-i', str(path),
                                      '-t', f'{dur + 0.5:.3f}', '-an', '-filter_complex', vf, '-f', 'rawvideo', '-'],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.n = -1
        self.last = Image.new('RGB', self.size)
        self.orig = self.size

    def get(self, t_local):
        want = int(round(t_local * self.fps))
        nbytes = self.size[0] * self.size[1] * 3
        while self.n < want and self.proc:
            buf = self.proc.stdout.read(nbytes)
            if len(buf) < nbytes:
                self.close()
                break
            self.last = Image.frombytes('RGB', self.size, buf)
            self.n += 1
        return self.last

    def close(self):
        if self.proc:
            self.proc.stdout.close()
            self.proc.kill()
            self.proc.wait()
            self.proc = None


# ───────────────────────── cảnh ─────────────────────────

class Shot:
    def __init__(self, src, t0, t1, W, H, tu, den, vao='cat', rung=0.0, muot=False, so=0):
        self.src, self.t0, self.t1, self.W, self.H = src, t0, t1, W, H
        self.tu, self.den = [float(v) for v in tu], [float(v) for v in den]
        self.vao, self.rung, self.muot, self.so = vao or 'cat', float(rung or 0), bool(muot), so
        self.seed = (so * 7.13 + t0 * 3.7) % 100

    def frame(self, t):
        span = max(0.001, self.t1 - self.t0)
        p = (t - self.t0) / span
        p = _ease(p) if self.muot else min(1.0, max(0.0, p))
        (x0, y0, z0), (x1, y1, z1) = self.tu, self.den
        cx, cy = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
        z = math.exp(math.log(max(1.0, z0)) + (math.log(max(1.0, z1)) - math.log(max(1.0, z0))) * p)
        dt = t - self.t0
        if self.vao == 'giat' and dt < 0.28:
            z *= 1 + 0.16 * (1 - dt / 0.28) ** 3
        img = self.src.get(dt)
        iw, ih = img.size
        sc = self.src.zmax / z  # px nguồn cho mỗi px khung
        sc = min(sc, iw / self.W, ih / self.H)
        vw, vh = self.W * sc, self.H * sc
        px, py = cx * iw, cy * ih
        if self.rung:
            a = self.rung * self.W * 0.006
            px += sc * a * (math.sin(t * 7.3 + self.seed) + 0.6 * math.sin(t * 13.1 + self.seed * 2))
            py += sc * a * (math.cos(t * 6.1 + self.seed) + 0.6 * math.sin(t * 11.7 + self.seed * 3))
        px = min(max(px, vw / 2), iw - vw / 2)
        py = min(max(py, vh / 2), ih - vh / 2)
        return img.transform((self.W, self.H), Image.AFFINE, (sc, 0, px - vw / 2, 0, sc, py - vh / 2),
                             resample=Image.BILINEAR)

    def close(self):
        self.src.close()


def word_times(timing, so):
    return [(w[0], w[1], w[2]) for w in timing['tu'] if w[3] == so]


def cut_at(words, word, after, lo, hi):
    """Thời điểm cắt ngay trước từ `word` (lần đầu sau `after`)."""
    key = _norm(word)
    for w, s, _e in words:
        if s > after + 0.05 and (_norm(w) == key or (key and _norm(w).startswith(key))):
            return min(max(s - 0.07, lo), hi)
    return None


AUTO_MOVES = [((0.5, 0.45, 1.0), (0.5, 0.42, 1.10)),   # đẩy vào
              ((0.42, 0.45, 1.14), (0.58, 0.45, 1.14)),  # trôi phải
              ((0.5, 0.42, 1.16), (0.5, 0.45, 1.04)),   # lùi ra
              ((0.5, 0.58, 1.14), (0.5, 0.40, 1.14)),   # ngước lên
              ((0.58, 0.45, 1.14), (0.42, 0.45, 1.14))]  # trôi trái


def auto_canh(b, media, sizes, words, t0, t1, k):
    """Biên tập tự động khi y.json không có `canh`."""
    n = len(media)
    out = []
    # chia ý theo số file, cắt ở đầu từ gần nhất
    bounds = [t0]
    for j in range(1, n):
        target = t0 + (t1 - t0) * j / n
        best = min((s for _w, s, _e in words if bounds[-1] + 0.6 < s < t1 - 0.6), key=lambda s: abs(s - target), default=target)
        bounds.append(best - 0.07)
    bounds.append(t1)
    for j in range(n):
        s, e = bounds[j], bounds[j + 1]
        w, h = sizes[j]
        wide = w / max(1, h) > 1.2
        video = _is_video(media[j]) if isinstance(media[j], Path) else False
        dirn = 1 if (k + j) % 2 == 0 else -1
        if video:
            out.append(dict(luc=s - t0, file=j + 1, tu=[0.5, 0.5, 1.0], den=[0.5, 0.5, 1.05]))
        elif wide:
            low = h < 700
            fit = 'contain' if low else 'cover'
            z = 1.45 if low else 1.0
            a, c = (0.3, 0.7) if dirn > 0 else (0.7, 0.3)
            out.append(dict(luc=s - t0, file=j + 1, vua=fit, tu=[a, 0.5, z], den=[c, 0.5, z]))
        elif e - s >= 4.2:
            mid = (s + e) / 2
            cut = min((ws for _w, ws, _e in words if s + 1.6 < ws < e - 1.4), key=lambda ws: abs(ws - mid), default=None)
            mv = AUTO_MOVES[(k + j) % len(AUTO_MOVES)]
            out.append(dict(luc=s - t0, file=j + 1, tu=list(mv[0]), den=list(mv[1])))
            if cut is not None:
                zz = 1.32 if min(w, h) < 900 else 1.55
                out.append(dict(luc=cut - 0.07 - t0, file=j + 1, tu=[0.5, 0.36, zz], den=[0.5 + 0.03 * dirn, 0.35, zz * 1.06]))
        else:
            mv = AUTO_MOVES[(k + j) % len(AUTO_MOVES)]
            out.append(dict(luc=s - t0, file=j + 1, tu=list(mv[0]), den=list(mv[1]), vao='giat' if e - s < 2.3 else 'cat'))
    return out


def lia_xen_ke(b, media, words, t0, t1, plan, counter):
    """Mỗi file một cảnh lấp đầy khung; hướng dịch xen kẽ; kết thúc ở chủ thể với zoom lớn hơn."""
    n = len(media)
    z0, z1 = float(plan.get('zoom_dau', 1.22)), float(plan.get('zoom_cuoi', 1.48))
    dx = float(plan.get('do_lia', 0.16))
    ct = b.get('chu_the') or [0.5, 0.42]
    pts = ct if ct and isinstance(ct[0], (list, tuple)) else [ct] * n
    bounds = [t0]
    for j in range(1, n):
        target = t0 + (t1 - t0) * j / n
        best = min((s for _w, s, _e in words if bounds[-1] + 0.6 < s < t1 - 0.6), key=lambda s: abs(s - target), default=target)
        bounds.append(best - 0.07)
    out = []
    for j in range(n):
        if isinstance(media[j], Path) and _is_video(media[j]):  # video: giữ nguyên, không zoom/lia
            out.append(dict(luc=bounds[j] - t0, file=j + 1, vua='cover', tu=[0.5, 0.5, 1.0], den=[0.5, 0.5, 1.0]))
            continue
        sx, sy = (pts[j] if j < len(pts) else pts[-1])[:2]
        # ảnh dịch trái → phải = khung nhìn đi từ bên phải chủ thể về chủ thể (và ngược lại)
        d = 1 if counter[0] % 2 == 0 else -1
        counter[0] += 1
        out.append(dict(luc=bounds[j] - t0, file=j + 1, vua='cover',
                        tu=[sx + d * dx, sy, z0], den=[sx, sy, z1]))
    return out


def build_shots(d, beats, timing, W, H, fps, plan, images_for, open_image, placeholder, allow_missing, die):
    tmap = {t['so']: t for t in timing['y']}
    total = timing['tong']
    default_fit = plan.get('vua_khung', 'auto')
    shots, missing = [], []
    counter = [0]
    for k, b in enumerate(beats):
        t = tmap.get(b['so'])
        if not t:
            die(f'thoi-gian.json không có ý {b["so"]} — chạy lại: python3 ghep.py can <ten>')
        t0, t1 = t['bat_dau'], t['ket_thuc']
        media = images_for(d, b['so'])
        if not media:
            missing.append(b['so'])
            if not allow_missing:
                continue
            media = [placeholder(b, W, H)]
        stills, sizes = {}, []
        for m in media:
            if isinstance(m, Path) and _is_video(m):
                w, h, _ = video_info(m)
                sizes.append((w, h))
            else:
                im = open_image(m) if isinstance(m, Path) else m
                stills[id(m)] = im
                sizes.append(im.size)
        words = word_times(timing, b['so'])
        if plan.get('kieu_edit') == 'lia_xen_ke':
            canh = lia_xen_ke(b, media, words, t0, t1, plan, counter)
        else:
            canh = b.get('canh') or auto_canh(b, media, sizes, words, t0, t1, k)
        # thời điểm cắt
        starts, prev = [], t0 - 1
        for i, c in enumerate(canh):
            if i == 0:
                st = t0
            elif c.get('tu_chu'):
                st = cut_at(words, c['tu_chu'], prev, prev + 0.35, t1 - 0.3)
                if st is None:
                    print(f'  ý {b["so"]}: không thấy từ "{c["tu_chu"]}" — chia đều')
                    st = t0 + (t1 - t0) * i / len(canh)
            elif c.get('luc') is not None:
                st = t0 + float(c['luc'])
            else:
                st = t0 + (t1 - t0) * i / len(canh)
            st = max(st, prev + 0.3) if i else st
            starts.append(st)
            prev = st
        last_end = total if k == len(beats) - 1 else t1
        for i, c in enumerate(canh):
            s, e = starts[i], (starts[i + 1] if i + 1 < len(canh) else last_end)
            fi = max(1, int(c.get('file', 1))) - 1
            fi = min(fi, len(media) - 1)
            m = media[fi]
            w, h = sizes[fi]
            fit = c.get('vua') or b.get('vua_khung') or default_fit
            if fit == 'auto':
                fit = 'cover'
            tu = c.get('tu') or [0.5, 0.5, 1.0]
            den = c.get('den') or tu
            zmax = max(tu[2], den[2]) * (1.16 if c.get('vao') == 'giat' else 1.0)
            if isinstance(m, Path) and _is_video(m):
                src = VideoSource(m, W, H, fps, zmax, fit, float(c.get('tu_giay', b.get('video_tu', 0)) or 0), e - s)
            else:
                src = StillSource(stills[id(m)], W, H, zmax, fit)
            if not isinstance(m, Path):
                tu = den = [0.5, 0.5, 1.0]
            shots.append(Shot(src, s, e, W, H, tu, den, c.get('vao', 'cat'), c.get('rung', 0), c.get('muot', False), b['so']))
    return shots, missing


# ───────────────────────── vẽ khung ─────────────────────────

class Look:
    """Lớp màu chung: tương phản nhẹ, viền tối, hạt phim."""

    def __init__(self, W, H, plan):
        self.contrast = float(plan.get('tuong_phan', 1.07))
        vig = float(plan.get('vien_toi', 0.32))
        grain = float(plan.get('hat_phim', 0))  # hạt phim làm video nặng gấp chục lần — mặc định tắt
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
        self.vmask = (1 - vig * np.clip(r, 0, 1) ** 2.2)[..., None].astype(np.float32)
        rng = np.random.default_rng(7)
        self.grain = [(rng.standard_normal((H, W, 1)) * 255 * grain).astype(np.float32) for _ in range(6)] if grain > 0 else None
        self.i = 0

    def apply(self, frame):
        a = np.asarray(frame, dtype=np.float32)
        a = (a - 128) * self.contrast + 128
        a *= self.vmask
        if self.grain is not None:
            a += self.grain[self.i % len(self.grain)]
            self.i += 1
        return np.clip(a, 0, 255).astype(np.uint8)


def whip(img, amount, W):
    """Lia nhanh: dịch ngang + nhòe chuyển động."""
    a = np.asarray(img, dtype=np.float32)
    shift = int(W * 0.45 * amount)
    acc = np.zeros_like(a)
    n = 7
    for i in range(n):
        acc += np.roll(a, shift + int(i * W * 0.03 * amount), axis=1)
    return Image.fromarray(np.clip(acc / n, 0, 255).astype(np.uint8))


def compose(shots, ci, t, W, H, total, fade_out):
    c = shots[ci]
    frame = c.frame(t)
    dt = t - c.t0
    if ci > 0:
        if c.vao == 'mo' and dt < 0.35:
            frame = Image.blend(shots[ci - 1].frame(t), frame, _ease(dt / 0.35))
        elif c.vao == 'flash' and dt < 0.22:
            frame = Image.blend(frame, Image.new('RGB', (W, H), (255, 248, 235)), 0.85 * (1 - dt / 0.22) ** 2)
        elif c.vao == 'lia' and dt < 0.16:
            frame = whip(frame, (1 - dt / 0.16) ** 2, W)
        elif c.vao == 'toi' and dt < 0.3:
            frame = Image.blend(Image.new('RGB', (W, H)), frame, _ease(dt / 0.3))
    if ci + 1 < len(shots) and shots[ci + 1].vao == 'lia' and shots[ci + 1].t0 - t < 0.08:
        frame = whip(frame, -(1 - (shots[ci + 1].t0 - t) / 0.08) * 0.6, W)
    if fade_out and t > total - fade_out:
        frame = Image.blend(frame, Image.new('RGB', (W, H)), min(1.0, (t - (total - fade_out)) / fade_out))
    return frame
