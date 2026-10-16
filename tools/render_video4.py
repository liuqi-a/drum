# 用途：渲染“滚动谱 + 连续播放光标”视频（每行 4 小节；光标在小节内连续行进并压在鼓点上）
import glob
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BPM = 106.0
PHASE = 14.33          # 谱面第 1 小节 = 歌曲鼓组进入点（秒）
BAR = 240.0 / BPM
FPS = 60
WIDTH, HEIGHT = 1920, 1080
BARS_PER_ROW = 4
WORK_W = 3000.0

SECTIONS = [
    (1, 7, '主歌 A'),
    (8, 16, '主歌 A2'),
    (17, 27, '副歌 B'),
    (28, 32, '衔接'),
    (33, 41, '副歌 B2'),
    (42, 59, '重复（副歌）'),
    (60, 61, '过门'),
    (62, 79, '重复编排'),
]


def section_of(bar_no):
    for a, b, name in SECTIONS:
        if a <= bar_no <= b:
            return name
    return ''


def parse_svg(path):
    # 读出谱线、小节线与符头坐标（SVG 内部坐标空间）
    txt = open(path, encoding='utf-8').read()
    vb = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', txt)
    vb_w = float(vb.group(1)) if vb else 9924.0
    staff = []
    for m in re.finditer(r'<polyline class="StaffLines"[^>]*points="([^"]+)"', txt):
        pts = [tuple(float(v) for v in p.split(',')) for p in m.group(1).split()]
        staff.append({'x0': pts[0][0], 'x1': pts[-1][0], 'y': pts[0][1]})
    barlines = []
    for m in re.finditer(r'<polyline class="BarLine"[^>]*points="([^"]+)"', txt):
        pts = [tuple(float(v) for v in p.split(',')) for p in m.group(1).split()]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        barlines.append({'x': sum(xs) / len(xs), 'y0': min(ys), 'y1': max(ys)})
    notes = []
    for m in re.finditer(r'<path class="Note"[^>]*d="M([-\d.]+),([-\d.]+)', txt):
        notes.append((float(m.group(1)), float(m.group(2))))
    return staff, barlines, notes, vb_w


def build_bars(svg_dir, total_bars):
    rows = []
    for path in sorted(glob.glob(os.path.join(svg_dir, '*.svg'))):
        staff, barlines, notes, vb_w = parse_svg(path)
        k = WORK_W / vb_w
        staff = [{'x0': s['x0'] * k, 'x1': s['x1'] * k, 'y': s['y'] * k} for s in staff]
        barlines = [{'x': b['x'] * k, 'y0': b['y0'] * k, 'y1': b['y1'] * k} for b in barlines]
        notes = [(x * k, y * k) for x, y in notes]
        staff.sort(key=lambda s: s['y'])
        i = 0
        while i + 4 < len(staff):
            grp = staff[i:i + 5]
            ys = [g['y'] for g in grp]
            gaps = np.diff(ys)
            if gaps.max() - gaps.min() < 4:
                top, bottom = ys[0], ys[-1]
                bl = sorted(b['x'] for b in barlines if b['y0'] < top + 8 and b['y1'] > bottom - 8)
                inside = sorted(x for x, y in notes if top - 60 <= y <= bottom + 60)
                rows.append({'page': int(re.search(r'(\d+)', os.path.basename(path)).group(1)),
                             'top': top, 'bottom': bottom,
                             'x0': min(g['x0'] for g in grp), 'x1': max(g['x1'] for g in grp),
                             'barlines': bl, 'notes': inside})
                i += 5
            else:
                i += 1
    rows.sort(key=lambda r: (r['page'], r['top']))
    bars = []
    for ri, row in enumerate(rows):
        start = ri * BARS_PER_ROW
        if start >= total_bars:
            break
        n = min(BARS_PER_ROW, total_bars - start)
        edges = [row['x0']] + [x for x in row['barlines']]
        if len(edges) < n + 1:
            w = (row['x1'] - row['x0']) / n
            edges = [row['x0'] + t * w for t in range(n + 1)]
        edges = sorted(edges)[:n + 1]
        for j in range(n):
            bars.append({'row': row, 'xa': edges[j], 'xb': edges[j + 1]})
    return bars


def main():
    svg_dir, pages_dir, score_json, audio, out_path = sys.argv[1:6]
    data = json.load(open(score_json, encoding='utf-8'))
    total_bars = len(data['bars'])
    bars = build_bars(svg_dir, total_bars)
    print('排版：%d 小节，共 %d 行' % (len(bars), len(set(id(b["row"]) for b in bars))))
    pages = {}
    for name in sorted(glob.glob(os.path.join(pages_dir, '*.png'))):
        img = Image.open(name).convert('RGB')
        wk = WORK_W / img.width
        pages[int(re.search(r'(\d+)', os.path.basename(name)).group(1))] = img.resize((int(WORK_W), int(img.height * wk)), Image.LANCZOS)
    pw = int(WORK_W)
    scale = WIDTH / float(pw)
    win_h = int(pw * HEIGHT / float(WIDTH))
    dur = float(sys.argv[6]) if len(sys.argv) > 6 else 191.85
    total = int(dur * FPS)
    ff = subprocess.run([sys.executable, '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True).stdout.strip()
    cmd = [ff, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (WIDTH, HEIGHT),
           '-r', str(FPS), '-i', '-', '-i', audio, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 44)
    except Exception:
        font = ImageFont.load_default()
    for i in range(total):
        t = i / float(FPS)
        bi = min(max(int((t - PHASE) / BAR), 0), len(bars) - 1)
        f = min(max((t - PHASE) / BAR - bi, 0.0), 1.0)
        bar = bars[bi]
        row = bar['row']
        # 小节内的音符列 → 与十六分位置配对，形成“连续行进 + 压在鼓点上”的锚点
        cols = [x for x in row['notes'] if bar['xa'] - 18 <= x <= bar['xb'] + 18]
        poss = sorted({e['pos'] for e in data['bars'][bi]['events']})
        marks = [(0.0, bar['xa'])]
        if poss and cols:
            if len(poss) == len(cols):
                pairs = list(zip(poss, cols))
            else:
                pairs = [(p, cols[min(len(cols) - 1, int(round(p * (len(cols) - 1) / 15.0)))]) for p in poss]
            marks += [(float(p), x) for p, x in pairs]
        marks.append((16.0, bar['xb']))
        cur = f * 16.0
        k2 = 0
        while k2 + 1 < len(marks) and marks[k2 + 1][0] <= cur:
            k2 += 1
        if k2 + 1 < len(marks):
            p0, x0 = marks[k2]
            p1, x1 = marks[k2 + 1]
            g = 0.0 if p1 <= p0 else min(max((cur - p0) / (p1 - p0), 0.0), 1.0)
            x = x0 + g * (x1 - x0)
        else:
            x = marks[-1][1]
        page = pages.get(row['page'], list(pages.values())[0])
        y = row['top']
        y_off = int(max(0, min(page.height - win_h, y - win_h * 0.38)))
        frame = page.crop((0, y_off, pw, y_off + win_h)).resize((WIDTH, HEIGHT), Image.BILINEAR)
        half = int(0.035 * WIDTH)
        px = int(x * scale)
        top = int((y - y_off - 95) * scale)
        bot = int((y - y_off + 130) * scale)
        top, bot = max(0, top), min(HEIGHT, bot)
        if bot > top:
            x_lo = max(0, px - half)
            x_hi = min(WIDTH, px + half)
            if x_hi > x_lo:
                overlay = Image.new('RGBA', (x_hi - x_lo, bot - top), (110, 160, 215, 115))
                box = frame.crop((x_lo, top, x_hi, bot)).convert('RGBA')
                frame.paste(Image.alpha_composite(box, overlay).convert('RGB'), (x_lo, top))
        draw = ImageDraw.Draw(frame)
        draw.text((40, 30), '%s   第 %d 小节' % (section_of(bi + 1), bi + 1), fill=(60, 60, 60), font=font)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    print('完成:', out_path)


if __name__ == '__main__':
    main()
