# 用途：查看导出的 SVG 里各类元素的数量与样例，确认可用来定位小节线
import re
import sys


def main():
    txt = open(sys.argv[1], encoding='utf-8').read()
    if len(sys.argv) > 3:
        lo, hi = float(sys.argv[2]), float(sys.argv[3])
        for m in re.finditer(r'<polyline class="BarLine"[^>]*points="([^"]+)"', txt):
            pts = [tuple(float(v) for v in p.split(',')) for p in m.group(1).split()]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cy = (min(ys) + max(ys)) / 2
            if lo <= cy <= hi:
                print('  BarLine x=%.0f y=%.0f..%.0f' % (sum(xs) / len(xs), min(ys), max(ys)))
        return
    for cls in ('BarLine', 'Stem', 'Beam', 'StaffLines', 'MeasureNumber', 'Clef'):
        els = re.findall(r'<[a-zA-Z]+[^>]*class="%s"[^>]*>' % cls, txt)
        print('%s 元素数: %d' % (cls, len(els)))
        for e in els[:3]:
            print('   ', e[:160])


if __name__ == '__main__':
    main()
