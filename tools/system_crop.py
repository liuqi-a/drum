# 用途：把一条谱表系统按列做垂直偏移（分段估计谱线高度并插值），消除透视/纸张起伏，输出拉平后的整行高清图
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw


def line_rows_in_window(gray, y0, y1, x0, x1, thr=170, need=5):
    # 在一个窄窗内用行暗度峰值找谱线位置
    band = gray[y0:y1, x0:x1]
    prof = (band < thr).mean(axis=1)
    peaks = []
    for i in range(1, len(prof) - 1):
        if prof[i] > 0.5 and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]:
            if peaks and i - peaks[-1] <= 5:
                if prof[i] > prof[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
    return [p + y0 for p in peaks]


def pick_staff(rows, gap_min=10, gap_max=34):
    # 从候选行里挑出间距均匀的 5 条谱线
    best = None
    for i in range(len(rows)):
        for step in range(i + 4, len(rows)):
            grp = rows[i:step + 1]
            if len(grp) < 5:
                continue
            if len(grp) == 5:
                gaps = np.diff(grp)
                if gaps.min() >= gap_min and gaps.max() <= gap_max:
                    score = float(gaps.std())
                    if best is None or score < best[0]:
                        best = (score, list(grp))
    return None if best is None else best[1]


def main():
    page, x0, x1, ytop, ybot, out = sys.argv[1:7]
    clean = len(sys.argv) > 7 and sys.argv[7] == 'clean'
    x0, x1, ytop, ybot = int(x0), int(x1), int(ytop), int(ybot)
    img = Image.open(page).convert('RGB')
    gray = np.array(img.convert('L')).astype(np.int16)
    ytop = max(0, ytop - 80)
    ybot = min(img.height, ybot + 80)
    band = gray[ytop:ybot, :]
    # 分 10 段估计谱线整体高度
    nseg = 10
    xs = np.linspace(x0 + 120, x1 - 120, nseg).astype(int)
    ref = []
    for xc in xs:
        rows = line_rows_in_window(band, 0, ybot - ytop, xc - 130, xc + 130)
        staff = pick_staff(rows)
        ref.append(None if staff is None else staff[0])
    known = [(xs[i], ref[i]) for i in range(nseg) if ref[i] is not None]
    if len(known) < 3:
        print('谱线估计失败，已知点不足')
        return
    target = float(np.median([v for _, v in known]))
    shifts = []
    for x in range(x0, x1):
        # 线性插值出每一列需要的垂直偏移量
        shift = np.interp(x, [p[0] for p in known], [p[1] - target for p in known])
        shifts.append(shift)
    shifts = np.array(shifts, dtype=np.float32)
    crop = np.array(img.crop((x0, ytop, x1, ybot)))
    h, w = crop.shape[:2]
    map_x = np.tile(np.arange(w, dtype=np.float32), (h, 1))
    map_y = (np.arange(h, dtype=np.float32)[:, None] + shifts[None, :]).astype(np.float32)
    flat = cv2.remap(crop, map_x, map_y, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    flat_img = Image.fromarray(flat)
    fgray = np.array(flat_img.convert('L')).astype(np.int16)
    prof = (fgray < 170).mean(axis=1)
    rows = line_rows_in_window(fgray, 0, h, 0, w, need=5)
    staff = pick_staff(rows)
    draw = ImageDraw.Draw(flat_img)
    bars = []
    if staff:
        space = (staff[4] - staff[0]) / 4.0
        for r in staff:
            draw.line([(0, r - 1), (w, r - 1)], fill=(0, 170, 220), width=1)
        for pos in range(-2, 15):
            y = int(staff[4] - pos * space / 2.0)
            if 0 <= y < h:
                draw.line([(0, y), (w, y)], fill=(200, 90, 200), width=1)
                draw.text((2, max(0, y - 12)), str(pos), fill=(160, 0, 160))
        sub = fgray[staff[0] + 3:staff[-1] - 3, :]
        colfrac = (sub < 170).mean(axis=0)
        cols = [x for x in range(w) if colfrac[x] > 0.85]
        groups = []
        for x in cols:
            if groups and x - groups[-1][-1] <= 4:
                groups[-1].append(x)
            else:
                groups.append([x])
        bars = [int(sum(g) / len(g)) for g in groups]
        for cx in bars:
            draw.line([(cx, 0), (cx, h)], fill=(0, 190, 90), width=1)
        print('谱线行:', staff, ' 间距 %.1f' % space)
        print('小节线列(局部坐标, 原点 x=%d): %s' % (x0, bars))
        print('换算到原图 x:', [b + x0 for b in bars])
    big = flat_img.resize((flat_img.width * 2, flat_img.height * 2), Image.LANCZOS)
    if clean:
        # 只输出拉平后的原图，不叠加任何参考线
        Image.fromarray(flat).resize((flat.shape[1] * 2, flat.shape[0] * 2), Image.LANCZOS).save(out)
        print('已保存(无网格):', out)
        return
    big.save(out)
    print('已保存:', out, big.size)


if __name__ == '__main__':
    main()
