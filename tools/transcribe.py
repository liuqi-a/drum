# 用途：从原曲音频逐小节测出鼓点（底鼓/军鼓/踩镲/镲片），并输出乐谱数据 JSON
import json
import subprocess
import sys

import numpy as np

FFMPEG = subprocess.run([sys.executable, '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True).stdout.strip()
BPM = 106.0
PHASE = 0.044


def load(path, sr=22050):
    cmd = [FFMPEG, '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, dtype=np.float32), sr


def analyse(x, sr, n=1024, hop=128):
    win = np.hanning(n)
    frames = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * win, axis=1))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    dt = hop / float(sr)
    bands = {'low': (30, 150), 'mid': (150, 600), 'hi': (2500, 7000), 'top': (6500, 12000)}
    be = {}
    for k, (lo, hi) in bands.items():
        sel = (freqs >= lo) & (freqs < hi)
        be[k] = np.log1p(spec[:, sel].sum(axis=1))
    full = np.log1p(spec[:, (freqs >= 200) & (freqs < 8000)].sum(axis=1))
    flux = np.maximum(np.diff(full, prepend=full[:1]), 0)
    return spec, freqs, be, flux, dt


def onsets(flux, dt, thr_ratio=0.22, min_gap=0.055):
    thr = flux.max() * thr_ratio
    res, i = [], 0
    gap = int(min_gap / dt)
    while i < len(flux):
        if flux[i] > thr:
            j = i
            while j < len(flux) and flux[j] > thr:
                j += 1
            k = i + int(np.argmax(flux[i:j]))
            if not res or k - res[-1] >= gap:
                res.append(k)
            i = j
        else:
            i += 1
    return np.array(res)


def main():
    path, out_json = sys.argv[1], sys.argv[2]
    x, sr = load(path)
    spec, freqs, be, flux, dt = analyse(x, sr)
    idx = onsets(flux, dt)
    step = 60.0 / BPM / 4.0
    bar_dur = step * 16
    bars = {}
    for i in idx:
        t = i * dt
        # 用起音前后 30ms 的频段能量差做分类
        a, b = max(0, i - 2), min(len(flux), i + 3)
        d_low = float(be['low'][b] - be['low'][a])
        d_mid = float(be['mid'][b] - be['mid'][a])
        d_hi = float(be['hi'][b] - be['hi'][a])
        d_top = float(be['top'][b] - be['top'][a])
        kind = 'hat'
        if d_low > max(d_mid, d_hi, d_top) * 0.9:
            kind = 'kick'
        elif d_mid + d_hi > (d_top + d_low) * 1.1:
            kind = 'snare'
        pos = int(round((t - PHASE) / step))
        if pos < 0:
            continue
        bar = pos // 16 + 1
        slot = pos % 16
        bars.setdefault(bar, {'kick': [], 'snare': [], 'hat': []})[kind].append(slot)
    for k in bars:
        for drum in bars[k]:
            bars[k][drum] = sorted(set(bars[k][drum]))
    print('检测到有内容的小节数:', len(bars), '总小节(按音频长度):', int((len(x) / sr - PHASE) / bar_dur) + 1)
    for bar in range(1, 86):
        row = bars.get(bar, {'kick': [], 'snare': [], 'hat': []})
        cells = []
        for s in range(16):
            tags = ''
            if s in row['kick']:
                tags += 'K'
            if s in row['snare']:
                tags += 'S'
            if s in row['hat']:
                tags += 'h'
            cells.append(tags if tags else ' .')
        print('%2d: %s' % (bar, ' '.join(cells)))
    json.dump({'bpm': BPM, 'phase': PHASE, 'bars': bars}, open(out_json, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print('已写出:', out_json)


if __name__ == '__main__':
    main()
