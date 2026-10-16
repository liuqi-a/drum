# 用途：对原曲做分频段起音检测，量化到 16 分网格，逐小节输出鼓组演奏格（用于与纸谱对照）
import subprocess
import sys

import numpy as np

FFMPEG = subprocess.run([sys.executable, '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True).stdout.strip()


def load(path, sr=22050):
    cmd = [FFMPEG, '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, dtype=np.float32), sr


def spec_flux(x, sr, bands, n=1024, hop=128):
    win = np.hanning(n)
    frames = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * win, axis=1))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    out = {}
    for name, (lo, hi) in bands.items():
        sel = (freqs >= lo) & (freqs < hi)
        e = np.log1p(spec[:, sel].sum(axis=1))
        d = np.maximum(np.diff(e, prepend=e[:1]), 0)
        out[name] = d
    return out, hop / float(sr)


def peaks(env, dt, thr_ratio=0.30, min_gap=0.05):
    if env.max() <= 0:
        return np.array([])
    thr = env.max() * thr_ratio
    res = []
    i = 0
    gap = int(min_gap / dt)
    while i < len(env):
        if env[i] > thr:
            j = i
            while j < len(env) and env[j] > thr:
                j += 1
            k = i + int(np.argmax(env[i:j]))
            if not res or k - res[-1] >= gap:
                res.append(k)
            i = j
        else:
            i += 1
    return np.array(res) * dt


def main():
    path = sys.argv[1]
    bpm = float(sys.argv[2]) if len(sys.argv) > 2 else 106.0
    bar_from = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    bar_to = int(sys.argv[4]) if len(sys.argv) > 4 else 16
    x, sr = load(path)
    bands = {'kick': (35, 110), 'snare': (1000, 4000), 'hihat': (6000, 12000)}
    envs, dt = spec_flux(x, sr, bands)
    hits = {}
    for name, e in envs.items():
        hits[name] = peaks(e, dt)
    bar_dur = 240.0 / bpm
    step = 60.0 / bpm / 4.0
    all_pts = np.concatenate([hits[n] for n in hits])
    best = (1e9, 0.0)
    for ph in np.arange(0, step, 0.002):
        err = np.abs((all_pts - ph) / step - np.round((all_pts - ph) / step))
        if err.mean() < best[0]:
            best = (err.mean(), float(ph))
    phase = best[1]
    print('相位 %.3f 秒（平均网格偏差 %.3f 格），速度 %.2f BPM，每小节 %.3f 秒' % (phase, best[0], bpm, bar_dur))
    for bar in range(bar_from, bar_to + 1):
        t0 = phase + (bar - 1) * bar_dur
        t1 = t0 + bar_dur
        row = {}
        for name in ('kick', 'snare', 'hihat'):
            pts = hits[name][(hits[name] >= t0 - step / 2) & (hits[name] < t1 - step / 2)]
            idxs = sorted(set(int(round((p - t0) / step)) for p in pts))
            row[name] = [i for i in idxs if 0 <= i < 16]
        cells = []
        for i in range(16):
            tags = []
            if i in row['kick']:
                tags.append('K')
            if i in row['snare']:
                tags.append('S')
            if i in row['hihat']:
                tags.append('h')
            cells.append(''.join(tags) if tags else ' .')
        print('第%2d小节: %s' % (bar, ' '.join(cells)))


if __name__ == '__main__':
    main()
