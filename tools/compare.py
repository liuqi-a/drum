# 用途：把“参考图（纸谱/PDF）的某小节”与“MuseScore 渲染图的对应小节”对齐后上下拼接，便于逐小节核对
import sys

import numpy as np
from PIL import Image, ImageDraw


def staff_rows(gray, ratio=0.5, thr=170):
    prof = (gray < thr).mean(axis=1)
    # 谱线是“细而连续”的横线：先找超过阈值的行段，只保留很薄的行段作为候选
    above = prof > ratio
    runs = []
    start = -1
    for i, v in enumerate(above):
        if v and start < 0:
            start = i
        if (not v) and start >= 0:
            runs.append((start, i - 1))
            start = -1
    if start >= 0:
        runs.append((start, len(above) - 1))
    peaks = [int((a + b) / 2) for a, b in runs if (b - a) <= 8]
    best = None
    for s in range(len(peaks)):
        grp = peaks[s:s + 5]
        if len(grp) < 5:
            continue
        gaps = np.diff(grp)
        if gaps.min() < 8 or gaps.max() > 60:
            continue
        sc = float(gaps.std())
        if best is None or sc < best[0]:
            best = (sc, list(grp))
    return None if best is None else best[1]


def barlines(gray, staff, thr=170):
    top, bottom = staff[0], staff[-1]
    sub = gray[top + 3:bottom - 3, :]
    frac = (sub < thr).mean(axis=0)
    cols = [x for x in range(gray.shape[1]) if frac[x] > 0.7]
    groups = []
    for x in cols:
        if groups and x - groups[-1][-1] <= 4:
            groups[-1].append(x)
        else:
            groups.append([x])
    out = []
    for g in groups:
        if len(g) > 10:
            continue
        cx = int(sum(g) / len(g))
        col = gray[:, cx - 1:cx + 2].min(axis=1)
        dark = np.where(col < thr)[0]
        if dark.size == 0:
            continue
        if dark.min() < top - 4 or dark.max() > bottom + 4:
            continue
        if np.diff(dark).size and np.diff(dark).max() > 6:
            continue
        out.append(cx)
    return out


def bar_index_to_span(bars, staff, width):
    # 依据小节线推算第 n 小节的左右边界（第 1 小节从谱表左端开始）
    if len(bars) >= 2:
        width_est = int(np.median(np.diff(bars)))
    else:
        width_est = width // 4
    spans = [(max(0, bars[0] - width_est), bars[0])]
    for i in range(len(bars) - 1):
        spans.append((bars[i], bars[i + 1]))
    return spans


def crop_bar(img, staff, bars, index, pad=1.8):
    gray = np.asarray(img.convert('L'))
    spans = bar_index_to_span(bars, staff, img.width)
    if index - 1 >= len(spans):
        return None
    x0, x1 = spans[index - 1]
    space = (staff[-1] - staff[0]) / 4.0
    y0 = max(0, int(staff[0] - pad * space))
    y1 = min(img.height, int(staff[-1] + pad * space))
    return img.crop((x0, y0, x1, y1))


def main():
    ref_path, ren_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    ref_bar = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    ren_bar = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    ref = Image.open(ref_path).convert('RGB')
    ren = Image.open(ren_path).convert('RGB')
    # 渲染图（整页高 dpi）先等比缩小，避免内存过大并让谱线更容易被检出
    if ren.width > 6000:
        k = 6000.0 / ren.width
        ren = ren.resize((6000, int(ren.height * k)), Image.LANCZOS)
    r_gray = np.asarray(ref.convert('L')).astype(np.int16)
    n_gray = np.asarray(ren.convert('L')).astype(np.int16)
    r_thr = float(np.median(r_gray)) - 45
    n_thr = float(np.median(n_gray)) - 45
    rs = staff_rows(r_gray, ratio=0.45, thr=r_thr)
    ns = staff_rows(n_gray, ratio=0.35, thr=n_thr)
    if rs is None or ns is None:
        print('谱线检测失败 rs=%s ns=%s' % (rs, ns))
        return
    rb = barlines(r_gray, rs, thr=r_thr)
    nb = barlines(n_gray, ns, thr=n_thr)
    print('参考图谱线', rs, '小节线', rb[:12])
    print('渲染图谱线', ns, '小节线', nb[:12])
    ref_crop = crop_bar(ref, rs, rb, ref_bar)
    ren_crop = crop_bar(ren, ns, nb, ren_bar)
    if ref_crop is None or ren_crop is None:
        print('取小节失败')
        return
    # 以参考图的谱表间距为基准，把渲染图缩放到同一尺度
    ref_space = (rs[-1] - rs[0]) / 4.0
    ren_space = (ns[-1] - ns[0]) / 4.0
    k = ref_space / ren_space
    ren_crop = ren_crop.resize((max(1, int(ren_crop.width * k)), max(1, int(ren_crop.height * k))), Image.LANCZOS)
    W = max(ref_crop.width, ren_crop.width)
    H = ref_crop.height + ren_crop.height + 30
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    canvas.paste(ref_crop, (0, 0))
    canvas.paste(ren_crop, (0, ref_crop.height + 30))
    d = ImageDraw.Draw(canvas)
    d.line([(0, ref_crop.height + 14), (W, ref_crop.height + 14)], fill=(220, 0, 0), width=2)
    d.text((4, ref_crop.height + 16), '上=参考 下=渲染', fill=(200, 0, 0))
    canvas.save(out)
    print('已保存对照图:', out, canvas.size)


if __name__ == '__main__':
    main()
