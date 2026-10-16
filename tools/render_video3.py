# 用途：每小节独占一行的排版下渲染“滚动谱 + 蓝色播放头”视频（用 SVG 拿精确坐标，用 PNG 取像素）
import glob
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw
from PIL import ImageFont

# 谱面第 1 小节 = 歌曲鼓组进入点（实测 14.33 秒），不是 0 秒
BPM = 106.0
PHASE = 14.33
BAR = 240.0 / BPM
FPS = 60
WIDTH, HEIGHT = 1920, 1080

# 段落标记：视频左上角显示当前段落（重复段会标出「重复」）
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
    txt = open(path, encoding='utf-8').read()
    # SVG 内部坐标空间可能远大于缩放后的 PNG，这里取出比例用于换算
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


def main():
    svg_dir, pages_dir, score_json, audio, out_path = sys.argv[1:6]
    data = json.load(open(score_json, encoding='utf-8'))
    rows = []
    for path in sorted(glob.glob(os.path.join(svg_dir, '*.svg'))):
        staff, barlines, notes, vb_w = parse_svg(path)
        k = 3000.0 / vb_w  # 与 pages_dir 里统一缩放后的宽度一致
        staff = [{'x0': s['x0'] * k, 'x1': s['x1'] * k, 'y': s['y'] * k} for s in staff]
        barlines = [{'x': b['x'] * k, 'y0': b['y0'] * k, 'y1': b['y1'] * k} for b in barlines]
        notes = [(x * k, y * k) for x, y in notes]
        staff.sort(key=lambda s: s['y'])
        i = 0
        while i + 4 < len(staff):
            grp = staff[i:i + 5]
            ys = [g['y'] for g in grp]
            gaps = [ys[k + 1] - ys[k] for k in range(4)]
            if max(gaps) - min(gaps) < 6:
                top, bottom = ys[0], ys[-1]
                bl = [b['x'] for b in barlines if b['y0'] < top + 6 and b['y1'] > bottom - 6]
                inside = [n for n in notes if top - 60 <= n[1] <= bottom + 60]
                # 把该小节的符头按 x 归成“音符列”，每列对应谱上的一个十六分位置
                cols = []
                for x, y in sorted(inside, key=lambda p: p[0]):
                    if cols and abs(x - cols[-1]) <= 12:
                        continue
                    cols.append(x)
                rows.append({'page': int(re.search(r'(\d+)', os.path.basename(path)).group(1)),
                             'top': top, 'bottom': bottom,
                             'x0': min([g['x0'] for g in grp] + [n[0] for n in inside] or [0]),
                             'x1': max(bl) if bl else max([g['x1'] for g in grp]),
                             'notes': sorted(n[0] for n in inside), 'cols': cols})
                i += 5
            else:
                i += 1
    rows.sort(key=lambda r: (r['page'], r['top']))
    print('谱行数（应等于小节数 85）:', len(rows))
    pages = {}
    for name in sorted(glob.glob(os.path.join(pages_dir, '*.png'))):
        img = Image.open(name).convert('RGB')
        wk = 3000.0 / img.width
        pages[int(re.search(r'(\d+)', os.path.basename(name)).group(1))] = img.resize((3000, int(img.height * wk)), Image.LANCZOS)
    pw = list(pages.values())[0].width
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
        font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 46)
    except Exception:
        font = ImageFont.load_default()
    for i in range(total):
        t = i / float(FPS)
        bar = min(max(int((t - PHASE) / BAR), 0), len(rows) - 1)
        f = min(max((t - PHASE) / BAR - bar, 0.0), 1.0)
        row = rows[bar]
        # 播放头锚点：把小节的十六分位置映射到谱面上真实音符列的 x，保证光标落在鼓点上
        poss = sorted({e['pos'] for e in data['bars'][bar]['events']})
        cols = row['cols']
        if poss and cols:
            if len(poss) == len(cols):
                marks = list(zip(poss, cols))
            else:
                # 数量对不上时按位置比例取最近的音符列
                marks = [(p, cols[min(len(cols) - 1, int(round(p * (len(cols) - 1) / 15.0)))]) for p in poss]
            cur = f * 16.0
            k = 0
            while k + 1 < len(marks) and marks[k + 1][0] <= cur:
                k += 1
            if k + 1 < len(marks):
                p0, x0a = marks[k]
                p1, x1a = marks[k + 1]
                g = 0.0 if p1 <= p0 else min(max((cur - p0) / (p1 - p0), 0.0), 1.0)
                x = x0a + g * (x1a - x0a)
            else:
                x = marks[-1][1]
        else:
            x = row['x0'] + f * (row['x1'] - row['x0'])
        page = pages.get(row['page'], list(pages.values())[0])
        y = row['top']
        target = y - win_h * 0.4
        y_off = int(max(0, min(page.height - win_h, target)))
        frame = page.crop((0, y_off, pw, y_off + win_h)).resize((WIDTH, HEIGHT), Image.BILINEAR)
        half = int(0.05 * WIDTH)
        px = int(x * scale)
        top = int((y - y_off - 95) * scale)
        bot = int((y - y_off + 130) * scale)
        top, bot = max(0, top), min(HEIGHT, bot)
        if bot > top and 0 <= px - half and px + half <= WIDTH:
            overlay = Image.new('RGBA', (half * 2, bot - top), (110, 160, 215, 115))
            box = frame.crop((px - half, top, px + half, bot)).convert('RGBA')
            frame.paste(Image.alpha_composite(box, overlay).convert('RGB'), (px - half, top))
        # 左上角显示段落标记与当前小节号
        draw = ImageDraw.Draw(frame)
        label = section_of(bar + 1)
        draw.text((40, 30), '%s   第 %d 小节' % (label, bar + 1), fill=(60, 60, 60), font=font)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    print('完成:', out_path)


if __name__ == '__main__':
    main()
