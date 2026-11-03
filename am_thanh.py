"""Âm thanh: giọng đọc + nhạc nền (tự nhỏ đi khi có giọng) + hiệu ứng đặt đúng lúc chuyển cảnh → một file wav.

Tự động theo cách dựng:
  đầu video → `boom` · cảnh `lia` → `whoosh` · `giat` → `hit` + `boom` · `flash` → `reverse` (dồn vào lúc cắt) + `shimmer`
  · `mo` → `transition` nhẹ · `toi` → `boom` nhẹ · cắt thẳng sang ý mới → `whoosh` rất nhẹ.
Trong y.json (đều không bắt buộc):
  "nhac": "cinematic_suspense" | "mystery" | "horror_tension" | false   (file du-an/<ten>/nhac.* của bạn luôn được ưu tiên)
  "do_to": -9           độ to tổng (LUFS; −14 nhỏ hơn, chuẩn nền tảng) · "nhac_db": -3  độ to nhạc (cao hơn = to hơn; 0 ≈ ngang giọng) so với giọng (dB) · "sfx_db": 0  cộng/trừ cho mọi hiệu ứng
  "am_thanh": false     chỉ giữ giọng đọc
  y[].am: [{"loai": "boom", "tu_chu": "Tod", "db": -8}]   thêm hiệu ứng ở từ đó (hoặc "luc": giây tính từ đầu ý)
Loại có sẵn: whoosh, transition, boom, hit, riser, shimmer, reverse (am-thanh/thu-vien.json, đều CC0).
"""
import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = json.loads((ROOT / 'am-thanh' / 'thu-vien.json').read_text(encoding='utf-8'))
AUDIO_EXT = ('.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.opus')

# loại → độ to mặc định (dB), chỉnh theo đo thực tế: giọng ~ −18 LUFS; vút nhỏ hơn giọng ~8 LU, va/bùm ngang giọng
DB = {'whoosh': 0, 'transition': -9, 'boom': -2, 'hit': 0, 'riser': -5, 'shimmer': -11, 'reverse': -2}


def pick(loai, k):
    items = LIB['sfx'].get(loai) or []
    return items[k % len(items)] if items else None


def su_kien(shots, beats, timing, plan, cut_at, word_times):
    """[(giây đỉnh âm, loại, dB)]"""
    ev = [(0.0, 'boom', 0)]
    prev_so = shots[0].so if shots else None
    for s in shots[1:]:
        t = s.t0
        new_idea = s.so != prev_so
        prev_so = s.so
        v = s.vao
        if v == 'lia':
            ev.append((t, 'whoosh', DB['whoosh']))
        elif v == 'giat':
            ev += [(t, 'hit', DB['hit']), (t, 'boom', DB['boom'] - 2)]
        elif v == 'flash':
            ev += [(t, 'reverse', DB['reverse']), (t + 0.05, 'shimmer', DB['shimmer'])]
        elif v == 'mo':
            ev.append((t, 'transition', DB['transition'] - 4))
        elif v == 'toi':
            ev.append((t, 'boom', DB['boom'] - 4))
        elif new_idea:
            ev.append((t, 'whoosh', DB['whoosh'] - 6))
    tmap = {t['so']: t for t in timing['y']}
    for b in beats:
        t0 = tmap.get(b['so'], {}).get('bat_dau', 0)
        words = word_times(timing, b['so'])
        for a in b.get('am') or []:
            if a.get('tu_chu'):
                t = cut_at(words, a['tu_chu'], t0 - 1, t0, 1e9)
                if t is None:
                    continue
                t += 0.07
            else:
                t = t0 + float(a.get('luc', 0))
            loai = a.get('loai', 'boom')
            ev.append((t, loai, float(a.get('db', DB.get(loai, -12)))))
    return sorted(ev)


def tron(d, voice, total, events, plan, out):
    """Trộn ra out (wav 48 kHz stereo). Độ to `do_to` (mặc định −9 LUFS, đỉnh sát 0 dB; −14 = chuẩn nền tảng)."""
    if plan.get('am_thanh') is False:
        events = []
    nhac = None
    if plan.get('am_thanh') is not False and plan.get('nhac') is not False:
        nhac = next((f for f in sorted(d.glob('nhac.*')) if f.suffix.lower() in AUDIO_EXT), None)
        if not nhac:
            mood = plan.get('nhac') if isinstance(plan.get('nhac'), str) else 'cinematic_suspense'
            files = LIB['nhac'].get(mood) or LIB['nhac'].get('cinematic_suspense') or []
            nhac = ROOT / files[0] if files else None
    sfx_db = float(plan.get('sfx_db', 0))
    inputs, chains, labels = ['-i', str(voice)], [], []
    fmt = 'aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo'
    chains.append(f'[0:a]{fmt},apad,atrim=0:{total:.3f},asplit=2[v][vsc]')
    labels.append('[v]')
    n = 1
    if nhac:
        inputs += ['-stream_loop', '-1', '-i', str(nhac)]
        ndb = float(plan.get('nhac_db', -3))  # −3 → nhạc nằm ~6 LU dưới giọng (đo trên imperator-tot); −15 cũ = 29 LU, không nghe thấy
        chains.append(f'[{n}:a]{fmt},atrim=0:{total:.3f},volume={ndb}dB,afade=t=in:d=1.2,'
                      f'afade=t=out:st={max(0, total - 2.5):.2f}:d=2.5[m0];'
                      f'[m0][vsc]sidechaincompress=threshold=0.08:ratio=2.5:attack=20:release=450[m]')
        labels.append('[m]')
        n += 1
    else:
        chains.append('[vsc]anullsink')
    used = {}
    for t, loai, db in events:
        k = used.get(loai, 0)
        used[loai] = k + 1
        it = pick(loai, k)
        if not it:
            continue
        start = t - (it['peak'] if loai not in ('reverse', 'riser') else it['dur'] - 0.03)
        trim = max(0.0, -start)
        start = max(0.0, start)
        if start >= total:
            continue
        inputs += ['-i', str(ROOT / it['file'])]
        ms = int(start * 1000)
        chains.append(f'[{n}:a]{fmt},atrim=start={trim:.3f},asetpts=PTS-STARTPTS,volume={db + sfx_db}dB,'
                      f'adelay={ms}|{ms}[s{n}]')
        labels.append(f'[s{n}]')
        n += 1
    chains.append(f'{"".join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first,'
                  f'atrim=0:{total:.3f},loudnorm=I={float(plan.get("do_to", -9))}:TP=-0.5:LRA=9,'
                  f'alimiter=limit=0.97:attack=3:release=60:level=false[out]')
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(chains), '-map', '[out]',
           '-ar', '48000', '-ac', '2', str(out)]
    subprocess.run(cmd, check=True)
    return {'nhac': str(nhac.relative_to(ROOT)) if nhac and nhac.is_relative_to(ROOT) else (str(nhac) if nhac else None),
            'hieu_ung': len(labels) - 1 - (1 if nhac else 0)}
