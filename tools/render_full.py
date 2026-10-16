# 用途：整曲渲染——PDF 原页做底图（谱面零改动），光标按「每小节 = BAR 秒」扫过该小节。
#       片头定格倒数 3 秒（3→2→1 白字），倒数结束对准第 1 小节强拍后光标开扫；
#       每行光标从第一个音符起，跳过行首打击乐谱号（双竖线）与拍号。
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont


def desktop_dir():
    # 用户桌面目录（编制完成后成片要拷到这里）
    home = os.path.expanduser('~')
    for name in ('Desktop', '桌面'):
        path = os.path.join(home, name)
        if os.path.isdir(path):
            return path
    return home


def save_to_desktop(src_mp4):
    # 编制完成后把成片复制到桌面，返回桌面路径
    if not src_mp4 or not os.path.isfile(src_mp4):
        return None
    dest = os.path.join(desktop_dir(), os.path.basename(src_mp4))
    shutil.copy2(src_mp4, dest)
    return dest

BPM = 103.5          # 烟嗓版：按听感再放慢一点点
BEAT = 60.0 / BPM
BAR = 4 * BEAT
PHASE = 0.38          # 烟嗓版：谱面第 1 小节对到该版本第一个强拍
COUNTDOWN = 3.0       # 片头定格倒数秒数（3→2→1），结束时刻 = 第 1 小节强拍
FPS = 60
W, H = 1920, 1080
TOTAL_BARS = 60          # 只做 PDF 覆盖的 1–60 小节
CHART_BARS = 60          # PDF 覆盖 1–60 小节
REPEAT_FROM = 42         # 61 小节起复用 PDF 第 42 小节开始的节奏
# 各页每条谱行的小节数（按 PDF 行首小节号读出，合计 41 + 19 = 60）
CHARTS = {1: [7, 5, 4, 3, 3, 5, 5, 3, 3, 3], 2: [3, 3, 3, 3, 3, 3, 1]}


def render_pdf(pdf, dpi=300):
    # 把 PDF 每一页渲成高分辨率位图
    doc = pymupdf.open(pdf)
    imgs = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_page_tmp.png')
        pix.save(tmp)
        imgs.append(Image.open(tmp).convert('RGB'))
    doc.close()
    return imgs


def detect_systems(gray):
    # 找五线谱系统：连续细横线聚成一组
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
        if float((gray[a:b + 1, :] < thr).mean()) > 0.75:
            lines.append(int((a + b) / 2))
    systems, cur = [], []
    for y in lines:
        if cur and y - cur[-1] > 60:
            if len(cur) >= 5:
                systems.append(cur[:5])
            cur = []
        cur.append(y)
    if len(cur) >= 5:
        systems.append(cur[:5])
    out = []
    for s in systems:
        if len(s) == 5:
            gaps = np.diff(s)
            if gaps.min() > 4 and gaps.max() < 40:
                out.append(s)
    return out


def detect_barlines(gray, staff):
    # 在谱带内找竖向小节线
    thr = float(np.median(gray)) - 60
    top, bottom = staff[0], staff[-1]
    need = int((bottom - top) * 0.85)
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


def clef_end_x(gray, staff, xa, xb):
    # 行首打击乐谱号（两条粗竖线）的右端
    thr = float(np.median(gray)) - 60
    top, bottom = staff[0], staff[-1]
    h = bottom - top + 1
    ink = gray[top:bottom + 1, xa:xb] < thr
    col_h = ink.sum(axis=0)
    n = len(col_h)
    i, last, blocks = 0, 0, 0
    while i < min(n, 120):
        if col_h[i] >= h * 0.55:
            j = i
            while j < n and col_h[j] >= h * 0.3:
                j += 1
            last, blocks = j, blocks + 1
            i = j
            k = i
            while k < min(n, i + 20) and col_h[k] < h * 0.25:
                k += 1
            i = k
            if blocks >= 2:
                break
        else:
            i += 1
    return xa + last


def first_note_x(gray, staff, xa, xb):
    # 跳过谱号（及可能的拍号），返回该小节内第一个符头的 x
    thr = float(np.median(gray)) - 60
    top, bottom = staff[0], staff[-1]
    gap = float(np.median(np.diff(staff)))
    y0 = max(0, int(top - 2 * gap))
    y1 = min(gray.shape[0], int(bottom + 3 * gap))
    ce = clef_end_x(gray, staff, xa, xb)
    x0 = min(xb - 10, ce + 6)
    roi = gray[y0:y1, x0:xb].astype(np.uint8)
    bw = (roi < thr).astype(np.uint8) * 255
    hline = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, int(gap * 3)), 1))
    vline = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, int(gap * 2.5))))
    notes = cv2.subtract(bw, cv2.morphologyEx(bw, cv2.MORPH_OPEN, hline))
    notes = cv2.subtract(notes, cv2.morphologyEx(bw, cv2.MORPH_OPEN, vline))
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(3, int(gap * 0.6)), max(3, int(gap * 0.6))))
    notes = cv2.morphologyEx(notes, cv2.MORPH_CLOSE, ker)
    nlab, _, stats, cents = cv2.connectedComponentsWithStats(notes, connectivity=8)
    gap = max(gap, 8.0)
    cands = []
    for i in range(1, nlab):
        x, y, w, h, area = stats[i]
        if area < gap * gap * 0.25 or area > gap * gap * 8:
            continue
        if w < gap * 0.35 or w > gap * 2.8:
            continue
        if h < gap * 0.35 or h > gap * 3.5:
            continue
        if h / float(w) > 3.2:
            continue
        cx = x0 + int(cents[i][0])
        cands.append((cx, w, h))
    if not cands:
        return min(xb - 5, ce + int(gap * 4))
    cands.sort(key=lambda t: t[0])
    filtered = []
    for cx, w, h in cands:
        # 紧贴谱号的瘦高块多半是拍号数字，跳过
        if cx - ce < gap * 2.2 and h > gap * 1.6 and w < gap * 1.2:
            continue
        filtered.append(cx)
    return filtered[0] if filtered else cands[0][0]


def draw_cursor(frame, b, x, y_off, scale):
    # 在帧上叠半透明蓝色播放光标
    half = int(0.016 * W)
    px = int(x * scale)
    top = int((b['top'] - y_off - 62) * scale)
    bot = int((b['bottom'] - y_off + 84) * scale)
    top, bot = max(0, top), min(H, bot)
    x_lo, x_hi = max(0, px - half), min(W, px + half)
    if bot > top and x_hi > x_lo:
        ov = Image.new('RGBA', (x_hi - x_lo, bot - top), (110, 160, 215, 120))
        box = frame.crop((x_lo, top, x_hi, bot)).convert('RGBA')
        frame.paste(Image.alpha_composite(box, ov).convert('RGB'), (x_lo, top))
    return frame


def main():
    pdf, audio, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    score_dur = float(sys.argv[4]) if len(sys.argv) > 4 else 191.85
    pages = render_pdf(pdf, 300)
    print('PDF 页数:', len(pages), '尺寸:', pages[0].size)
    # 依序建立 1..60 小节的位置表
    bars = []
    for pi, img in enumerate(pages, 1):
        gray = np.asarray(img.convert('L')).astype(np.int16)
        thr = float(np.median(gray)) - 60
        systems = detect_systems(gray)
        counts = CHARTS.get(pi, [])
        for si, staff in enumerate(systems):
            bl = detect_barlines(gray, staff)
            band = gray[staff[0]:staff[-1] + 1, :]
            xs = np.where((band < thr).mean(axis=0) > 0.02)[0]
            if xs.size == 0:
                continue
            n = counts[si] if si < len(counts) else max(1, len(bl))
            inner = [int(x) for x in sorted(bl) if int(xs[0]) + 30 < x < int(xs[-1]) - 10]
            if len(inner) == n - 1:
                edges = [int(xs[0])] + inner + [int(xs[-1])]
            else:
                w = (int(xs[-1]) - int(xs[0])) / float(n)
                edges = [int(xs[0] + k * w) for k in range(n + 1)]
            for i in range(n):
                xa, xb = edges[i], edges[i + 1]
                # 每行第一个小节：光标从首音符起，不从双竖线谱号起
                if i == 0:
                    xa = first_note_x(gray, staff, xa, xb)
                    if xa >= xb - 8:
                        xa = edges[i] + max(20, (edges[i + 1] - edges[i]) // 5)
                bars.append({'page': pi, 'xa': int(xa), 'xb': int(xb),
                             'top': staff[0], 'bottom': staff[-1], 'line': len(bars)})
    print('PDF 内检出小节数:', len(bars))
    if len(bars) > CHART_BARS:
        bars = bars[:CHART_BARS]
    play = []
    for pb in range(TOTAL_BARS):
        src = pb if pb < CHART_BARS else (REPEAT_FROM - 1) + (pb - CHART_BARS)
        if src >= len(bars):
            src = len(bars) - 1
        play.append(bars[src])
    print('播放小节数:', len(play), '倒数:', COUNTDOWN, 's')
    scale = W / float(pages[0].width)
    win_h = int(pages[0].width * H / float(W))
    # 视频总长 = 倒数 + 谱面时长；音频延迟使倒数结束 = PHASE 强拍
    audio_delay_ms = max(0, int(round((COUNTDOWN - PHASE) * 1000)))
    total = int((COUNTDOWN + score_dur) * FPS)
    ff = subprocess.run([sys.executable, '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True).stdout.strip()
    # adelay：片头静音垫到强拍，保证倒数结束与第 1 小节对齐
    cmd = [ff, '-y', '-v', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-i', audio,
           '-filter_complex', '[1:a]adelay=%d|%d[a]' % (audio_delay_ms, audio_delay_ms),
           '-map', '0:v', '-map', '[a]',
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 42)
        bigfont = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 380)
    except Exception:
        font = ImageFont.load_default()
        bigfont = font
    for i in range(total):
        t = i / float(FPS)
        if t < COUNTDOWN:
            # 定格：第 1 小节首音符，光标停住；只叠白色倒计时数字
            pb, f = 0, 0.0
            n = 3 - int(t)
            n = max(1, min(3, n))
            show_count = True
        else:
            t_mus = t - COUNTDOWN  # 0 对应第 1 小节强拍
            pb = int(t_mus / BAR)
            if pb < 0:
                pb = 0
            if pb >= len(play):
                pb = len(play) - 1
            t0 = pb * BAR
            f = min((t_mus - t0) / BAR, 1.0)
            show_count = False
            n = 0
        b = play[pb]
        x = b['xa'] + f * (b['xb'] - b['xa'])
        y = b['top']
        img = pages[b['page'] - 1]
        y_off = int(max(0, min(img.height - win_h, y - win_h * 0.42)))
        frame = img.crop((0, y_off, img.width, y_off + win_h)).resize((W, H), Image.BILINEAR)
        frame = draw_cursor(frame, b, x, y_off, scale)
        d = ImageDraw.Draw(frame)
        label = '重复（按前段节奏续写）' if pb + 1 > CHART_BARS else '原谱'
        d.text((36, 26), '%s   第 %d 小节' % (label, pb + 1), fill=(70, 70, 70), font=font)
        if show_count:
            txt = str(n)
            tw = d.textlength(txt, font=bigfont)
            cx, cy = W / 2, H / 2 - 90
            # 白色阿拉伯数字，淡黑描边保证可读
            d.text((cx - tw / 2 + 4, cy + 4), txt, fill=(0, 0, 0), font=bigfont)
            d.text((cx - tw / 2, cy), txt, fill=(255, 255, 255), font=bigfont)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    print('完成:', out_path, 'audio_delay_ms=', audio_delay_ms)
    desk = save_to_desktop(out_path)
    if desk:
        print('桌面副本:', desk)


if __name__ == '__main__':
    main()
