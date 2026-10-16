# 用途：批量把整页谱拉平、切分小节，输出 spec JSON（供图案聚类与逐小节读谱使用）
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image


def line_rows(gray, x0, x1, thr=170, ratio=0.5):
    band = gray[:, x0:x1]
    prof = (band < thr).mean(axis=1)
    peaks = []
    for i in range(1, len(prof) - 1):
        if prof[i] > ratio and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]:
            if peaks and i - peaks[-1] <= 5:
                if prof[i] > prof[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
    return peaks


def pick_staff(rows, gap_min=12, gap_max=34):
    best = None
    for i in range(len(rows)):
        for j in range(i + 4, min(i + 8, len(rows))):
            grp = rows[i:j + 1]
            if len(grp) != 5:
                continue
            gaps = np.diff(grp)
            if gaps.min() >= gap_min and gaps.max() <= gap_max:
                score = float(gaps.std())
                if best is None or score < best[0]:
                    best = (score, list(grp))
    return None if best is None else best[1]


def flatten(gray, color, x0, x1, band_top, band_bottom, nseg=10):
    # 分段估计谱线高度并逐列垂直偏移，消除透视与纸张起伏
    h = band_bottom - band_top
    # 自适应阈值：以该行区域的纸张亮度为基准（页面下部有阴影）
    paper = float(np.median(gray[band_top:band_bottom, x0:x1]))
    thr = paper - 45
    xs = np.linspace(x0 + 120, x1 - 120, nseg).astype(int)
    ref = []
    for xc in xs:
        rows = line_rows(gray[band_top:band_bottom + 1, :], xc - 130, xc + 130, thr=thr, ratio=0.45)
        staff = pick_staff(rows)
        ref.append(None if staff is None else staff[0])
    known = [(xs[i], ref[i]) for i in range(nseg) if ref[i] is not None]
    if len(known) < 3:
        return None, None
    target = float(np.median([v for _, v in known]))
    crop = color[band_top:band_bottom + 1, x0:x1]
    w = crop.shape[1]
    shifts = np.array([np.interp(x, [p[0] for p in known], [p[1] - target for p in known]) for x in range(x0, x1)], dtype=np.float32)
    map_x = np.tile(np.arange(w, dtype=np.float32), (h + 1, 1))
    map_y = (np.arange(h + 1, dtype=np.float32)[:, None] + shifts[None, :]).astype(np.float32)
    flat = cv2.remap(crop, map_x, map_y, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    fgray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    rows = line_rows(fgray, 0, w, thr=thr)
    staff = pick_staff(rows)
    return flat, staff


def detect_bars(fgray, staff, x0, thr=170):
    # 找“连续贯穿谱表”的细竖线作为小节线（用最大间隙来排除符干/符杠等干扰）
    top, bottom = staff[0], staff[-1]
    sub = fgray[top + 3:bottom - 3, :]
    frac = (sub < thr).mean(axis=0)
    cols = [x for x in range(fgray.shape[1]) if frac[x] > 0.7]
    groups = []
    for x in cols:
        if groups and x - groups[-1][-1] <= 4:
            groups[-1].append(x)
        else:
            groups.append([x])
    bars = []
    for g in groups:
        if len(g) > 10:
            continue
        cx = int(sum(g) / len(g))
        col = fgray[:, cx - 1:cx + 2].min(axis=1)
        dark = np.where(col < thr)[0]
        if dark.size == 0:
            continue
        if dark.min() < top - 3 or dark.max() > bottom + 3:
            continue
        gaps = np.diff(dark)
        if gaps.size and gaps.max() > 6:
            continue
        bars.append(cx + x0)
    return bars


def main():
    cfg = json.load(open(sys.argv[1], encoding='utf-8'))
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    spec = {'systems': []}
    for page in cfg['pages']:
        img = cv2.imread(page['file'])
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        for sysinfo in page['systems']:
            flat, staff = flatten(gray, img, page['x0'], page['x1'], sysinfo['y0'], sysinfo['y1'])
            if flat is None or staff is None:
                print('系统 y=%d..%d 拉平失败' % (sysinfo['y0'], sysinfo['y1']))
                continue
            fgray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
            paper = float(np.median(fgray[staff[0]:staff[-1], :]))
            barlines = detect_bars(fgray, staff, page['x0'], thr=paper - 45)
            name = 'p%d_sys%02d.png' % (page['page'], sysinfo['index'])
            path = os.path.join(outdir, name)
            Image.fromarray(cv2.cvtColor(flat, cv2.COLOR_BGR2RGB)).save(path)
            space = (staff[-1] - staff[0]) / 4.0
            print('p%d 系统%2d: 谱线 %s 间距%.1f 小节线 %s' % (page['page'], sysinfo['index'], staff, space, barlines))
            spec['systems'].append({
                'index': sysinfo['index'],
                'page': page['page'],
                'file': path,
                'staff': staff,
                'barlines': barlines,
                'firstBar': sysinfo.get('firstBar', 0),
            })
    json.dump(spec, open(os.path.join(outdir, 'spec.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写出 spec.json')


if __name__ == '__main__':
    main()
