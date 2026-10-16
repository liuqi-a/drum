# 用途：用长时段梳状匹配精修速度与首拍相位（对同步至关重要）
import subprocess
import sys

import numpy as np

FFMPEG = subprocess.run([sys.executable, '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True).stdout.strip()


def load(path, sr=22050):
    cmd = [FFMPEG, '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, dtype=np.float32), sr


def onset_env(x, sr, n=1024, hop=128):
    win = np.hanning(n)
    frames = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * win, axis=1))
    spec = np.log1p(spec)
    flux = np.maximum(np.diff(spec, axis=0), 0).sum(axis=1)
    flux = np.concatenate([[0], flux])
    return flux, hop / float(sr)


def main():
    path = sys.argv[1]
    t0, t1 = float(sys.argv[2]), float(sys.argv[3])
    x, sr = load(path)
    env, dt = onset_env(x, sr)
    env = env - env.mean()
    i0, i1 = int(t0 / dt), int(t1 / dt)
    seg = env[i0:i1]
    results = []
    for bpm in np.arange(100.0, 112.0, 0.01):
        period = 60.0 / bpm / dt
        k = np.arange(0, max(1, int(len(seg) / period) - 1))
        base = (k * period).astype(int)
        top = -1e18
        for off in range(0, int(period), 5):
            ii = base + off
            ii = ii[ii < len(seg)]
            s = float(seg[ii].sum())
            if s > top:
                top = s
        results.append((top, bpm))
    results.sort(reverse=True)
    print('速度候选（梳状匹配得分）:')
    for s, bpm in results[:8]:
        print('  BPM %.2f  小节度 %.4f 秒  得分 %.0f' % (bpm, 60.0 / bpm * 4, s))
    top_bpm = results[0][1]
    period = 60.0 / top_bpm / dt
    scores = []
    for o in range(int(period)):
        ii = (np.arange(0, max(1, int(len(seg) / period) - 1)) * period).astype(int) + o
        ii = ii[ii < len(seg)]
        scores.append(float(seg[ii].sum()))
    best_off = int(np.argmax(scores))
    print('精确速度 %.2f BPM, 首拍相位 %.3f 秒' % (top_bpm, t0 + best_off * dt))


if __name__ == '__main__':
    main()
