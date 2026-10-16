# 用途：把实拍纸谱整页自动拉平成「一条谱行一张图」，并检出每条谱行的小节线坐标
#   1) 逐行估计谱线高度 -> 分段插值做垂直校正，消除纸张起伏与透视
#   2) 把 5 条一组的谱线聚成「系统」，每条系统裁成独立图片
#   3) 在小节内检出贯穿谱表的竖直小节线，输出 spec.json 供逐小节读谱与切图
# 用法：python tools/flatten_page.py <页面图> <x0> <x1> <输出目录> [页号] [起始小节号列表,逗号分隔]
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image


def line_rows(gray, xa, xb, thr):
    # 用行暗度峰值找谱线：谱线很细且横向连续，符杠只在局部出现
    band = gray[:, xa:xb].astype(np.float32)
    prof = (band < thr).mean(axis=1)
    peaks = []
    for i in range(1, len(prof) - 1):
        if prof[i] > 0.45 and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]:
            if peaks and i - peaks[-1] <= 6:
                if prof[i] > prof[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
    return peaks


def pick_five(rows, gap_min=12, gap_max=34):
    # 从候选行里挑出间距最均匀的连续 5 条
    best = None
    for i in range(len(rows)):
        for j in range(i + 4, min(i + 9, len(rows))):
            grp = rows[i:j + 1]
            if len(grp) != 5:
                continue
            gaps = np.diff(grp)
            if gaps.min() >= gap_min and gaps.max() <= gap_max:
                sc = float(gaps.std())
                if best is None or sc < best[0]:
                    best = (sc, list(grp))
    return None if best is None else best[1]


def find_systems(gray, x0, x1, thr):
    # 在整页高度上用滑窗找一组组 5 线谱表，再按位置聚类成系统
    h = gray.shape[0]
    mids = []
    step = 200
    for y in range(0, h, step):
        y0, y1 = max(0, y - 40), min(h, y + step + 40)
        rows = line_rows(gray[y0:y1, :], x0, x1, thr)
        five = pick_five(rows)
        if five:
            mids.append([r + y0 for r in five])
    systems = []
    for five in mids:
        center = sum(five) / 5.0
        if systems and abs(center - systems[-1]['center']) < 60:
            systems[-1]['votes'].append(five)
        else:
            systems.append({'center': center, 'votes': [five]})
    out = []
    for s in systems:
        # 取投票里最靠近中位数的那一组，避免个别滑窗偏一点
        c = float(np.median([v[0] for v in s['votes']]))
        best = min(s['votes'], key=lambda v: abs(v[0] - c))
        out.append(best)
    return out


def flatten(color, gray, x0, x1, staff, thr):
    # 按列估计谱线整体偏移，逐列重采样，把起伏的谱行拉成水平
    top, bottom = staff[0], staff[-1]
    ytop = max(0, top - 90)
    ybot = min(gray.shape[0], bottom + 90)
    nseg = 12
    xs = np.linspace(x0 + 100, x1 - 100, nseg).astype(int)
    ref = []
    for xc in xs:
        rows = line_rows(gray[ytop:ybot, :], max(0, xc - 140), xc + 140, thr)
        five = pick_five(rows)
        ref.append(None if five is None else five[0])
    known = [(xs[i], ref[i]) for i in range(nseg) if ref[i] is not None]
    if len(known) < 3:
        return None, None
    target = float(np.median([v for _, v in known]))
    shifts = np.array([np.interp(x, [p[0] for p in known], [p[1] - target for p in known])
                       for x in range(x0, x1)], dtype=np.float32)
    crop = color[ytop:ybot, x0:x1]
    h, w = crop.shape[:2]
    map_x = np.tile(np.arange(w, dtype=np.float32), (h, 1))
    map_y = (np.arange(h, dtype=np.float32)[:, None] + shifts[None, :]).astype(np.float32)
    flat = cv2.remap(crop, map_x, map_y, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    fgray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    rows = line_rows(fgray, 0, w, paper_thr(fgray))
    five = pick_five(rows)
    return flat, five


def paper_thr(gray):
    # 以纸面亮度为基准自适应阈值，页面下部有阴影时仍能稳定二值化
    return float(np.median(gray)) - 45


def detect_bars(fgray, staff, x0, thr):
    # 小节线 = 竖直贯穿谱表的细线；用最大间隙排除符干与符杠
    top, bottom = staff[0], staff[-1]
    sub = fgray[top + 4:bottom - 3, :]
    frac = (sub < thr).mean(axis=0)
    cols = [x for x in range(fgray.shape[1]) if frac[x] > 0.72]
    groups = []
    for x in cols:
        if groups and x - groups[-1][-1] <= 5:
            groups[-1].append(x)
        else:
            groups.append([x])
    bars = []
    for g in groups:
        if len(g) > 14:
            continue
        cx = int(sum(g) / len(g))
        col = fgray[:, max(0, cx - 1):cx + 2].min(axis=1)
        dark = np.where(col < thr)[0]
        if dark.size == 0:
            continue
        if dark.min() < top - 4 or dark.max() > bottom + 4:
            continue
        gaps = np.diff(dark)
        if gaps.size and gaps.max() > 7:
            continue
        bars.append(cx)
    return bars


def main():
    page_path, x0, x1, outdir = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    page_no = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    first_bars = [int(v) for v in sys.argv[6].split(',')] if len(sys.argv) > 6 else []
    os.makedirs(outdir, exist_ok=True)
    color = cv2.imread(page_path)
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    thr = paper_thr(gray)
    systems = find_systems(gray, x0, x1, thr)
    print('第%d页 自动识别到系统 %d 个' % (page_no, len(systems)))
    spec = {'page': page_no, 'file': page_path, 'x0': x0, 'x1': x1, 'systems': []}
    for i, staff in enumerate(systems, 1):
        flat, fstaff = flatten(color, gray, x0, x1, staff, thr)
        if flat is None or fstaff is None:
            print('  系统%02d 拉平失败，跳过（原谱线 %s）' % (i, staff))
            continue
        fgray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
        fthr = paper_thr(fgray)
        bars = detect_bars(fgray, fstaff, x0, fthr)
        name = 'p%d_sys%02d.png' % (page_no, i)
        path = os.path.join(outdir, name)
        Image.fromarray(cv2.cvtColor(flat, cv2.COLOR_BGR2RGB)).save(path)
        first = first_bars[i - 1] if i - 1 < len(first_bars) else 0
        print('  系统%02d y=%s 谱线 %s 间距%.1f 小节线 %d 条 -> %s'
              % (i, [int(v) for v in staff], fstaff, (fstaff[-1] - fstaff[0]) / 4.0, len(bars), bars))
        spec['systems'].append({
            'index': i, 'page': page_no, 'file': path, 'orig': [int(v) for v in staff],
            'staff': fstaff, 'barlines': bars, 'firstBar': first,
        })
    json.dump(spec, open(os.path.join(outdir, 'spec.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('已写出 %s' % os.path.join(outdir, 'spec.json'))


if __name__ == '__main__':
    main()
