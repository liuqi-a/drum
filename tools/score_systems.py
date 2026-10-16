# 用途：在纸质谱照片里自动定位每条谱表系统（5 线一组），并裁出高清图供逐行读谱
import json
import os
import sys

import numpy as np
from PIL import Image


def find_systems(gray: np.ndarray, x0: int, x1: int, y_start: int = 200, threshold: float = 0.25):
    # 逐行统计暗像素比例，再取局部峰值作为谱线中心（对轻微倾斜与纸张起伏更稳）
    band = gray[y_start:, x0:x1]
    prof = (band < 170).mean(axis=1).astype(float)
    prof = np.convolve(prof, np.ones(5) / 5, mode='same')
    peaks = []
    for y in range(3, len(prof) - 3):
        if prof[y] >= prof[y - 1] and prof[y] >= prof[y + 1] and prof[y] > threshold:
            if peaks and y - peaks[-1] <= 8:
                if prof[y] > prof[peaks[-1]]:
                    peaks[-1] = y
            else:
                peaks.append(y)
    peaks = [p + y_start for p in peaks]
    # 把间距小的峰值聚成一条“系统”（一组 5 线）
    systems = []
    group = [peaks[0]]
    for c in peaks[1:]:
        if c - group[-1] <= 45:
            group.append(c)
        else:
            if len(group) >= 4:
                systems.append(group)
            group = [c]
    if len(group) >= 4:
        systems.append(group)
    return systems


def main():
    src = sys.argv[1]
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    img = Image.open(src).convert('L')
    arr = np.array(img)
    h, w = arr.shape
    x0, x1 = int(w * 0.08), int(w * 0.95)
    systems = find_systems(arr, x0, x1)
    print('页面尺寸: %dx%d, 识别到系统数: %d' % (w, h, len(systems)))
    info = []
    color = Image.open(src)
    for i, sys_lines in enumerate(systems):
        top = max(0, sys_lines[0] - 60)
        bottom = min(h, sys_lines[-1] + 60)
        # 上下各留 60 像素余量（含符干、装饰记号），整行裁切并放大 2 倍
        crop = color.crop((int(w * 0.03), top, w, bottom))
        scale = 2
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
        path = os.path.join(outdir, 'sys_%02d.png' % (i + 1))
        crop.save(path)
        info.append({'index': i + 1, 'lines': sys_lines, 'top': top, 'bottom': bottom, 'file': path})
        print('系统 %02d: 谱线 y=%s  裁切 %d..%d  -> %s' % (i + 1, sys_lines, top, bottom, os.path.basename(path)))
    with open(os.path.join(outdir, 'systems.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
