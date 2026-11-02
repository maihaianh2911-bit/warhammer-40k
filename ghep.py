#!/usr/bin/env python3
"""Ghép Hình Theo Ý — kịch bản + giọng đọc + hình từng ý → video MP4.

Mỗi dự án là một thư mục du-an/<ten>/:
    kich-ban.txt        kịch bản (bạn dán)
    voice.mp3|wav|m4a   giọng đọc (bạn dán)
    y.json              các ý + gợi ý hình (Claude viết sau khi phân tích kịch bản)
    hinh/03.jpg         hình cho ý số 3 (03b.jpg, 03c.png… = thêm hình cho cùng ý)
    y.md                bảng ý + gợi ý hình dễ đọc (máy tạo từ y.json)
    thoi-gian.json      thời điểm từng từ / từng ý trong giọng đọc (máy tạo)
    xuat/<ten>.mp4      video (máy dựng)

Lệnh:
    python3 ghep.py moi <ten>         tạo thư mục dự án
    python3 ghep.py bang <ten>        y.json → y.md (bảng ý + gợi ý hình)
    python3 ghep.py can <ten>         căn giọng đọc → thời điểm từng ý (Whisper; không có thì ước lượng)
    python3 ghep.py kiem <ten>        ý nào đã có / còn thiếu hình
    python3 ghep.py tobia <ten>       ảnh tổng hợp: hình từng ý + lời, để soát
    python3 ghep.py dung <ten> [--nhap]   dựng video (--nhap: bản nháp 540p, nhanh)
"""
import argparse, difflib, json, math, os, re, subprocess, sys, unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / 'du-an'
IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.heic', '.avif')
AUDIO_EXT = ('.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.opus', '.mp4', '.webm')
FORMATS = {'9:16': (1080, 1920), '16:9': (1920, 1080), '1:1': (1080, 1080), '4:5': (1080, 1350)}
FONT_CANDIDATES = [
    '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf',
    '/usr/share/fonts/opentype/inter/Inter-Bold.otf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
]
MOTIONS = ['zoom-in', 'pan-right', 'zoom-out', 'pan-left', 'pan-up', 'zoom-in', 'pan-down', 'zoom-out']


# ───────────────────────── tiện ích ─────────────────────────

def die(msg):
    print('LỖI: ' + msg, file=sys.stderr)
    sys.exit(1)


def proj_dir(name):
    d = PROJECTS / name
    if not d.is_dir():
        die(f'chưa có dự án "{name}" (tạo bằng: python3 ghep.py moi {name})')
    return d


def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save_json(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_plan(d):
    p = d / 'y.json'
    if not p.exists():
        die(f'{p} chưa có — Claude cần phân tích kịch bản và viết y.json trước')
    plan = load_json(p)
    beats = plan.get('y') or []
    if not beats:
        die('y.json không có ý nào (mảng "y" rỗng)')
    for i, b in enumerate(beats, 1):
        b.setdefault('so', i)
        if not (b.get('loi') or '').strip():
            die(f'ý {b["so"]} thiếu "loi" (đoạn lời đọc của ý)')
    return plan, beats


def find_voice(d):
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in AUDIO_EXT and f.stem.lower().startswith(('voice', 'giong')):
            return f
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in AUDIO_EXT:
            return f
    return None


def audio_duration(path):
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                   '-of', 'default=nw=1:nk=1', str(path)])
    return float(out.decode().strip())


def norm(w):
    w = unicodedata.normalize('NFC', w.lower()).replace('ß', 'ss').replace('đ', 'd')
    w = ''.join(c for c in unicodedata.normalize('NFD', w) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^0-9a-z]+', '', w)


def words_of(text):
    return [w for w in re.split(r'\s+', text.strip()) if norm(w)]


def images_for(d, so):
    """Hình của ý số `so`: 3.jpg, 03.jpg, 03b.png, 03-2.jpg, y03.jpg… sắp theo tên."""
    folder = d / 'hinh'
    if not folder.is_dir():
        return []
    out = []
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in IMG_EXT:
            continue
        m = re.match(r'^(?:y|ý|y_|y-)?0*(\d+)(?:$|[^0-9])', f.stem.lower())
        if m and int(m.group(1)) == so:
            out.append(f)
    return out


def font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def open_image(path):
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGBA', im.size, (0, 0, 0, 255))
        bg.alpha_composite(im)
        im = bg
    return im.convert('RGB')


# ───────────────────────── moi / bang / kiem ─────────────────────────

def cmd_moi(a):
    d = PROJECTS / a.ten
    (d / 'hinh').mkdir(parents=True, exist_ok=True)
    kb = d / 'kich-ban.txt'
    if not kb.exists():
        kb.write_text('', encoding='utf-8')
    print(f'Đã tạo {d.relative_to(ROOT)}/ — dán kịch bản vào kich-ban.txt, giọng đọc thành voice.mp3')


def cmd_bang(a):
    d = proj_dir(a.ten)
    plan, beats = load_plan(d)
    timing = load_json(d / 'thoi-gian.json') if (d / 'thoi-gian.json').exists() else None
    tmap = {t['so']: t for t in (timing or {}).get('y', [])}
    L = [f'# {plan.get("tieu_de") or a.ten}', '']
    if plan.get('tom_tat'):
        L += [plan['tom_tat'], '']
    L += [f'Khung hình: **{plan.get("khung", "9:16")}** · {len(beats)} ý · '
          'Dán hình cho ý số N vào `hinh/` với tên `NN.jpg` (vd `03.jpg`; thêm hình cho cùng ý: `03b.jpg`).', '']
    for b in beats:
        t = tmap.get(b['so'])
        when = f' · {t["bat_dau"]:.1f}s → {t["ket_thuc"]:.1f}s ({t["ket_thuc"] - t["bat_dau"]:.1f}s)' if t else ''
        have = images_for(d, b['so'])
        L += [f'## Ý {b["so"]:02d} — {b.get("y_chinh", "")}{when}', '',
              f'> {b["loi"].strip()}', '',
              f'**Gợi ý hình:** {b.get("goi_y_hinh", "")}', '']
        if b.get('phuong_an_khac'):
            L += [f'**Phương án khác:** {b["phuong_an_khac"]}', '']
        if b.get('prompt'):
            L += ['**Prompt tạo ảnh AI:**', '', '```', b['prompt'].strip(), '```', '']
        if b.get('tu_khoa'):
            L += [f'**Từ khóa tìm ảnh:** {b["tu_khoa"]}', '']
        L += [f'**Hình đã có:** {", ".join(f.name for f in have) if have else "— chưa có"}', '']
    (d / 'y.md').write_text('\n'.join(L), encoding='utf-8')
    print(f'Đã viết {(d / "y.md").relative_to(ROOT)}')


def cmd_kiem(a):
    d = proj_dir(a.ten)
    _, beats = load_plan(d)
    missing = []
    for b in beats:
        have = images_for(d, b['so'])
        print(f'Ý {b["so"]:02d}: {", ".join(f.name for f in have) if have else "THIẾU HÌNH"}  — {b.get("y_chinh", "")}')
        if not have:
            missing.append(b['so'])
    known = {f for b in beats for f in images_for(d, b['so'])}
    stray = [f.name for f in sorted((d / 'hinh').glob('*')) if f.suffix.lower() in IMG_EXT and f not in known] \
        if (d / 'hinh').is_dir() else []
    if stray:
        print('Hình không khớp số ý nào (đổi tên thành NN.jpg): ' + ', '.join(stray))
    print(f'\nCòn thiếu {len(missing)} ý: {", ".join(map(str, missing))}' if missing else '\nĐủ hình cho mọi ý.')
    return missing


# ───────────────────────── can: căn giọng ─────────────────────────

def whisper_words(audio, prompt, lang, model_name):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device='cpu', compute_type='int8')
    best = None
    for opts in (dict(vad_filter=False, condition_on_previous_text=True, prompt=True),
                 dict(vad_filter=True, condition_on_previous_text=False, prompt=False)):
        segs, info = model.transcribe(str(audio), language=lang, word_timestamps=True, beam_size=5,
                                      initial_prompt=prompt[:800] if opts['prompt'] else None,
                                      vad_filter=opts['vad_filter'],
                                      condition_on_previous_text=opts['condition_on_previous_text'])
        words = [(w.word.strip(), float(w.start), float(w.end)) for s in segs for w in (s.words or [])]
        yield words, info.language


def silences(audio):
    """[(start, end)] các đoạn im lặng ≥ 0.18 s (ffmpeg silencedetect)."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(audio), '-af',
                        'silencedetect=noise=-35dB:d=0.18', '-f', 'null', '-'], capture_output=True, text=True)
    st, out = None, []
    for line in r.stderr.splitlines():
        m = re.search(r'silence_start: ([\d.]+)', line)
        if m:
            st = float(m.group(1))
        m = re.search(r'silence_end: ([\d.]+)', line)
        if m and st is not None:
            out.append((st, float(m.group(1))))
            st = None
    return out


def estimate_times(script_words, dur, sil):
    """Không có Whisper: chia thời gian theo số ký tự, phần nói = tổng trừ khoảng lặng đầu/cuối."""
    lead = sil[0][1] if sil and sil[0][0] < 0.05 else 0.0
    tail = sil[-1][0] if sil and sil[-1][1] > dur - 0.05 else dur
    weights = [len(norm(w)) + 1.5 + (2.5 if re.search(r'[.!?…]$', w) else 1.0 if re.search(r'[,;:]$', w) else 0)
               for w in script_words]
    total = sum(weights) or 1
    t, out = lead, []
    for w, wt in zip(script_words, weights):
        span = (tail - lead) * wt / total
        out.append([t, t + span * 0.85])
        t += span
    return out


def fill_gaps(times, dur):
    """Từ nào Whisper không khớp → nội suy giữa hai từ khớp gần nhất."""
    n = len(times)
    idx = [i for i, t in enumerate(times) if t]
    if not idx:
        return None
    for i in range(n):
        if times[i]:
            continue
        prev = max((j for j in idx if j < i), default=None)
        nxt = min((j for j in idx if j > i), default=None)
        a = times[prev][1] if prev is not None else 0.0
        b = times[nxt][0] if nxt is not None else dur
        lo = prev if prev is not None else -1
        hi = nxt if nxt is not None else n
        k = (i - lo) / (hi - lo)
        s = a + (b - a) * (k - 0.5 / (hi - lo))
        times[i] = [max(a, s), max(a, s) + max(0.05, (b - a) / (hi - lo) * 0.8)]
    return times


def snap_to_silence(t, sil, lo, hi):
    best, bd = t, 0.8
    for s, e in sil:
        mid = (s + e) / 2
        if lo < mid < hi and abs(mid - t) < bd:
            best, bd = mid, abs(mid - t)
    return best


def cmd_can(a):
    d = proj_dir(a.ten)
    plan, beats = load_plan(d)
    voice = find_voice(d)
    if not voice:
        die(f'chưa có giọng đọc trong {d.relative_to(ROOT)}/ (vd voice.mp3)')
    dur = audio_duration(voice)
    sil = silences(voice)

    script_words, owner = [], []
    for bi, b in enumerate(beats):
        for w in words_of(b['loi']):
            script_words.append(w)
            owner.append(bi)
    A = [norm(w) for w in script_words]

    times, precision, lang = None, 'uoc-luong', plan.get('ngon_ngu')
    if not a.khong_whisper:
        try:
            best_ratio = -1
            prompt = ' '.join(script_words)
            for words, detected in whisper_words(voice, prompt, lang, a.model):
                cand = [None] * len(A)
                sm = difflib.SequenceMatcher(a=A, b=[norm(w[0]) for w in words], autojunk=False)
                for blk in sm.get_matching_blocks():
                    for k in range(blk.size):
                        cand[blk.a + k] = [words[blk.b + k][1], words[blk.b + k][2]]
                ratio = sum(1 for t in cand if t) / max(1, len(A))
                print(f'Whisper ({detected}): khớp {ratio:.0%} số từ')
                if ratio > best_ratio:
                    best_ratio, times, lang = ratio, cand, detected
                if ratio >= 0.9:
                    break
            if best_ratio < 0.35:
                print('Whisper khớp quá ít → dùng ước lượng theo độ dài chữ')
                times = None
            else:
                times = fill_gaps(times, dur)
                precision = 'tung-tu' if best_ratio >= 0.8 else 'gan-dung'
        except ImportError:
            print('Chưa cài faster-whisper (pip install faster-whisper) → dùng ước lượng theo độ dài chữ')
        except Exception as e:  # mạng / model lỗi → vẫn chạy được
            print(f'Whisper lỗi ({e}) → dùng ước lượng theo độ dài chữ')
    if times is None:
        times = estimate_times(script_words, dur, sil)

    # ranh giới ý: giữa khoảng lặng trước từ đầu tiên của ý, cắt sớm ~0.12 s trước khi nói
    firsts = [owner.index(bi) for bi in range(len(beats))]
    lasts = [len(owner) - 1 - owner[::-1].index(bi) for bi in range(len(beats))]
    cuts = [0.0]
    for bi in range(1, len(beats)):
        prev_end = times[lasts[bi - 1]][1]
        start = times[firsts[bi]][0]
        cut = prev_end + (start - prev_end) * 0.6 if start > prev_end else start - 0.05
        if precision == 'uoc-luong':
            cut = snap_to_silence(cut, sil, cuts[-1] + 0.4, dur - 0.2)
        cut = min(max(cut, cuts[-1] + 0.3), dur - 0.1)
        cuts.append(cut)
    end = dur + float(plan.get('duoi_giay', 0.6))
    cuts.append(end)

    out = {'giong': voice.name, 'thoi_luong': round(dur, 3), 'tong': round(end, 3),
           'do_chinh_xac': precision, 'ngon_ngu': lang, 'y': [], 'tu': []}
    for bi, b in enumerate(beats):
        out['y'].append({'so': b['so'], 'bat_dau': round(cuts[bi], 3), 'ket_thuc': round(cuts[bi + 1], 3),
                         'noi_tu': round(times[firsts[bi]][0], 3), 'noi_den': round(times[lasts[bi]][1], 3)})
    for w, t, bi in zip(script_words, times, owner):
        out['tu'].append([w, round(t[0], 3), round(t[1], 3), beats[bi]['so']])
    save_json(d / 'thoi-gian.json', out)
    print(f'Giọng {dur:.1f}s · độ chính xác: {precision}')
    for t in out['y']:
        print(f'  Ý {t["so"]:02d}: {t["bat_dau"]:6.2f} → {t["ket_thuc"]:6.2f}  ({t["ket_thuc"] - t["bat_dau"]:.1f}s)')
    if (d / 'y.json').exists():
        cmd_bang(a)


# ───────────────────────── dựng hình ─────────────────────────

def ease(x):
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, x)))


class Clip:
    """Một hình trên màn trong [t0, t1), có chuyển động Ken Burns mượt (dưới điểm ảnh)."""

    def __init__(self, src, t0, t1, W, H, motion, fit, strength):
        self.t0, self.t1, self.W, self.H = t0, t1, W, H
        self.motion, self.strength = motion, strength
        im = open_image(src) if isinstance(src, (str, Path)) else src
        iw, ih = im.size
        ratio = (iw / ih) / (W / H)
        if fit == 'auto':
            fit = 'contain' if (ratio > 1.45 or ratio < 1 / 1.45) else 'cover'
        if fit == 'contain':
            im = self._contain(im)
            iw, ih = im.size
        zmax = 1 + strength
        scale = max(W / iw, H / ih) * zmax
        self.img = im.resize((max(W, round(iw * scale)), max(H, round(ih * scale))), Image.LANCZOS)
        self.base = max(W / iw, H / ih) / scale  # nguồn px / khung px tại zoom 1

    def _contain(self, im):
        W, H = self.W, self.H
        bg = ImageOps.fit(im, (W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(14))
        bg = bg.resize((W, H), Image.BILINEAR).point(lambda v: int(v * 0.55))
        s = min(W / im.width, H / im.height) * 0.94
        fg = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
        return bg

    def frame(self, t):
        span = max(0.001, self.t1 - self.t0)
        p = ease((t - self.t0) / span) if self.motion != 'none' else 0.0
        s = self.strength
        m = self.motion
        zoom, px, py = 1.0, 0.0, 0.0
        if m == 'zoom-in':
            zoom = 1 + s * p
        elif m == 'zoom-out':
            zoom = 1 + s * (1 - p)
        elif m in ('pan-left', 'pan-right', 'pan-up', 'pan-down'):
            zoom = 1 + s * 0.85
            k = (p - 0.5) * 2  # -1 → 1
            if m == 'pan-right':
                px = k
            elif m == 'pan-left':
                px = -k
            elif m == 'pan-down':
                py = k
            else:
                py = -k
        iw, ih = self.img.size
        sc = self.base / zoom  # nguồn px cho mỗi px khung
        vw, vh = self.W * sc, self.H * sc
        cx = iw / 2 + px * (iw - vw) / 2 * 0.95
        cy = ih / 2 + py * (ih - vh) / 2 * 0.95
        x0, y0 = cx - vw / 2, cy - vh / 2
        return self.img.transform((self.W, self.H), Image.AFFINE, (sc, 0, x0, 0, sc, y0), resample=Image.BILINEAR)


def placeholder(beat, W, H):
    im = Image.new('RGB', (W, H), (24, 26, 32))
    dr = ImageDraw.Draw(im)
    f1, f2 = font(int(W * 0.09)), font(int(W * 0.036))
    dr.text((W / 2, H * 0.30), f'Ý {beat["so"]:02d}', font=f1, fill=(240, 200, 90), anchor='mm')
    dr.text((W / 2, H * 0.37), 'CHƯA CÓ HÌNH', font=f2, fill=(200, 90, 90), anchor='mm')
    txt = beat.get('goi_y_hinh') or beat.get('y_chinh') or ''
    y = H * 0.45
    for line in wrap(dr, txt, f2, W * 0.82)[:9]:
        dr.text((W / 2, y), line, font=f2, fill=(210, 210, 215), anchor='mm')
        y += f2.size * 1.35
    return im


def wrap(dr, text, f, maxw):
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if dr.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def subtitle_chunks(words, max_words=4, max_chars=26):
    """words: [[text, start, end, so]] → [(text, start, end)] cụm 2–4 từ, ngắt ở dấu câu."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        txt = ' '.join(x[0] for x in cur)
        if re.search(r'[.!?:;,…]$', w[0]) or len(cur) >= max_words or len(txt) >= max_chars:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        start = c[0][1]
        end = chunks[i + 1][0][1] if i + 1 < len(chunks) else c[-1][2] + 0.4
        end = min(end, c[-1][2] + 0.7)
        out.append((' '.join(x[0] for x in c), start, max(end, start + 0.25)))
    return out


def render_sub(text, W, H, style):
    size = int(W * (0.062 if H > W else 0.042))
    f = font(size)
    probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    lines = wrap(probe, text, f, W * 0.86)
    lh = int(size * 1.22)
    img = Image.new('RGBA', (W, lh * len(lines) + size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    stroke = max(3, size // 9)
    for i, line in enumerate(lines):
        y = size // 2 + i * lh + lh // 2
        if style == 'hop':
            tw = dr.textlength(line, font=f)
            dr.rounded_rectangle((W / 2 - tw / 2 - size * 0.35, y - lh * 0.55, W / 2 + tw / 2 + size * 0.35, y + lh * 0.5),
                                 radius=size // 4, fill=(0, 0, 0, 170))
            dr.text((W / 2, y), line, font=f, fill=(255, 255, 255, 255), anchor='mm')
        else:
            dr.text((W / 2, y), line, font=f, fill=(255, 255, 255, 255), anchor='mm',
                    stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    return img


def build_clips(d, beats, timing, W, H, plan, allow_missing):
    tmap = {t['so']: t for t in timing['y']}
    strength = float(plan.get('do_chuyen_dong', 0.10))
    default_fit = plan.get('vua_khung', 'auto')
    clips, missing = [], []
    k = 0
    for b in beats:
        t = tmap.get(b['so'])
        if not t:
            die(f'thoi-gian.json không có ý {b["so"]} — chạy lại: python3 ghep.py can <ten>')
        imgs = images_for(d, b['so'])
        if not imgs:
            missing.append(b['so'])
            if not allow_missing:
                continue
            imgs = [placeholder(b, W, H)]
        n = len(imgs)
        seg = (t['ket_thuc'] - t['bat_dau']) / n
        mot = b.get('chuyen_dong')
        mots = mot if isinstance(mot, list) else [mot] * n
        for j, src in enumerate(imgs):
            motion = mots[j] if j < len(mots) and mots[j] else MOTIONS[k % len(MOTIONS)]
            if not isinstance(src, (str, Path)):
                motion = 'none'
            clips.append(Clip(src, t['bat_dau'] + j * seg, t['bat_dau'] + (j + 1) * seg, W, H, motion,
                              b.get('vua_khung', default_fit), strength))
            k += 1
    if missing and not allow_missing:
        die(f'còn thiếu hình cho ý: {", ".join(map(str, missing))} (dựng thử với ô trống: thêm --nhap)')
    return clips, missing


def cmd_dung(a):
    d = proj_dir(a.ten)
    plan, beats = load_plan(d)
    if not (d / 'thoi-gian.json').exists():
        cmd_can(a)
    timing = load_json(d / 'thoi-gian.json')
    voice = d / timing['giong']
    fmt = plan.get('khung', '9:16')
    W, H = FORMATS.get(fmt, FORMATS['9:16'])
    fps = int(plan.get('fps', 30))
    if a.nhap:
        W, H, fps = W // 2, H // 2, 24
    clips, missing = build_clips(d, beats, timing, W, H, plan, allow_missing=a.nhap)
    xfade = float(plan.get('chuyen_canh', 0.3))
    subs_on = plan.get('phu_de', True)
    subs = []
    if subs_on:
        style = plan.get('kieu_phu_de', 'vien')
        for text, s, e in subtitle_chunks(timing['tu']):
            subs.append((s, e, render_sub(text, W, H, style)))
    sub_y = float(plan.get('vi_tri_phu_de', 0.72))
    total = timing['tong']
    nframes = int(math.ceil(total * fps))

    out_dir = d / 'xuat'
    out_dir.mkdir(exist_ok=True)
    out = out_dir / (f'{a.ten}-nhap.mp4' if a.nhap else f'{a.ten}.mp4')
    music = next((f for f in sorted(d.glob('nhac.*')) if f.suffix.lower() in AUDIO_EXT), None)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(fps), '-i', '-', '-i', str(voice)]
    if music:
        vol = float(plan.get('am_luong_nhac', 0.12))
        cmd += ['-stream_loop', '-1', '-i', str(music), '-filter_complex',
                f'[2:a]volume={vol},afade=t=out:st={max(0, total - 2):.2f}:d=2[m];'
                f'[1:a][m]amix=inputs=2:duration=first:normalize=0[a]', '-map', '0:v', '-map', '[a]']
    else:
        cmd += ['-map', '0:v', '-map', '1:a', '-af', 'apad']
    cmd += ['-c:v', 'libx264', '-preset', 'veryfast' if a.nhap else 'medium', '-crf', '24' if a.nhap else '19',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-t', f'{total:.3f}', '-movflags', '+faststart',
            str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ci = 0
    for fi in range(nframes):
        t = fi / fps
        while ci + 1 < len(clips) and t >= clips[ci + 1].t0:
            ci += 1
        if not clips:
            frame = Image.new('RGB', (W, H))
        else:
            c = clips[ci]
            frame = c.frame(t)
            if ci > 0 and xfade > 0 and t < c.t0 + xfade:
                prev = clips[ci - 1].frame(t)
                frame = Image.blend(prev, frame, ease((t - c.t0) / xfade))
        for s, e, img in subs:
            if s <= t < e:
                frame.paste(img, (0, int(H * sub_y - img.height / 2)), img)
                break
        ff.stdin.write(frame.tobytes())
        if fi % (fps * 10) == 0:
            print(f'  {t:5.1f}s / {total:.1f}s', flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        die('ffmpeg dựng video lỗi')
    print(f'Xong: {out.relative_to(ROOT)}  ({W}x{H}, {total:.1f}s)')
    if missing:
        print(f'(bản nháp — ý chưa có hình hiện ô trống: {", ".join(map(str, missing))})')


def cmd_tobia(a):
    """Ảnh soát: mỗi ý một ô (hình + số + lời) để kiểm tra hình có khớp ý không."""
    d = proj_dir(a.ten)
    plan, beats = load_plan(d)
    fmt = plan.get('khung', '9:16')
    W, H = FORMATS.get(fmt, FORMATS['9:16'])
    tw = 300
    th = int(tw * H / W)
    cap = 120
    cols = 5 if H > W else 3
    tile_w = tw if H > W else 420
    th = int(tile_w * H / W)
    rows = math.ceil(len(beats) / cols)
    sheet = Image.new('RGB', (cols * (tile_w + 16) + 16, rows * (th + cap + 16) + 16), (18, 18, 22))
    dr = ImageDraw.Draw(sheet)
    f1, f2 = font(22), font(15)
    for i, b in enumerate(beats):
        x = 16 + (i % cols) * (tile_w + 16)
        y = 16 + (i // cols) * (th + cap + 16)
        imgs = images_for(d, b['so'])
        im = ImageOps.fit(open_image(imgs[0]), (tile_w, th), Image.LANCZOS) if imgs else placeholder(b, tile_w, th)
        sheet.paste(im, (x, y))
        extra = f' (+{len(imgs) - 1})' if len(imgs) > 1 else ''
        dr.text((x, y + th + 6), f'Ý {b["so"]:02d}{extra}', font=f1, fill=(240, 200, 90))
        ly = y + th + 34
        for line in wrap(dr, b['loi'], f2, tile_w)[:4]:
            dr.text((x, ly), line, font=f2, fill=(220, 220, 225))
            ly += 19
    (d / 'xuat').mkdir(exist_ok=True)
    out = d / 'xuat' / 'to-bia.jpg'
    sheet.save(out, quality=88)
    print(f'Đã lưu {out.relative_to(ROOT)}')


def main():
    ap = argparse.ArgumentParser(description='Ghép Hình Theo Ý')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('moi', 'bang', 'kiem', 'tobia'):
        sub.add_parser(name).add_argument('ten')
    p = sub.add_parser('can')
    p.add_argument('ten')
    p.add_argument('--model', default='small')
    p.add_argument('--khong-whisper', action='store_true', help='bỏ qua Whisper, chỉ ước lượng')
    p = sub.add_parser('dung')
    p.add_argument('ten')
    p.add_argument('--nhap', action='store_true', help='bản nháp 540p, ý thiếu hình hiện ô trống')
    p.add_argument('--model', default='small')
    p.add_argument('--khong-whisper', action='store_true')
    a = ap.parse_args()
    {'moi': cmd_moi, 'bang': cmd_bang, 'kiem': cmd_kiem, 'tobia': cmd_tobia,
     'can': cmd_can, 'dung': cmd_dung}[a.cmd](a)


if __name__ == '__main__':
    main()
