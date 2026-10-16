# -*- coding: utf-8 -*-
"""
用途：追踪参考视频里「蓝色播放光标」的横坐标随时间的变化。

原理：光标是一块浅蓝色半透明矩形；逐帧统计「蓝色像素」最多的那一列，
即光标中心。得到 x(t) 后可反推：
  - 第 1 小节的时间原点（光标回到行首的时刻）
  - 实际速度 BPM（x 与 t 的斜率）

用法： python ref_cursor.py <ffmpeg.exe> <视频> <起始秒> <结束秒> <步长秒>
"""

import subprocess
import sys

import numpy as np


def grab_rgb(ff, video, t, w=960, h=540):
    """在指定时间点抽一帧，缩放到 w×h，返回 RGB 三维数组。"""
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", video,
           "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3).astype(np.int16)


def cursor_x(img):
    """找出蓝色像素最集中的列，返回 (x, 该列蓝像素数, 总蓝像素数)。"""
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    blue = (b - r > 18) & (b - g > 6) & (b > 110)
    col = blue.sum(axis=0)
    if col.max() < 4:
        return -1, 0, int(blue.sum())
    return int(col.argmax()), int(col.max()), int(blue.sum())


def main():
    ff, video = sys.argv[1], sys.argv[2]
    t0, t1, step = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
    W = 960
    print("  时间(s)  光标x(960宽)  该列蓝像素  蓝像素总数")
    samples = []
    t = t0
    while t <= t1 + 1e-9:
        x, n, tot = cursor_x(grab_rgb(ff, video, t))
        print(f"  {t:7.2f}   {x:>10}   {n:>10}   {tot:>10}")
        if x >= 0:
            samples.append((t, x * 2))   # 换算回 1920 坐标系
        t += step

    # 只在x单调递增的区段内做线性拟合，用于估算 BPM
    if len(samples) > 8:
        ts = np.array([s[0] for s in samples])
        xs = np.array([s[1] for s in samples], dtype=float)
        seg_t, seg_x = [ts[0]], [xs[0]]
        for i in range(1, len(samples)):
            if xs[i] > xs[i - 1]:
                seg_t.append(ts[i])
                seg_x.append(xs[i])
        seg_t, seg_x = np.array(seg_t), np.array(seg_x)
        if len(seg_t) > 8:
            k, b = np.polyfit(seg_t, seg_x, 1)
            print(f"\n[拟合] 光标 x = {k:.2f} * t + {b:.2f}  (像素/秒)")
            print("[提示] 每小节宽 440px 左右时，像素/秒 ÷ 每小节宽 × 4 = BPM")


if __name__ == "__main__":
    main()
