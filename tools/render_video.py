# 用途：把 MuseScore 导出的谱页渲染成“滚动谱 + 蓝色播放头”视频，并与原曲音频合成 MP4
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

BPM = 106.0
PHASE = 0.044
BAR = 240.0 / BPM
FPS = 60
WIDTH, HEIGHT = 1920, 1080


def staff_systems(gray):
    thr = float(np.median(gray)) - 45
    prof = (gray < thr).mean(axis=1)
    lines = []
    for ratio in (0.28, 0.18):
        above = prof > ratio
        runs, start = [], -1
        for i, v in enumerate(above):
            if v and start < 0:
                start = i
            if (not v) and start >= 0:
                runs.append((start, i - 1))
                start = -1
        if start >= 0:
            runs.append((start, len(above) - 1))
        # 谱线判据：够薄 + 横向几乎连续（符杠只在局部出现，连续性差）
        x0, x1 = int(gray.shape[1] * 0.08), int(gray.shape[1] * 0.96)
        lines = []
        for a, b in runs:
            if (b - a) > 16:
                continue
            band = gray[a:b + 1, x0:x1]
            cont = float((band < thr).mean())
            if cont > 0.75:
                lines.append(int((a + b) / 2))
        if len(lines) >= 5:
            break
    if len(lines) < 5:
        return []
    systems = []
    cur = []

    def best_five(group):
        # 候选行里挑间距最均匀的连续 5 条（排除符杠等干扰造成的多余行）
        best = None
        for s in range(0, max(1, len(group) - 4)):
            for e in range(s + 5, min(len(group) + 1, s + 8)):
                grp = group[s:e]
                if len(grp) != 5:
                    continue
                gaps = np.diff(grp)
                if gaps.min() < 15 or gaps.max() > 45:
                    continue
                sc = float(gaps.std())
                if best is None or sc < best[0]:
                    best = (sc, list(grp))
        return None if best is None else best[1]

    for y in lines:
        if cur and y - cur[-1] > 150:
            five = best_five(cur)
            if five:
                systems.append(five)
            cur = []
        cur.append(y)
    five = best_five(cur)
    if five:
        systems.append(five)
    return systems


def barlines(gray, staff):
    # 小节线 = 竖直贯穿谱表高度的细线段（与行带是否对齐无关，更稳）
    thr = float(np.median(gray)) - 45
    top, bottom = staff[0], staff[-1]
    h = bottom - top
    lo, hi = max(0, top - 6), min(gray.shape[0], bottom + 7)
    need = int(h * 0.85)
    out = []
    for x in range(gray.shape[1]):
        col = gray[lo:hi, x] < thr
        best, run = 0, 0
        for v in col:
            run = run + 1 if v else 0
            best = max(best, run)
        if best >= need:
            out.append(x)
    groups = []
    for x in out:
        if groups and x - groups[-1][-1] <= 4:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [int(sum(g) / len(g)) for g in groups if len(g) <= 14]


def build_bars(pages):
    # 依页顺序建立小节位置表：每行 4 小节，横向按谱行墨迹范围均分
    bars = []
    for img in pages:
        gray = np.asarray(img.convert('L')).astype(np.int16)
        thr = float(np.median(gray)) - 45
        for staff in staff_systems(gray):
            band = gray[staff[0]:staff[-1] + 1, :]
            ink = (band < thr).mean(axis=0) > 0.02
            xs = np.where(ink)[0]
            if xs.size < 10:
                continue
            x_left, x_right = int(xs[0]), int(xs[-1])
            bl = [b for b in barlines(gray, staff) if x_left - 20 <= b <= x_right + 20]
            spans = []
            if len(bl) >= 2:
                w = int(np.median(np.diff(bl)))
                spans.append((max(0, bl[0] - w), bl[0]))
                for i in range(len(bl) - 1):
                    spans.append((bl[i], bl[i + 1]))
            else:
                n = 4
                w = (x_right - x_left) / float(n)
                spans = [(int(x_left + k * w), int(x_left + (k + 1) * w)) for k in range(n)]
            for (x0, x1) in spans:
                bars.append({'page': img, 'x0': x0, 'x1': x1, 'top': staff[0], 'bottom': staff[-1]})
    return bars


def main():
    page_dir, audio, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    files = sorted(glob.glob(os.path.join(page_dir, 'lg-*.png')))
    if not files:
        print('没找到谱页图片')
        return
    # 大页先统一缩小到工作分辨率，避免逐帧处理过慢
    raw_pages = [Image.open(f).convert('RGB') for f in files]
    wk = 3000.0 / raw_pages[0].width
    pages = [p.resize((3000, int(p.height * wk)), Image.LANCZOS) for p in raw_pages]
    bars = build_bars(pages)
    print('共识别到 %d 个小节位置' % len(bars), '页数', len(pages))
    if len(bars) < 80:
        print('警告：小节数不足 85，回退为等宽近似布局')
    scale = WIDTH / float(pages[0].width)
    dur = float(sys.argv[4]) if len(sys.argv) > 4 else 191.85
    total = int(dur * FPS)
    ff = subprocess.run([sys.executable, '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True).stdout.strip()
    cmd = [ff, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (WIDTH, HEIGHT),
           '-r', str(FPS), '-i', '-', '-i', audio, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    page_w = pages[0].width
    win_h = int(page_w * HEIGHT / WIDTH)
    for i in range(total):
        t = i / float(FPS)
        idx = min(len(bars) - 1, max(0, int((t - PHASE) / BAR)))
        bar = bars[idx]
        f = ((t - PHASE) / BAR) - idx
        f = min(max(f, 0.0), 1.0)
        page = bar['page']
        # 纵向滚动：让当前谱行大致处于画面中上部，行间平滑过渡
        target = bar['top'] - win_h * 0.32
        nxt = bars[min(idx + 1, len(bars) - 1)]
        if nxt['page'] is not page:
            target = bar['top'] - win_h * 0.32
        y0 = int(max(0, min(page.height - win_h, target)))
        frame = page.crop((0, y0, page_w, y0 + win_h)).resize((WIDTH, HEIGHT), Image.BILINEAR)
        # 播放头：横跨当前谱行的半透明蓝色竖条
        x = int((bar['x0'] + f * (bar['x1'] - bar['x0'])) * scale)
        half = int(0.055 * WIDTH)
        top = int((bar['top'] - y0 - 0.9 * (bar['bottom'] - bar['top']) / 4) * scale)
        bot = int((bar['bottom'] - y0 + 1.1 * (bar['bottom'] - bar['top']) / 4) * scale)
        top = max(0, top)
        bot = min(HEIGHT, bot)
        if bot > top:
            overlay = Image.new('RGBA', (abs(half * 2), bot - top), (110, 160, 215, 110))
            frame.paste(Image.alpha_composite(frame.crop((x - half, top, x + half, bot)).convert('RGBA'), overlay).convert('RGB'),
                        (x - half, top))
        proc.stdin.write(frame.tobytes())
        if i % 600 == 0:
            print('  帧 %d/%d' % (i, total))
    proc.stdin.close()
    proc.wait()
    print('完成:', out_path)


if __name__ == '__main__':
    main()
