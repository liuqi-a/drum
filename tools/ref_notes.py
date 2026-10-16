# -*- coding: utf-8 -*-
"""
用途：从参考谱面抽帧里「机器识谱」——自动定位符头，再按小节线映射到十六分格子。
原理：积分图做滑动窗口暗像素求和 -> 符头区域得分远高于谱线 -> 非极大值抑制取峰
      -> 按 y 分到鼓件行（镲片/军鼓/底鼓）-> 按 x 映射到小节内的十六分格子。
用法： python ref_notes.py <ffmpeg.exe> <抽帧png>
"""

import subprocess
import sys

import numpy as np

# 参考帧 hq_t1.png（1920x1080）实测版面常量：两个系统的三种鼓件所在 y 范围
ROWS = [
    ("sys1_cymbal", 340, 378, 0.35),
    ("sys1_snare", 403, 424, 0.55),
    ("sys1_kick", 450, 505, 0.55),
    ("sys2_cymbal", 551, 589, 0.35),
    ("sys2_snare", 614, 635, 0.55),
    ("sys2_kick", 661, 716, 0.55),
]

# 每小节左右边界（由 ref_analyze 检出的相邻小节线）
BARS = [
    (3, 1181, 1818),
    (4, 155, 485),
    (5, 485, 825),
    (6, 825, 1164),
    (7, 1164, 1594),
    (8, 1594, 1818),
]


def gray(ff, png):
    """整帧转灰度，返回 1080x1920 数组。"""
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-i", png,
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(1080, 1920)


def boxsum(a, kw, kh):
    """积分图求 kw×kh 滑动窗口内像素和。"""
    ii = np.pad(np.cumsum(np.cumsum(a, axis=0), axis=1), ((1, 0), (1, 0)))
    return ii[kh:, kw:] - ii[:-kh, kw:] - ii[kh:, :-kw] + ii[:-kh, :-kw]


def find_heads(dark, y0, y1, thr, min_dx=13):
    """在 y0..y1 行带内找符头中心，返回按 x 升序的 (x, y) 列表。"""
    band = dark[y0:y1, :].astype(np.float32)
    kh = y1 - y0
    score = boxsum(band, 17, kh) / (17.0 * kh)
    prof = score.max(axis=0)
    out = []
    for c in np.where(prof > thr)[0]:
        if out and c - out[-1] < min_dx:
            if prof[c] > prof[out[-1]]:
                out[-1] = int(c)
            continue
        out.append(int(c))
    heads = []
    for c in out:
        col = score[:, max(0, c - 8):c + 9].mean(axis=1)
        heads.append((c, int(y0 + np.argmax(col))))
    return heads


def main():
    ff, png = sys.argv[1], sys.argv[2]
    dark = gray(ff, png) < 110
    heads = {name: find_heads(dark, y0, y1, thr) for name, y0, y1, thr in ROWS}
    for name, hs in heads.items():
        print(f"[{name}] {len(hs)} 个符头 x=" + ",".join(str(h[0]) for h in hs))

    print("\n[汇总] H=镲片 S=军鼓 K=底鼓（按小节 × 十六分格子）")
    print("            1   e   &   a   2   e   &   a   3   e   &   a   4   e   &   a")
    for bar, x0, x1 in BARS:
        pre = "sys1" if bar == 3 else "sys2"
        cells = ["" for _ in range(16)]
        for sym, key in (("H", "cymbal"), ("S", "snare"), ("K", "kick")):
            for x, _y in heads[f"{pre}_{key}"]:
                if not (x0 <= x <= x1):
                    continue
                slot = min(15, max(0, int(round((x - x0) / (x1 - x0) * 16 - 0.5))))
                if sym not in cells[slot]:
                    cells[slot] += sym
        line = " ".join(f"{c if c else '.':^3}" for c in cells)
        print(f"  bar{bar:>2}   {line[:35]} | {line[36:]}")


if __name__ == "__main__":
    main()
