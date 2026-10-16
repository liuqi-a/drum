# 用途：比较各条已拉平谱行之间的相似度，找出重复段落，减少需要精读的行数
import glob
import os
import sys

import numpy as np
from PIL import Image


def vector(path, staff):
    img = Image.open(path).convert('L')
    a = np.asarray(img, dtype=np.float32)
    top, bottom = staff[0], staff[-1]
    space = (bottom - top) / 4.0
    y0 = max(0, int(top - 3.2 * space))
    y1 = min(a.shape[0], int(bottom + 3.2 * space))
    crop = Image.fromarray(a[y0:y1].astype(np.uint8)).resize((640, 120), Image.LANCZOS)
    v = 255.0 - np.asarray(crop, dtype=np.float32)
    v = v - v.mean()
    v = v.ravel()
    n = np.linalg.norm(v)
    return v / (n if n > 1e-6 else 1.0)


def main():
    spec_dir = sys.argv[1]
    import json
    spec = json.load(open(os.path.join(spec_dir, 'spec.json'), encoding='utf-8'))
    names, vecs, info = [], [], []
    for s in spec['systems']:
        names.append('p%d-行%d' % (s['page'], s['index']))
        vecs.append(vector(s['file'], [v * 2 for v in s['staff']]))
        info.append(s)
    n = len(vecs)
    sim = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            sim[i, j] = float(np.dot(vecs[i], vecs[j]))
    print('谱行两两相似度（>0.5 视为高度重复）:')
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(' -- ')
            else:
                row.append('%4.2f' % sim[i, j])
        print('%8s %s' % (names[i], ' '.join(row)))
    print()
    for i in range(n):
        same = [names[j] for j in range(n) if j != i and sim[i, j] > 0.5]
        if same:
            print('%s 与以下高度相似: %s' % (names[i], ', '.join(same)))


if __name__ == '__main__':
    main()
