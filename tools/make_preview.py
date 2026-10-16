# 用途：用 PDF 页面原图做底，生成「前 N 拍」的样片（谱面与 PDF 逐符号一致，光标按时间线性扫行）
import os
import subprocess
import sys

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

BPM = 104.0          # 再放慢一点点
BEAT = 60.0 / BPM
PHASE = 14.33            # 谱面第 1 小节 = 歌曲 14.33 秒（鼓组进入点）
FPS = 60
WIDTH, HEIGHT = 1920, 1080


def detect_systems(gray):
    # 谱线 = 又薄又横向连续的暗行；5 条一组构成一条谱行
    thr = float(np.median(gray)) - 60
    prof = (gray < thr).mean(axis=1)
    above = prof > 0.25
    runs, start = [], -1
    for i, v in enumerate(above):
        if v and start < 0:
            start = i
        if (not v) and start >= 0:
            runs.append((start, i - 1))
            start = -1
    if start >= 0:
        runs.append((start, len(above) - 1))
    lines = []
    for a, b in runs:
        if (b - a) > 14:
            continue
        band = gray[a:b + 1, :]
        if float((band < thr).mean()) > 0.75:
            lines.append(int((a + b) / 2))
    systems, cur = [], []
    for y in lines:
        if cur and y - cur[-1] > 60:
            if len(cur) >= 5:
                systems.append(cur[:5] if len(cur) == 5 else cur)
            cur = []
        cur.append(y)
    if len(cur) >= 5:
        systems.append(cur)
    out = []
    for s in systems:
        if len(s) >= 5:
            grp = s[:5]
            gaps = np.diff(grp)
            if gaps.min() > 4 and gaps.max() < 40:
                out.append(grp)
    return out


def detect_barlines(gray, staff):
    # 小节线 = 竖直贯穿谱表高度的细线段
    thr = float(np.median(gray)) - 60
    top, bottom = staff[0], staff[-1]
    h = bottom - top
    need = int(h * 0.85)
    cols = []
    for x in range(gray.shape[1]):
        col = gray[max(0, top - 6):bottom + 7, x] < thr
        best, run = 0, 0
        for v in col:
            run = run + 1 if v else 0
            best = max(best, run)
        if best >= need:
            cols.append(x)
    groups = []
    for x in cols:
        if groups and x - groups[-1][-1] <= 5:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [int(sum(g) / len(g)) for g in groups if len(g) <= 16]


def main():
    pdf, audio, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    n_beats = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    n_bars = max(1, n_beats // 4)
    dpi = int(sys.argv[5]) if len(sys.argv) > 5 else 300
    doc = pymupdf.open(pdf)
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    tmp = os.path.join(os.path.dirname(out_path), '_preview_page.png')
    pix.save(tmp)
    img = Image.open(tmp).convert('RGB')
    gray = np.asarray(img.convert('L')).astype(np.int16)
    systems = detect_systems(gray)
    if not systems:
        print('没检出谱行')
        return
    # 依序切出小节：每个谱行内用小节线分小节，第一小节从谱线左端起算
    bars = []
    for staff in systems:
        bl = detect_barlines(gray, staff)
        # 谱行墨迹的横向范围，作为该行第一小节的起点
        band = gray[staff[0]:staff[-1] + 1, :]
        xs = np.where((band < (float(np.median(gray)) - 60)).mean(axis=0) > 0.02)[0]
        if xs.size == 0 or len(bl) < 1:
            continue
        edges = [int(xs[0])] + sorted(bl)
        for i in range(len(edges) - 1):
            bars.append({'xa': edges[i], 'xb': edges[i + 1], 'top': staff[0], 'bottom': staff[-1]})
        # 行末小节（最后一条小节线之后）
        bars.append({'xa': edges[-1], 'xb': int(xs[-1]), 'top': staff[0], 'bottom': staff[-1]})
        if len(bars) >= n_bars:
            break
    bars = bars[:n_bars]
    print('检出谱行 %d 条，取前 %d 小节做样片' % (len(systems), len(bars)))
    for i, b in enumerate(bars, 1):
        print('  第%d小节 x=%d..%d y=%d..%d' % (i, b['xa'], b['xb'], b['top'], b['bottom']))
    scale = WIDTH / float(img.width)
    win_h = int(img.width * HEIGHT / float(WIDTH))
    dur = n_bars * 4 * BEAT
    total = int(round(dur * FPS))
    ff = subprocess.run([sys.executable, '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True).stdout.strip()
    cmd = [ff, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (WIDTH, HEIGHT),
           '-r', str(FPS), '-i', '-', '-ss', '%.3f' % PHASE, '-t', '%.3f' % dur, '-i', audio,
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 44)
    except Exception:
        font = ImageFont.load_default()
    for i in range(total):
        t = i / float(FPS)
        # 匀速：光标在同一谱行内以恒定速度扫过（像钟表指针），不在小节线处变速
        f_line = min(max(t / dur, 0.0), 1.0)
        x = bars[0]['xa'] + f_line * (bars[-1]['xb'] - bars[0]['xa'])
        which = min(len(bars) - 1, int(t / (4 * BEAT)))
        bar = bars[which]
        y_off = int(max(0, min(img.height - win_h, bar['top'] - win_h * 0.45)))
        frame = img.crop((0, y_off, img.width, y_off + win_h)).resize((WIDTH, HEIGHT), Image.BILINEAR)
        half = int(0.018 * WIDTH)
        px = int(x * scale)
        top = int((bar['top'] - y_off - 70) * scale)
        bot = int((bar['bottom'] - y_off + 90) * scale)
        top, bot = max(0, top), min(HEIGHT, bot)
        x_lo, x_hi = max(0, px - half), min(WIDTH, px + half)
        if bot > top and x_hi > x_lo:
            ov = Image.new('RGBA', (x_hi - x_lo, bot - top), (110, 160, 215, 120))
            box = frame.crop((x_lo, top, x_hi, bot)).convert('RGBA')
            frame.paste(Image.alpha_composite(box, ov).convert('RGB'), (x_lo, top))
        d = ImageDraw.Draw(frame)
        d.text((40, 28), '样片：前 %d 拍（第 %d–%d 小节）' % (n_beats, 1, len(bars)), fill=(60, 60, 60), font=font)
        d.text((WIDTH - 300, 28), '第 %d 小节' % (which + 1), fill=(150, 60, 60), font=font)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    print('完成:', out_path, '时长 %.2f 秒' % dur)


if __name__ == '__main__':
    main()
