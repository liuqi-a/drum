# 用途：在拉平后的谱行图上分析符干（竖直墨迹段），给出每个音的横向位置、符干方向与符头所在高度
import sys

import numpy as np
from PIL import Image


def ink_runs(column, y0, y1, thr=160):
    dark = [y for y in range(y0, y1) if column[y] < thr]
    runs = []
    for y in dark:
        if runs and y - runs[-1][-1] <= 3:
            runs[-1].append(y)
        else:
            runs.append([y])
    return [(r[0], r[-1]) for r in runs]


def main():
    img = sys.argv[1]
    x0, x1 = int(sys.argv[2]), int(sys.argv[3])
    a = np.array(Image.open(img).convert('L'))
    # 谱线行由调用者给定（2x 坐标）
    staff = [int(v) for v in sys.argv[4:9]]
    top, bottom = staff[0], staff[-1]
    half = (bottom - top) / 8.0
    print('谱线:', staff, '半格=%.1fpx' % half)
    cand = []
    for x in range(x0, x1):
        col = a[:, x]
        for (ra, rb) in ink_runs(col, top - 120, bottom + 120):
            if rb - ra >= 2.2 * half:
                cand.append((x, ra, rb))
                break
    # 把相邻列合并成一根符干
    stems = []
    for x, ra, rb in cand:
        if stems and x - stems[-1]['x'][-1] <= 2:
            stems[-1]['x'].append(x)
            stems[-1]['ra'].append(ra)
            stems[-1]['rb'].append(rb)
        else:
            stems.append({'x': [x], 'ra': [ra], 'rb': [rb]})
    print('%6s %6s %6s %8s %8s %s' % ('x', '上端', '下端', '长度', '符头位置', '方向'))
    for s in stems:
        cx = sum(s['x']) // len(s['x'])
        ra = int(np.median(s['ra']))
        rb = int(np.median(s['rb']))
        length = rb - ra
        # 符头在符干较短的一端：此处用“离谱表中心较远的一端”近似
        if abs(ra - (top + bottom) / 2) > abs(rb - (top + bottom) / 2):
            head_y, direction = ra, '向下(符头在上)'
        else:
            head_y, direction = rb, '向上(符头在下)'
        pos = (bottom - head_y) / half
        print('%6d %6d %6d %8d %8.2f %s' % (cx, ra, rb, length, pos, direction))


if __name__ == '__main__':
    main()
