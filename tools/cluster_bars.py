# 用途：把各小节的图样归一化后做相似度聚类，找出重复的节奏型，减少需要逐小节精读的数量
import json
import sys

import numpy as np
from PIL import Image


def bar_vector(img, x_start, x_end, top, bottom, space):
    # 归一化裁切：上下留出空间后统一缩放到固定尺寸，便于按像素比较
    y0 = max(0, int(top - 2.6 * space))
    y1 = min(img.height, int(bottom + 2.6 * space))
    crop = img.crop((max(0, x_start), y0, min(img.width, x_end), y1)).convert('L')
    crop = crop.resize((320, 170), Image.LANCZOS)
    a = 255.0 - np.asarray(crop, dtype=np.float32)
    a = a - a.mean()
    n = np.linalg.norm(a)
    return a / (n if n > 1e-6 else 1.0)


def main():
    spec = json.load(open(sys.argv[1], encoding='utf-8'))
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.55
    vecs = []
    labels = []
    for one in spec['systems']:
        img = Image.open(one['file'])
        bars = one['bars']
        top = one['staff'][0] * 2
        bottom = one['staff'][-1] * 2
        space = (bottom - top) / 4.0
        for i in range(len(bars) - 1):
            vecs.append(bar_vector(img, bars[i], bars[i + 1], top, bottom, space))
            labels.append((one['index'], i + 1))
    n = len(vecs)
    clusters = []
    assigned = [None] * n
    for i in range(n):
        if assigned[i] is not None:
            continue
        members = [i]
        assigned[i] = len(clusters)
        for j in range(i + 1, n):
            if assigned[j] is not None:
                continue
            if float(np.dot(vecs[i], vecs[j])) > threshold:
                assigned[j] = len(clusters)
                members.append(j)
        clusters.append(members)
    print('总小节数: %d, 聚成 %d 类 (阈值 %.2f)' % (n, len(clusters), threshold))
    for k, m in enumerate(clusters):
        if len(m) >= 2:
            names = ['系统%d-第%d小节' % labels[i] for i in m[:14]]
            print('类%d: %d 个相同 -> %s%s' % (k + 1, len(m), ', '.join(names), ' ...' if len(m) > 14 else ''))
        else:
            print('类%d: 独一份 -> 系统%d-第%d小节' % (k + 1, labels[m[0]][0], labels[m[0]][1]))
    json.dump({'labels': labels, 'clusters': clusters}, open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写出:', sys.argv[3])


if __name__ == '__main__':
    main()
