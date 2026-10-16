# 用途：分析原曲音频，估计速度并对底鼓/军鼓/踩镲做分频段起音检测，用于校核鼓谱
import subprocess
import sys

import numpy as np

FFMPEG = subprocess.run([sys.executable, '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True).stdout.strip()


def load_audio(path, sr=22050):
    # 用 ffmpeg 解码成单声道 float32 PCM
    cmd = [FFMPEG, '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def stft(x, n=1024, hop=256):
    win = np.hanning(n)
    frames = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.fft.rfft(x[idx] * win, axis=1)
    return np.abs(spec), hop, n


def band_flux(spec, freqs, lo, hi):
    # 某频段的谱通量（只保留增加量），用来找该鼓件的击打点
    sel = (freqs >= lo) & (freqs < hi)
    e = spec[:, sel].sum(axis=1)
    e = np.log1p(e)
    d = np.diff(e, prepend=e[:1])
    return np.maximum(d, 0)


def pick_peaks(env, hop, sr, thr_ratio=0.35, min_gap=0.09):
    if env.max() <= 0:
        return np.array([])
    thr = env.max() * thr_ratio
    gap = int(min_gap * sr / hop)
    peaks = []
    i = 0
    while i < len(env):
        if env[i] > thr:
            j = i
            while j < len(env) and env[j] > thr:
                j += 1
            k = i + int(np.argmax(env[i:j]))
            if not peaks or k - peaks[-1] >= gap:
                peaks.append(k)
            i = j
        else:
            i += 1
    return np.array(peaks) * hop / float(sr)


def main():
    path = sys.argv[1]
    x, sr = load_audio(path)
    print('时长 %.1f 秒, 采样率 %d' % (len(x) / sr, sr))
    spec, hop, n = stft(x)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    full = band_flux(spec, freqs, 30, 12000)
    env = full - full.mean()
    ac = np.correlate(env, env, 'full')[len(env) - 1:]
    cand = []
    for bpm in np.arange(60, 180, 0.25):
        lag = 60.0 / bpm * sr / hop
        i = int(round(lag))
        if i < len(ac):
            cand.append((ac[i] + (ac[2 * i] if 2 * i < len(ac) else 0) * 0.5, bpm))
    cand.sort(reverse=True)
    top = ['%.2f (score %.0f)' % (b, s) for s, b in cand[:6]]
    print('速度候选:', top)
    bands = [('kick 40-110Hz', 40, 110), ('snare 150-400Hz', 150, 400), ('hihat 6k-12kHz', 6000, 12000)]
    for name, lo, hi in bands:
        e = band_flux(spec, freqs, lo, hi)
        t = pick_peaks(e, hop, sr)
        head = np.round(t[t < 30], 2).tolist()
        print('%s 击打点 %d 个; 前30秒: %s' % (name, len(t), head))


if __name__ == '__main__':
    main()
