#!/usr/bin/env python3
"""Nối trang Xưởng Ghép Hình (artifact claude.ai) với thư mục du-an/.

Claude dùng các lệnh này cùng công cụ ArtifactData (đọc/ghi db của trang) và Artifact read (tải asset):

  python3 trang.py giai <file> <dich>
      Giải file asset base64 (giọng đọc, .mov, .heic… trang lưu dạng text) → file thật. File thường thì chép.

  python3 trang.py nhan-y <ten> <thu_muc_dump> <thu_muc_asset>
      Từ bản dump db (ArtifactData list … out_dir) của du_an/<ten>/y, xếp ảnh/video từng ý vào
      du-an/<ten>/hinh/NN-…/ (tên file gốc), xóa file trong ô mà trang đã bỏ. Asset phải tải sẵn
      vào <thu_muc_asset> (Artifact read path=<id>), tên bắt đầu bằng id.

  python3 trang.py trang-thai <ten> <gia_tri> [--video URL] [--loi-nhan "…"]
      Ghi du-an/<ten>/trang-thai.json (trang web GitHub Pages đọc file này).

  python3 trang.py day-y <ten> <thu_muc_ra>
      y.json + thoi-gian.json → mỗi ý một file JSON (để ArtifactData batch set du_an/<ten>/y/NN).
"""
import base64, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import ghep  # noqa: E402


def giai(src, dst):
    src, dst = Path(src), Path(dst)
    raw = src.read_bytes()
    head = raw[:64].strip()
    if head and re.fullmatch(rb'[A-Za-z0-9+/=\s]+', raw[:4096]):
        dst.write_bytes(base64.b64decode(raw))
    else:
        shutil.copyfile(src, dst)
    return dst


def find_asset(asset_dir, aid):
    hits = sorted(Path(asset_dir).glob(aid + '*'))
    return hits[0] if hits else None


def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|]+', '_', name).strip() or 'file'
    return name


def nhan_y(ten, dump_dir, asset_dir):
    d = ghep.proj_dir(ten)
    docs = sorted(Path(dump_dir).rglob('*.json'))
    missing = []
    for p in docs:
        j = json.loads(p.read_text(encoding='utf-8'))
        y = j.get('data', j)
        so = int(y['so'])
        slot = ghep.slot_of(d, so)
        if not slot:
            slot = d / 'hinh' / f'{so:02d}-{ghep.slug(y.get("y_chinh", ""))}'.rstrip('-')
            slot.mkdir(parents=True, exist_ok=True)
        want = []
        for i, m in enumerate(y.get('media') or []):
            src = find_asset(asset_dir, m['id'])
            name = f'{i + 1:02d}-{safe_name(m.get("ten") or m["id"])}'
            if Path(name).suffix.lower() not in ghep.MEDIA_EXT:
                ext = {'video/mp4': '.mp4', 'video/webm': '.webm', 'video/quicktime': '.mov', 'image/png': '.png',
                       'image/jpeg': '.jpg', 'image/webp': '.webp', 'image/gif': '.gif', 'image/heic': '.heic'}
                name += ext.get(m.get('type', ''), '.mp4' if m.get('kieu') == 'video' else '.jpg')
            want.append(name)
            if (slot / name).exists():
                continue
            if not src:
                missing.append(m['id'])
                continue
            if m.get('b64'):
                giai(src, slot / name)
            else:
                shutil.copyfile(src, slot / name)
            if (slot / name).suffix.lower() == '.heic':
                conv = (slot / name).with_suffix('.jpg')
                try:
                    from PIL import Image
                    import pillow_heif  # noqa: F401
                    pillow_heif.register_heif_opener()
                    Image.open(slot / name).convert('RGB').save(conv, quality=92)
                    (slot / name).unlink()
                    want[-1] = conv.name
                except Exception:
                    print(f'Không đổi được HEIC → JPG: {name} (pip install pillow-heif)')
        for f in slot.iterdir():
            if f.is_file() and f.suffix.lower() in ghep.MEDIA_EXT and f.name not in want:
                f.unlink()
        print(f'Ý {so:02d}: {len(want)} file')
    if missing:
        print('Thiếu asset (tải bằng Artifact read path=<id>): ' + ' '.join(sorted(set(missing))))
        sys.exit(2)


def day_y(ten, out_dir):
    d = ghep.proj_dir(ten)
    plan, beats = ghep.load_plan(d)
    tm = {t['so']: t for t in ghep.load_json(d / 'thoi-gian.json')['y']}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for b in beats:
        t = tm[b['so']]
        o = {k: b.get(k) for k in ('so', 'loi', 'nghia', 'y_chinh', 'goi_y_hinh', 'phuong_an_khac', 'tu_khoa', 'tu_khoa_en')}
        o.update(bat_dau=t['bat_dau'], ket_thuc=t['ket_thuc'], media=[])
        (out / f'{b["so"]:02d}.json').write_text(json.dumps(o, ensure_ascii=False), encoding='utf-8')
    print(f'{len(beats)} file trong {out}')


def trang_thai(ten, val, video=None, loi_nhan=None):
    import time
    p = ghep.proj_dir(ten) / 'trang-thai.json'
    st = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'ten': ten}
    st['trang_thai'] = val
    st['cap_nhat'] = int(time.time())
    if video is not None:
        st['video'] = {'url': video, 'ten': video.rsplit('/', 1)[-1]}
    if loi_nhan is not None:
        st['loi_nhan'] = loi_nhan
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(p)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['giai'] and len(a) == 3:
        print(giai(a[1], a[2]))
    elif a[:1] == ['nhan-y'] and len(a) == 4:
        nhan_y(a[1], a[2], a[3])
    elif a[:1] == ['trang-thai'] and len(a) >= 3:
        opt = dict(zip(a[3::2], a[4::2]))
        trang_thai(a[1], a[2], opt.get('--video'), opt.get('--loi-nhan'))
    elif a[:1] == ['day-y'] and len(a) == 3:
        day_y(a[1], a[2])
    else:
        print(__doc__)
        sys.exit(1)
