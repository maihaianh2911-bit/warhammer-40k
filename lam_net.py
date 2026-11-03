#!/usr/bin/env python3
"""Làm nét ảnh nhỏ bằng AI (Real-ESRGAN, phóng ×4) trước khi dựng.

    python3 lam_net.py <ten>            # mọi ảnh trong du-an/<ten>/hinh/ nhỏ hơn mức cần → hinh/NN-…/.net/<tên>.jpg
    python3 lam_net.py <ten> --model general  # model nhẹ, nhanh ~10 lần, mịn hơn nhưng ít chi tiết

ghep.py tự dùng bản trong `.net/` nếu có. Cần: pip install torch (bản CPU là đủ).
Model tải một lần về ~/.cache/ghep-hinh/ (Real-ESRGAN, giấy phép BSD-3, của xinntao).
"""
import argparse, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

MODELS = {
    'general': ('realesr-general-x4v3.pth', 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth'),
    'x4plus': ('RealESRGAN_x4plus.pth', 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth'),
}
CACHE = Path.home() / '.cache' / 'ghep-hinh'


def build(kind):
    import torch
    from torch import nn
    import torch.nn.functional as F

    class SRVGG(nn.Module):  # realesr-general-x4v3
        def __init__(s, nf=64, nc=32, up=4):
            super().__init__()
            s.up = up
            body = [nn.Conv2d(3, nf, 3, 1, 1), nn.PReLU(nf)]
            for _ in range(nc):
                body += [nn.Conv2d(nf, nf, 3, 1, 1), nn.PReLU(nf)]
            body += [nn.Conv2d(nf, 3 * up * up, 3, 1, 1)]
            s.body = nn.ModuleList(body)
            s.ps = nn.PixelShuffle(up)

        def forward(s, x):
            o = x
            for m in s.body:
                o = m(o)
            return s.ps(o) + F.interpolate(x, scale_factor=s.up, mode='nearest')

    class RDB(nn.Module):
        def __init__(s, nf=64, gc=32):
            super().__init__()
            s.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
            s.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
            s.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
            s.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
            s.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)
            s.l = nn.LeakyReLU(0.2, True)

        def forward(s, x):
            x1 = s.l(s.conv1(x))
            x2 = s.l(s.conv2(torch.cat((x, x1), 1)))
            x3 = s.l(s.conv3(torch.cat((x, x1, x2), 1)))
            x4 = s.l(s.conv4(torch.cat((x, x1, x2, x3), 1)))
            return s.conv5(torch.cat((x, x1, x2, x3, x4), 1)) * 0.2 + x

    class RRDB(nn.Module):
        def __init__(s, nf=64):
            super().__init__()
            s.rdb1, s.rdb2, s.rdb3 = RDB(nf), RDB(nf), RDB(nf)

        def forward(s, x):
            return s.rdb3(s.rdb2(s.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):  # RealESRGAN_x4plus
        def __init__(s, nf=64, nb=23):
            super().__init__()
            s.conv_first = nn.Conv2d(3, nf, 3, 1, 1)
            s.body = nn.Sequential(*[RRDB(nf) for _ in range(nb)])
            s.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
            s.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1)
            s.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1)
            s.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1)
            s.conv_last = nn.Conv2d(nf, 3, 3, 1, 1)
            s.l = nn.LeakyReLU(0.2, True)

        def forward(s, x):
            f = s.conv_first(x)
            f = f + s.conv_body(s.body(f))
            f = s.l(s.conv_up1(F.interpolate(f, scale_factor=2, mode='nearest')))
            f = s.l(s.conv_up2(F.interpolate(f, scale_factor=2, mode='nearest')))
            return s.conv_last(s.l(s.conv_hr(f)))

    name, url = MODELS[kind]
    CACHE.mkdir(parents=True, exist_ok=True)
    w = CACHE / name
    if not w.exists():
        print(f'Tải model {name}…')
        urllib.request.urlretrieve(url, w)
    sd = torch.load(w, map_location='cpu', weights_only=True)
    sd = sd.get('params_ema') or sd.get('params') or sd
    net = SRVGG() if kind == 'general' else RRDBNet()
    if kind == 'general':  # khóa trong file: body.<i>.weight
        net.load_state_dict({k: v for k, v in sd.items()}, strict=True)
    else:
        net.load_state_dict(sd, strict=True)
    return net.eval()


def upscale(net, im, tile=256, pad=12):
    import numpy as np
    import torch
    a = torch.from_numpy(np.asarray(im.convert('RGB'), dtype=np.float32) / 255).permute(2, 0, 1)[None]
    _, _, h, w = a.shape
    out = torch.zeros(1, 3, h * 4, w * 4)
    with torch.inference_mode():
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                y0, x0 = max(0, y - pad), max(0, x - pad)
                y1, x1 = min(h, y + tile + pad), min(w, x + tile + pad)
                o = net(a[:, :, y0:y1, x0:x1]).clamp(0, 1)
                oy, ox = (y - y0) * 4, (x - x0) * 4
                th, tw = min(tile, h - y) * 4, min(tile, w - x) * 4
                out[:, :, y * 4:y * 4 + th, x * 4:x * 4 + tw] = o[:, :, oy:oy + th, ox:ox + tw]
    from PIL import Image
    return Image.fromarray((out[0].permute(1, 2, 0).numpy() * 255 + 0.5).astype('uint8'))


def main():
    import ghep
    ap = argparse.ArgumentParser()
    ap.add_argument('ten')
    ap.add_argument('--model', default='x4plus', choices=list(MODELS))
    ap.add_argument('--nguong', type=int, default=1400, help='làm nét ảnh có cạnh dài nhỏ hơn số này (px)')
    a = ap.parse_args()
    d = ghep.proj_dir(a.ten)
    plan, beats = ghep.load_plan(d)
    todo = []
    for b in beats:
        for f in ghep.images_for(d, b['so']):
            if ghep.is_video(f):
                continue
            dst = f.parent / '.net' / (f.stem + '.jpg')
            if dst.exists():  # (mtime không dùng được: git checkout đặt lại mọi mtime)
                continue
            im = ghep.open_image(f) if not (f.parent / '.net' / (f.stem + '.jpg')).exists() else ghep.Image.open(f).convert('RGB')
            if max(im.size) < a.nguong:
                todo.append((f, dst, im))
    if not todo:
        print('Không có ảnh nào cần làm nét.')
        return
    import torch
    torch.set_num_threads(max(1, torch.get_num_threads()))
    net = build(a.model)
    for f, dst, im in todo:
        t = time.time()
        big = upscale(net, im)
        if max(big.size) > 3200:  # đủ cho 1080×1920 kể cả khi zoom
            s = 3200 / max(big.size)
            from PIL import Image
            big = big.resize((round(big.width * s), round(big.height * s)), Image.LANCZOS)
        dst.parent.mkdir(exist_ok=True)
        big.save(dst, quality=93, subsampling=0)
        print(f'{f.parent.name}/{f.name}: {im.size} → {big.size}  ({time.time() - t:.1f}s)')


if __name__ == '__main__':
    main()
