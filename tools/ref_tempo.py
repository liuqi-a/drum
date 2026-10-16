# -*- coding: utf-8 -*-
"""
用途：从音频直接测出真实 BPM，并找出鼓组第一次进入的时间点。

做法：
  1) 计算宽带能量包络的「起音强度」（正向差分），做自相关找拍周期。
  2) 在 35-120Hz（底鼓）频段找峰值，观察鼓组进入时刻。

用法： python ref_tempo.py <ffmpeg.exe> <音频> <起始秒> <结束秒>
"""

import subprocess
import sys

import numpy as np


def decode(ff, path, t0, t1, sr=22050):
    """解码指定时间区间为单声道浮点数组。"""
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-ss", str(t0), "-t", str(t1 - t0),
           "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0, sr


def stft_mag(sig, n_fft=1024, hop=256):
    """短时幅度谱与频率轴、时间轴。"""
    win = np.hanning(n_fft).astype(np.float32)
    frames = 1 + (len(sig) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(frames)[:, None]
    return np.abs(np.fft.rfft(sig[idx] * win, axis=1)), hop


def band(mag, freqs, lo, hi):
    """取指定频段的平均能量包络。"""
    m = (freqs >= lo) & (freqs <= hi)
    return mag[:, m].mean(axis=1)


def main():
    ff, audio = sys.argv[1], sys.argv[2]
    t0, t1 = float(sys.argv[3]), float(sys.argv[4])
    sr = 22050
    sig, _ = decode(ff, audio, t0, t1, sr)
    mag, hop = stft_mag(sig)
    freqs = np.fft.rfftfreq(1024, 1.0 / sr)

    kick = band(mag, freqs, 35, 120)
    snare = band(mag, freqs, 150, 420)
    hat = band(mag, freqs, 6000, 11000)
    broad = kick + snare + hat
    fps = sr / hop   # 包络帧率

    # 起音强度：正向差分后做自相关
    onset = np.diff(broad)
    onset[onset < 0] = 0.0
    onset = onset - onset.mean()
    ac = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
    ac = ac / (ac[0] + 1e-9)

    lo_lag = int(0.30 * fps)   # 最快 200 BPM
    hi_lag = int(1.20 * fps)   # 最慢 50 BPM
    seg = ac[lo_lag:hi_lag]
    peaks = []
    for i in range(1, len(seg) - 1):
        if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1]:
            peaks.append((float(seg[i]), lo_lag + i))
    peaks.sort(reverse=True)

    print(f"[速度] 分析区间 {t0}-{t1}s，包络帧率 {fps:.1f} Hz")
    print("[速度] 自相关候选（相关值 / 周期秒 / 对应 BPM）:")
    for v, lag in peaks[:6]:
        period = lag / fps
        print(f"        {v:6.3f}   {period:6.3f}s   {60.0 / period:7.2f} BPM")

    # 底鼓峰值出现时刻
    thr = np.percentile(kick, 92)
    times = (np.arange(len(kick)) * hop + 1024 / 2) / sr + t0
    hits = []
    for i in range(1, len(kick) - 1):
        if kick[i] > thr and kick[i] > kick[i - 1] and kick[i] >= kick[i + 1]:
            if not hits or times[i] - hits[-1] > 0.12:
                hits.append(float(times[i]))
    print(f"\n[鼓组] 底鼓峰值前 20 个时刻（区间 {t0}-{t1}s）:")
    print("        " + ", ".join(f"{h:.2f}" for h in hits[:20]))
    if len(hits) > 2:
        d = np.diff(hits[:20])
        print(f"[鼓组] 相邻底鼓间隔: {np.round(d, 3).tolist()}")


if __name__ == "__main__":
    main()
