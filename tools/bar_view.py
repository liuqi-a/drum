# 用途：对谱页中的指定区域做局部拉平（消除纸张倾斜与弧度），标出五线谱线与小节线并放大输出，便于逐小节读谱
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw


def first_strong_peak(prof, thr):
    # 从上往下找第一个显著峰，作为某根谱线的位置
    for i in range(1, len(prof) - 1):
        if prof[i] > thr and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]:
            return i
    return None


def estimate_angle(arr, y0, y1, x0, x1, win=70):
    # 用左右两个窗口里同一条谱线的高度差估算局部倾斜角
    def top_line(xc):
        prof = (arr[y0:y1, xc - win:xc + win] < 170).mean(axis=1)
        i = first_strong_peak(prof, 0.5)
        return None if i is None else y0 + i
    yl = top_line(x0 + win)
    yr = top_line(x1 - win)
    if yl is None or yr is None:
        return 0.0
    slope = (yr - yl) / float((x1 - win) - (x0 + win))
    return float(np.degrees(np.arctan(slope)))


def find_staff_rows(prof, thr=0.55):
    # 在一段行暗度曲线里找出 5 条谱线（峰值）的位置
    peaks = []
    for i in range(1, len(prof) - 1):
        if prof[i] > thr and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]:
            if peaks and i - peaks[-1] <= 5:
                if prof[i] > prof[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
    return peaks


def find_heads(gray, rows, top_pad=0):
    # 用形态学腐蚀去掉符干/符杠/谱线，剩下符头的“芯”，得到每个音的横纵位置
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    mask = (gray < 145).astype(np.uint8) * 255
    core = cv2.erode(mask, kernel)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(core)
    heads = []
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < 25:
            continue
        heads.append((float(cents[i][0]), float(cents[i][1]), area))
    heads.sort()
    return heads


def main():
    page, x0, x1, ytop, ybot, out = sys.argv[1:7]
    x0, x1, ytop, ybot = int(x0), int(x1), int(ytop), int(ybot)
    img = Image.open(page).convert('RGB')
    arr = np.array(img.convert('L')).astype(np.int16)
    pad = 40
    lx = max(0, x0 - pad)
    ty = max(0, ytop - 70)
    rx = min(img.width, x1 + pad)
    by = min(img.height, ybot + 70)
    angle = estimate_angle(arr, ty, by, lx, rx)
    crop = img.crop((lx, ty, rx, by)).rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    carr = np.array(crop.convert('L')).astype(np.int16)
    prof = (carr < 170).mean(axis=1)
    rows = find_staff_rows(prof)
    staff = []
    if len(rows) >= 5:
        best = None
        for start in range(0, len(rows) - 4):
            grp = rows[start:start + 5]
            gaps = np.diff(grp)
            if gaps.min() < 8 or gaps.max() > 40:
                continue
            score = float(gaps.std())
            if best is None or score < best[0]:
                best = (score, grp)
        if best:
            staff = list(best[1])
    draw = ImageDraw.Draw(crop)
    for r in staff:
        draw.line([(0, r - 1), (crop.width, r - 1)], fill=(0, 170, 220), width=1)
    if len(staff) == 5:
        # 画“半格”参考网格：0=最低谱线，8=最高谱线，9 及以上在谱表上方，负数在下方
        space = (staff[4] - staff[0]) / 4.0
        for pos in range(-2, 15):
            y = int(staff[4] - pos * space / 2.0)
            if 0 <= y < crop.height:
                draw.line([(0, y), (crop.width, y)], fill=(200, 90, 200), width=1)
                draw.text((2, y - 12), str(pos), fill=(160, 0, 160))
    group_centers = []
    if staff:
        band = carr[staff[0] + 2:staff[-1] - 2, :]
        colfrac = (band < 170).mean(axis=0)
        cols = [x for x in range(crop.width) if colfrac[x] > 0.85]
        groups = []
        for x in cols:
            if groups and x - groups[-1][-1] <= 3:
                groups[-1].append(x)
            else:
                groups.append([x])
        group_centers = [int(sum(g) / len(g)) for g in groups]
        for cx in group_centers:
            draw.line([(cx, 0), (cx, crop.height)], fill=(0, 190, 90), width=2)
        print('谱线行:', staff)
        print('小节线列:', group_centers)
    print('局部倾斜角: %.2f 度' % angle)
    if len(staff) == 5:
        space = (staff[4] - staff[0]) / 4.0
        gray = np.array(crop.convert('L'))
        heads = find_heads(gray, staff)
        print('%4s %7s %7s %7s %9s' % ('#', 'x', 'y', 'area', '半格位置'))
        for idx, (hx, hy, area) in enumerate(heads, 1):
            pos = (staff[4] - hy) / (space / 2.0)
            print('%4d %7.0f %7.0f %7d %9.2f' % (idx, hx, hy, area, pos))
            draw.ellipse([hx - 5, hy - 5, hx + 5, hy + 5], outline=(255, 0, 0), width=2)
            draw.text((hx + 6, hy - 26), str(idx), fill=(220, 0, 0))
    big = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
    big.save(out)
    print('已保存:', out)


if __name__ == '__main__':
    main()
