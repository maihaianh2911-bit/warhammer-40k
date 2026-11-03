#!/usr/bin/env python3
"""Ghép Hình Theo Ý — kịch bản + giọng đọc + hình từng ý → video MP4.

Mỗi dự án là một thư mục du-an/<ten>/:
    kich-ban.txt        kịch bản (bạn dán)
    voice.mp3|wav|m4a   giọng đọc (bạn dán)
    y.json              các ý + gợi ý hình (Claude viết sau khi phân tích kịch bản)
    hinh/03-<ten-y>/    ô dán cho ý số 3: ảnh hoặc video, bao nhiêu file cũng được (chạy theo thứ tự tên);
                        README.md trong ô ghi lời, nghĩa, gợi ý hình của ý đó (máy tạo từ y.json)
    y.md                bảng tất cả ý + gợi ý hình (máy tạo từ y.json)
    thoi-gian.json      thời điểm từng từ / từng ý trong giọng đọc (máy tạo)
    xuat/<ten>.mp4      video (máy dựng)

Lệnh:
    python3 ghep.py moi <ten>         tạo thư mục dự án
    python3 ghep.py bang <ten>        y.json → y.md + ô dán hinh/NN-<ten-y>/ cho từng ý
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
IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.heic', '.avif', '.jfif')
VID_EXT = ('.mp4', '.mov', '.webm', '.mkv', '.m4v', '.avi')
MEDIA_EXT = IMG_EXT + VID_EXT
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


def num_of(name):
    m = re.match(r'^(?:y|ý|y_|y-)?0*(\d+)(?:$|[^0-9])', name.lower())
    return int(m.group(1)) if m else None


def slot_of(d, so):
    """Ô dán của ý số `so`: thư mục hinh/NN-… (None nếu chưa có)."""
    folder = d / 'hinh'
    if folder.is_dir():
        for f in sorted(folder.iterdir()):
            if f.is_dir() and num_of(f.name) == so:
                return f
    return None


def images_for(d, so):
    """Ảnh/video của ý số `so`: mọi file trong ô hinh/NN-…/ (sắp theo tên), cộng file rời hinh/03.jpg, 03b.mp4…"""
    folder = d / 'hinh'
    if not folder.is_dir():
        return []
    out = []
    slot = slot_of(d, so)
    if slot:
        out += [f for f in sorted(slot.iterdir(), key=lambda f: f.name.lower())
                if f.is_file() and f.suffix.lower() in MEDIA_EXT]
    for f in sorted(folder.iterdir()):
        if f.is_file() and f.suffix.lower() in MEDIA_EXT and num_of(f.stem) == so:
            out.append(f)
    return out


def is_video(p):
    return isinstance(p, Path) and p.suffix.lower() in VID_EXT


def slug(text):
    t = unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')[:40].strip('-')


def font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def open_image(path):
    if str(path).lower().endswith(('.heic', '.heif')):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            die(f'{path}: cần pip install pillow-heif để đọc ảnh HEIC của iPhone')
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
          'Mỗi ý có một **ô dán** (thư mục trong `hinh/`): bấm vào ô → **Add file → Upload files** → '
          'kéo ảnh/video vào → **Commit changes**.', '']
    for b in beats:
        t = tmap.get(b['so'])
        dur = f'{t["ket_thuc"] - t["bat_dau"]:.1f} giây' if t else ''
        when = f'{t["bat_dau"]:.1f}s → {t["ket_thuc"]:.1f}s ({dur})' if t else ''
        slot = slot_of(d, b['so'])
        if not slot:
            slot = d / 'hinh' / (f'{b["so"]:02d}-{slug(b.get("y_chinh", ""))}'.rstrip('-'))
            slot.mkdir(parents=True, exist_ok=True)
        have = images_for(d, b['so'])
        block = [f'> {b["loi"].strip()}', '']
        if b.get('nghia'):
            block += [f'**Nghĩa:** {b["nghia"]}', '']
        block += [f'**Gợi ý hình:** {b.get("goi_y_hinh", "")}', '']
        if b.get('phuong_an_khac'):
            block += [f'**Phương án khác:** {b["phuong_an_khac"]}', '']
        if b.get('tu_khoa'):
            block += [f'**Từ khóa tìm:** {b["tu_khoa"]}', '']
        if b.get('tu_khoa_en'):
            block += [f'**Tìm bằng tiếng Anh (nhiều kết quả hơn):** {b["tu_khoa_en"]}', '']
        have_txt = ', '.join(f.name for f in have) if have else '— chưa có'
        L += [f'## Ý {b["so"]:02d} — {b.get("y_chinh", "")}', '',
              f'{when} · [**→ Ô dán ý {b["so"]:02d}**](hinh/{slot.name}/)', ''] + block + \
             [f'**Đã dán:** {have_txt}', '']
        R = [f'# Ý {b["so"]:02d} — {b.get("y_chinh", "")}', '',
             f'**Dán ảnh / video cho ý này vào đây:** bấm **Add file → Upload files** (góc phải, ngay trong thư mục này) '
             f'→ kéo file vào → **Commit changes**.', '',
             f'Ý dài **{dur}**' + (f' (từ giây {t["bat_dau"]:.1f} đến {t["ket_thuc"]:.1f})' if t else '') + '. Nhiều file → chạy lần lượt theo tên file (chia đều thời gian). '
             'Video: lấy từ đầu clip, tắt tiếng; clip ngắn hơn ý thì lặp lại.', ''] + block + \
            [f'**Đã dán:** {have_txt}', '']
        (slot / 'README.md').write_text('\n'.join(R), encoding='utf-8')
    (d / 'y.md').write_text('\n'.join(L), encoding='utf-8')
    print(f'Đã viết {(d / "y.md").relative_to(ROOT)} + ô dán cho {len(beats)} ý trong hinh/')


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
    stray = [str(f.relative_to(d / 'hinh')) for f in sorted((d / 'hinh').rglob('*'))
             if f.is_file() and f.suffix.lower() in MEDIA_EXT and f not in known] if (d / 'hinh').is_dir() else []
    if stray:
        print('File không thuộc ô dán của ý nào: ' + ', '.join(stray))
    print(f'\nCòn thiếu {len(missing)} ý: {", ".join(map(str, missing))}' if missing else '\nĐủ hình cho mọi ý.')
    if (d / 'y.json').exists():
        cmd_bang(a)
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
    import bien_tap
    clips, missing = bien_tap.build_shots(d, beats, timing, W, H, fps, plan, images_for, open_image, placeholder,
                                          a.nhap or a.cho_phep_thieu, die)
    look = bien_tap.Look(W, H, plan)
    fade_out = float(plan.get('mo_cuoi', 0.7))
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
    cap = []
    if a.toi_da_mb:
        kbps = int(a.toi_da_mb * 8 * 1024 * 0.9 / total) - 192
        cap = ['-maxrate', f'{max(kbps, 300)}k', '-bufsize', f'{max(kbps, 300) * 2}k']
    cmd += ['-c:v', 'libx264', '-preset', 'veryfast' if a.nhap else 'medium', '-crf', '24' if a.nhap else '19', *cap,
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-t', f'{total:.3f}', '-movflags', '+faststart',
            str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ci = 0
    for fi in range(nframes):
        t = fi / fps
        while ci + 1 < len(clips) and t >= clips[ci + 1].t0:
            if ci > 0:
                clips[ci - 1].close()
            ci += 1
        frame = bien_tap.compose(clips, ci, t, W, H, total, fade_out) if clips else Image.new('RGB', (W, H))
        frame = Image.fromarray(look.apply(frame))
        for s, e, img in subs:
            if s <= t < e:
                frame.paste(img, (0, int(H * sub_y - img.height / 2)), img)
                break
        ff.stdin.write(frame.tobytes())
        if fi % (fps * 10) == 0:
            print(f'  {t:5.1f}s / {total:.1f}s', flush=True)
    ff.stdin.close()
    for c in clips:
        c.close()
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
        if not imgs:
            im = placeholder(b, tile_w, th)
        elif is_video(imgs[0]):
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '0.5', '-i', str(imgs[0]), '-frames:v', '1',
                                  '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
            im = Image.open(__import__('io').BytesIO(raw)).convert('RGB') if raw else placeholder(b, tile_w, th)
            im = ImageOps.fit(im, (tile_w, th), Image.LANCZOS)
            ImageDraw.Draw(im).text((10, 8), '▶ VIDEO', font=font(18), fill=(255, 255, 255))
        else:
            im = ImageOps.fit(open_image(imgs[0]), (tile_w, th), Image.LANCZOS)
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
    p.add_argument('--cho-phep-thieu', action='store_true', help='ý thiếu hình hiện ô gợi ý thay vì báo lỗi')
    p.add_argument('--toi-da-mb', type=float, default=0, help='giới hạn dung lượng MP4 (vd 19 để tải lên trang)')
    p.add_argument('--model', default='small')
    p.add_argument('--khong-whisper', action='store_true')
    a = ap.parse_args()
    {'moi': cmd_moi, 'bang': cmd_bang, 'kiem': cmd_kiem, 'tobia': cmd_tobia,
     'can': cmd_can, 'dung': cmd_dung}[a.cmd](a)


if __name__ == '__main__':
    main()
