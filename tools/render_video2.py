# 用途：用 SVG 里 Note 的坐标作为锚点，渲染“滚动谱 + 蓝色播放头”视频并与原曲音频合成
import glob
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

BPM = 106.0
PHASE = 0.044
BAR = 240.0 / BPM
STEP = BAR / 16.0
FPS = 60
WIDTH, HEIGHT = 1920, 1080


def parse_svg(path):
    txt = open(path, encoding='utf-8').read()
    staff = []
    for m in re.finditer(r'<polyline class="StaffLines"[^>]*points="([^"]+)"', txt):
        pts = [tuple(float(v) for v in p.split(',')) for p in m.group(1).split()]
        staff.append({'x0': pts[0][0], 'x1': pts[-1][0], 'y': pts[0][1]})
    notes = []
    for m in re.finditer(r'<path class="Note"[^>]*d="M([-\d.]+),([-\d.]+)', txt):
        notes.append((float(m.group(1)), float(m.group(2))))
    return staff, notes


def note_groups(notes, eps_x=14.0):
    # 同一时刻的和弦会画在相近的 x 上，这里按 x 归组（x 已按时间递增）
    notes.sort(key=lambda p: (round(p[0]), p[1]))
    groups = []
    for x, y in notes:
        if groups and abs(x - groups[-1][-1][0]) <= eps_x:
            groups[-1].append((x, y))
        else:
            groups.append([(x, y)])
    return [{'x': sum(p[0] for p in g) / len(g), 'y': sum(p[1] for p in g) / len(g)} for g in groups]


def main():
    svg_dir, pages_dir, score_json, audio, out_path = sys.argv[1:6]
    data = json.load(open(score_json, encoding='utf-8'))
    # 乐谱里所有“有音的时间点”，按时间排序
    times = []
    for bi, bar in enumerate(data['bars']):
        poss = sorted({e['pos'] for e in bar['events']})
        for p in poss:
            times.append((bi + 1 - 1) * BAR + p * STEP + PHASE)
        if not poss:
            times.append((bi) * BAR + PHASE)
    anchors = []
    for path in sorted(glob.glob(os.path.join(svg_dir, '*.svg'))):
        staff, notes = parse_svg(path)
        groups = note_groups(notes)
        # 谱行按 y 排序，用于滚动定位
        staff.sort(key=lambda s: s['y'])
        page_no = int(re.search(r'(\d+)', os.path.basename(path)).group(1))
        for g in groups:
            # 找到该音所在的谱行
            row = None
            for s in staff:
                if s['y'] - 40 <= g['y'] <= s['y'] + 400:
                    if row is None or abs(s['y'] - g['y']) < abs(row['y'] - g['y']):
                        row = s
            g['page'] = page_no
            g['staff_y'] = row['y'] if row else g['y']
        anchors.extend(groups)
    print('谱面里识别到的音组数: %d, 乐谱数据里的时间点数: %d' % (len(anchors), len(times)))
    n = min(len(anchors), len(times))
    mapping = [(times[i], anchors[i]['x'], anchors[i]['staff_y'], anchors[i]['page']) for i in range(n)]
    pages = {}
    for i, name in enumerate(sorted(glob.glob(os.path.join(pages_dir, '*.png'))), 1):
        img = Image.open(name).convert('RGB')
        wk = 3000.0 / img.width
        pages[i] = img.resize((3000, int(img.height * wk)), Image.LANCZOS)
    pw = pages[1].width
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
    k = 0
    for i in range(total):
        t = i / float(FPS)
        while k + 1 < len(mapping) and mapping[k + 1][0] <= t:
            k += 1
        t0, x0, y0, p0 = mapping[k]
        if k + 1 < len(mapping):
            t1, x1, y1, p1 = mapping[k + 1]
            f = 0.0 if t1 <= t0 else min(max((t - t0) / (t1 - t0), 0.0), 1.0)
        else:
            t1, x1, y1, p1 = t0, x0, y0, p0
            f = 1.0
        page_no = p0 if f < 0.5 else p1
        x = x0 + f * (x1 - x0)
        y = y0 + f * (y1 - y0)
        page = pages.get(page_no, pages[1])
        target = y - win_h * 0.35
        y_off = int(max(0, min(page.height - win_h, target)))
        frame = page.crop((0, y_off, pw, y_off + win_h)).resize((WIDTH, HEIGHT), Image.BILINEAR)
        half = int(0.05 * WIDTH)
        px = int(x * scale)
        top = int((y - y_off - 90) * scale)
        bot = int((y - y_off + 120) * scale)
        top, bot = max(0, top), min(HEIGHT, bot)
        if bot > top:
            overlay = Image.new('RGBA', (half * 2, bot - top), (110, 160, 215, 115))
            box = frame.crop((px - half, top, px + half, bot)).convert('RGBA')
            frame.paste(Image.alpha_composite(box, overlay).convert('RGB'), (px - half, top))
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    print('完成:', out_path)


if __name__ == '__main__':
    main()
