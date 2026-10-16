# -*- coding: utf-8 -*-
"""
用途：从参考视频中提取「客观证据」，避免肉眼读谱出错。

做三件事：
  1) 谱面几何：定位五线谱横线，并在谱带内检出所有小节线的横坐标。
  2) 节拍对齐：用音频宽带能量包络自动求出十六分网格的时间原点。
  3) 鼓点推断：把前 30 秒音频按十六分网格切分，分频段统计能量，推断命中。

用法： python ref_analyze.py <ffmpeg.exe> <抽帧png> <音频文件> [bpm] [bar1时间]
"""

import subprocess
import sys

import numpy as np


def ff_gray(ff, png, x, y, w, h):
    """裁切图像并转灰度裸数据，返回二维数组。"""
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-i", png,
           "-vf", f"crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    data = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(data, dtype=np.uint8).reshape(h, w)


def ff_audio(ff, path, seconds, sr=22050):
    """解码为单声道 16bit PCM，返回归一化浮点数组。"""
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-t", str(seconds), "-i", path,
           "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0, sr


def band_energy(sig, sr, n_fft=1024, hop=256):
    """短时 FFT，输出各频段能量包络与对应时间轴。"""
    win = np.hanning(n_fft).astype(np.float32)
    frames = 1 + (len(sig) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.abs(np.fft.rfft(sig[idx] * win, axis=1))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    bands = {
        "kick": (35, 120),        # 底鼓：低频冲击
        "snare": (150, 420),      # 军鼓：中频鼓皮共振
        "snare_n": (1200, 3500),  # 军鼓：响弦噪声
        "hat": (6000, 11000),     # 踩镲：高频噪声
    }
    env = {}
    for name, (lo, hi) in bands.items():
        m = (freqs >= lo) & (freqs <= hi)
        env[name] = spec[:, m].mean(axis=1)
    times = (np.arange(frames) * hop + n_fft / 2) / sr
    return env, times


def detect_staff(img, w):
    """找出最上面一组连续五线谱横线，返回暗像素掩码与谱带范围。"""
    dark = img < 110
    rows = np.where(dark.sum(axis=1) > w * 0.5)[0]
    groups, cur = [], [int(rows[0])]
    for y in rows[1:]:
        if y - cur[-1] <= 24:   # 五线谱行距约 17px，用 24 把同一条谱表的 5 条线归并
            cur.append(int(y))
        else:
            groups.append(cur)
            cur = [int(y)]
    groups.append(cur)
    band = [v for v in groups[0]]
    return dark, band, band[0] - 2, band[-1] + 2


def find_barlines(dark, top, bot):
    """在谱带内找整列几乎全暗的竖线（小节线）。"""
    col_dark = dark[top:bot + 1, :].sum(axis=0)
    cand = np.where(col_dark > (bot - top + 1) * 0.8)[0]
    out, group = [], []
    for c in cand:
        if group and c - group[-1] > 3:
            out.append(int(np.mean(group)))
            group = []
        group.append(c)
    if group:
        out.append(int(np.mean(group)))
    return out


def main():
    ff, frame_png, audio = sys.argv[1], sys.argv[2], sys.argv[3]
    bpm = float(sys.argv[4]) if len(sys.argv) > 4 else 100.0
    bar1 = float(sys.argv[5]) if len(sys.argv) > 5 else None
    sixteenth = (60.0 / bpm) / 4.0
    total_bars = 10

    # ---- 1) 谱面几何 ----
    x0, y0 = 0, int(sys.argv[6]) if len(sys.argv) > 6 else 300
    w, h = 1920, 300
    img = ff_gray(ff, frame_png, x0, y0, w, h)
    dark, band, top, bot = detect_staff(img, w)
    print("[谱面] 系统1五线谱横线绝对y:", [int(y + y0) for y in band])
    print(f"[谱面] 谱带 y={top + y0}..{bot + y0}")
    barlines = find_barlines(dark, top, bot)
    print("[谱面] 系统1小节线x:", barlines)
    if len(barlines) >= 2:
        print("[谱面] 相邻间距:", np.diff(barlines).tolist())

    # ---- 2) 音频网格对齐 ----
    sig, sr = ff_audio(ff, audio, 30.0)
    env, times = band_energy(sig, sr)
    broad = env["kick"] + env["snare"] + env["snare_n"] + env["hat"]
    broad = broad / (broad.max() + 1e-9)
    off, best = 0.0, -1.0
    for cand in np.arange(0.0, sixteenth, 0.005):
        grid = cand + np.arange(0, int(28.0 / sixteenth)) * sixteenth
        gi = np.searchsorted(times, grid)
        gi = gi[(gi > 2) & (gi < len(broad) - 2)]
        score = float(np.mean([broad[i - 2:i + 3].max() for i in gi]))
        if score > best:
            best, off = score, float(cand)
    print(f"[音频] 十六分网格相位 = {off:.3f}s（对齐度 {best:.3f}）")
    if bar1 is not None:
        print(f"[音频] 指定第1小节起点 {bar1:.3f}s → 相位 {bar1 % sixteenth:.3f}s（应≈{off:.3f}）")
        off = bar1 if bar1 is not None else off
    grid0 = off

    # ---- 3) 十六分网格的分频段推断 ----
    rows = []
    for b in range(total_bars):
        line = []
        for s in range(16):
            t0 = grid0 + (b * 16 + s) * sixteenth
            m = (times >= t0) & (times < t0 + sixteenth)
            line.append([float(env[n][m].max()) if m.any() else 0.0
                         for n in ("kick", "snare", "snare_n", "hat")])
        rows.append(line)
    # 阈值只用「鼓组已经进入」的小节来估（避免开头静音段把阈值压低）
    flat = np.array(rows[2:]).reshape(-1, 4)
    thr = np.percentile(flat, 70, axis=0)
    print("[音频] 阈值(kick,snare,snare_n,hat) =", np.round(thr, 4).tolist())

    print("\n[音频] 命中推断 K=底鼓 S=军鼓 H=踩镲")
    print("         1   e   &   a   2   e   &   a   3   e   &   a   4   e   &   a")
    for b, row in enumerate(rows):
        txt = []
        for k, sn, nn, ht in row:
            mark = ("K" if k > thr[0] else "") \
                   + ("S" if (sn > thr[1] or nn > thr[2]) else "") \
                   + ("H" if ht > thr[3] else "")
            txt.append(mark if mark else ".")
        head = " ".join(f"{t:^3}" for t in txt[:8])
        tail = " ".join(f"{t:^3}" for t in txt[8:])
        print(f"  bar{b + 1:>2} @{grid0 + b * 16 * sixteenth:5.2f}s  {head} | {tail}")


if __name__ == "__main__":
    main()
