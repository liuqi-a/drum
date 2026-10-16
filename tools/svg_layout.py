# 用途：解析 MuseScore 导出的 SVG，取出每条谱行的位置与小节线坐标（用于视频里精确摆放播放头）
import glob
import json
import os
import re
import sys


def parse_page(path):
    txt = open(path, encoding='utf-8').read()
    staff = []
    for m in re.finditer(r'<polyline class="StaffLines"[^>]*points="([^"]+)"', txt):
        pts = [tuple(float(v) for v in p.split(',')) for p in m.group(1).split()]
        if len(pts) >= 2:
            staff.append({'x0': pts[0][0], 'x1': pts[-1][0], 'y': pts[0][1]})
    bars = []
    for m in re.finditer(r'<polyline class="BarLine"[^>]*points="([^"]+)"', txt):
        pts = [tuple(float(v) for v in p.split(',')) for p in m.group(1).split()]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bars.append({'x': sum(xs) / len(xs), 'y0': min(ys), 'y1': max(ys)})
    numbers = []
    for m in re.finditer(r'<text class="MeasureNumber"[^>]*x="([-\d.]+)"[^>]*y="([-\d.]+)"[^>]*>([^<]*)</text>', txt):
        numbers.append({'x': float(m.group(1)), 'y': float(m.group(2)), 'text': m.group(3)})
    return staff, bars, numbers


def main():
    folder = sys.argv[1]
    out = sys.argv[2]
    systems = []
    for path in sorted(glob.glob(os.path.join(folder, '*.svg'))):
        staff, bars, numbers = parse_page(path)
        staff.sort(key=lambda s: s['y'])
        # 5 条一组作为一条谱行
        i = 0
        while i + 4 < len(staff):
            grp = staff[i:i + 5]
            ys = [g['y'] for g in grp]
            gaps = [ys[k + 1] - ys[k] for k in range(4)]
            if max(gaps) - min(gaps) < 6:
                top, bottom = ys[0], ys[-1]
                cand = [b['x'] for b in bars if b['y0'] < top + 6 and b['y1'] > bottom - 6]
                systems.append({'file': path, 'top': top, 'bottom': bottom,
                                'x0': grp[0]['x0'], 'x1': grp[0]['x1'], 'barlines': sorted(cand)})
                i += 5
            else:
                i += 1
    total_bars = 0
    for k, s in enumerate(systems, 1):
        bl = s['barlines']
        n = len(bl)
        total_bars += n if n else 0
        print('第%02d行 y=%.0f..%.0f x=%.0f..%.0f 小节线 %d 条 -> %s' % (
            k, s['top'], s['bottom'], s['x0'], s['x1'], n, [int(v) for v in bl[:8]]))
    print('合计谱行 %d，小节线合计 %d' % (len(systems), total_bars))
    json.dump(systems, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写出', out)


if __name__ == '__main__':
    main()
