# 用途：测量指定区域内每个符头的位置（相对谱线的高度 + 横向位置），用于客观判断鼓件与节拍位置
import sys

import cv2
import numpy as np
from PIL import Image


def staff_rows(gray, y0, y1, x0, x1, thr=170):
    # 用行暗度峰值找 5 条谱线
    band = gray[y0:y1, x0:x1]
    prof = (band < thr).mean(axis=1)
    peaks = []
    for i in range(1, len(prof) - 1):
        if prof[i] > 0.55 and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]:
            if peaks and i - peaks[-1] <= 5:
                if prof[i] > prof[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
    return [p + y0 for p in peaks]


def main():
    page, x0, x1, ytop, ybot = sys.argv[1:6]
    x0, x1, ytop, ybot = int(x0), int(x1), int(ytop), int(ybot)
    gray = np.array(Image.open(page).convert('L'))
    rows = staff_rows(gray, ytop, ybot, x0, x1)
    print('谱线行:', rows)
    if len(rows) < 5:
        print('谱线不足 5 条，请调整区域')
        return
    top, bottom = rows[0], rows[-1]
    space = (bottom - top) / 4.0  # 每条线之间的间距
    # 提取符头：先二值化，再用较大的椭圆核腐蚀掉符干/符杠/谱线（它们更细）
    region = gray[max(0, ytop):ybot, x0:x1]
    mask = (region < 145).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    core = cv2.erode(mask, kernel)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(core)
    items = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 25:
            continue
        cx = cents[i][0] + x0
        cy = cents[i][1] + max(0, ytop)
        # 换算成“相对最低谱线的半格数”：4 = 最低线, 8 = 最高线, >8 在谱表上方, <4 在下方
        pos = 4 + (bottom - cy) / (space / 2.0)
        items.append((cx, cy, area, pos))
    items.sort()
    print('区域 x=%d..%d  谱线 top=%d bottom=%d 间距=%.1f' % (x0, x1, top, bottom, space))
    print('%8s %8s %8s %10s' % ('x', 'y', 'area', '半格位置'))
    for cx, cy, area, pos in items:
        print('%8.0f %8.0f %8d %10.2f' % (cx, cy, area, pos))


if __name__ == '__main__':
    main()
