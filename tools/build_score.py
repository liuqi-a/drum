#!/usr/bin/env python3
# 用途：把 score/groove.json 的鼓点网格编译成两样东西——
#   1) 与鼓点严格对齐的音频 assets/bgm.wav / bgm.mp3（用 numpy 合成底鼓/军鼓/镲/通鼓）
#   2) 谱面数据 assets/score-data.js（每小节两个声部的音符与休止，供页面用 VexFlow 排版）
# 因为音频和谱面出自同一份网格，所以「动态鼓谱」的光标与声音天生同步，不存在对轴误差。

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100  # 采样率

# 乐器 -> 五线谱位置 / 声部 / 声像。voice 1 符干朝上（镲、军鼓、通鼓），voice 2 符干朝下（底鼓）
STAFF_MAP = {
    "hh":     {"key": "g/5/x2", "voice": 1, "pan": 0.22, "gain": 0.42},
    "ride":   {"key": "f/5/x2", "voice": 1, "pan": 0.30, "gain": 0.40},
    "crash":  {"key": "a/5/x2", "voice": 1, "pan": -0.30, "gain": 0.34},
    "snare":  {"key": "c/5",   "voice": 1, "pan": -0.10, "gain": 0.85},
    "snare2": {"key": "c/5",   "voice": 1, "pan": -0.10, "gain": 0.85},
    "tom1":   {"key": "e/5",   "voice": 1, "pan": -0.26, "gain": 0.70},
    "tom2":   {"key": "d/5",   "voice": 1, "pan": -0.05, "gain": 0.70},
    "floor":  {"key": "a/4",   "voice": 1, "pan": 0.12, "gain": 0.72},
    "kick":   {"key": "f/4",   "voice": 2, "pan": 0.00, "gain": 1.00},
}

# VexFlow 时值串：q=四分, 8=八分, 16=十六分, 8d=附点八分, 后缀 r 表示休止


def exp_env(n, tau):
    """指数衰减包络，n 为样本数，tau 为时间常数（秒）。"""
    return np.exp(-np.arange(n) / SR / tau)


def synth_kick():
    """底鼓：正弦波频率快速下坠 + 短促噪声击点，得到厚实的低频冲击。"""
    n = int(0.60 * SR)
    t = np.arange(n) / SR
    freq = 48.0 + 110.0 * np.exp(-t / 0.030)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * exp_env(n, 0.20)
    rng = np.random.default_rng(11)
    click = rng.normal(0, 1, n) * exp_env(n, 0.004) * 0.22
    return (body + click) * 1.0


def synth_snare():
    """军鼓：高通白噪声（响弦）+ 190Hz 鼓腔音，噪声衰减略慢于音高。"""
    n = int(0.35 * SR)
    rng = np.random.default_rng(23)
    noise = rng.normal(0, 1, n)
    hp = noise - np.concatenate(([0.0], noise[:-1]))
    tone = np.sin(2 * np.pi * 190.0 * np.arange(n) / SR)
    return hp * exp_env(n, 0.105) * 0.95 + tone * exp_env(n, 0.055) * 0.45


def synth_hat(open_hat=False):
    """踩镲：二阶差分的白噪声即高频，闭合用极短衰减，打开则拉长尾巴。"""
    tau = 0.070 if open_hat else 0.024
    n = int((0.55 if open_hat else 0.18) * SR)
    rng = np.random.default_rng(37)
    noise = rng.normal(0, 1, n)
    hp = np.diff(noise, prepend=0.0)
    hp = np.diff(hp, prepend=0.0)
    return hp * exp_env(n, tau) * 0.55


def synth_ride():
    """叮叮镲：噪声加一点固定音高，衰减比踩镲长，音色偏亮。"""
    n = int(1.10 * SR)
    rng = np.random.default_rng(41)
    noise = rng.normal(0, 1, n)
    hp = np.diff(noise, prepend=0.0)
    ping = np.sin(2 * np.pi * 1180.0 * np.arange(n) / SR)
    return hp * exp_env(n, 0.30) * 0.34 + ping * exp_env(n, 0.10) * 0.12


def synth_crash():
    """吊镲：长衰减的高频噪声，用来标出段落开头。"""
    n = int(1.90 * SR)
    rng = np.random.default_rng(53)
    noise = rng.normal(0, 1, n)
    hp = np.diff(noise, prepend=0.0)
    return hp * exp_env(n, 0.75) * 0.40


def synth_tom(f0):
    """通鼓：正弦波轻微下坠，衰减中等，按基频区分高/中/落地通鼓。"""
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    freq = f0 * (1.0 + 0.22 * np.exp(-t / 0.035))
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * exp_env(n, 0.170) * 0.85


VOICES = {
    "kick": synth_kick,
    "snare": synth_snare,
    "snare2": synth_snare,
    "hh": lambda: synth_hat(False),
    "hho": lambda: synth_hat(True),
    "ride": synth_ride,
    "crash": synth_crash,
    "tom1": lambda: synth_tom(210.0),
    "tom2": lambda: synth_tom(165.0),
    "floor": lambda: synth_tom(112.0),
}


def expand(arrangement, patterns):
    """把编排展开为逐小节的 {instrument: 16 格命中掩码} 结构。"""
    bars = []
    for item in arrangement:
        pat = dict(patterns[item["pattern"]])
        if item.get("crash"):
            pat["crash"] = "x..............."
        slots = {}
        for inst, grid in pat.items():
            if inst not in STAFF_MAP:
                raise SystemExit(f"未知乐器：{inst}")
            if len(grid) != 16:
                raise SystemExit(f"{inst} 的网格长度必须是 16，当前为 {len(grid)}")
            for i, ch in enumerate(grid):
                if ch != ".":
                    slots.setdefault(i, []).append(inst)
        bars.append({"bar": item["bar"], "slots": slots})
    return bars


def hit_times(bars, beat_sec):
    """列出每一击的绝对时间（秒），用于合成音频。"""
    hits = []
    for bi, bar in enumerate(bars):
        bar_t = bi * 4 * beat_sec
        for slot in sorted(bar["slots"]):
            for inst in bar["slots"][slot]:
                hits.append((bar_t + slot * beat_sec / 4.0, inst))
    return sorted(hits)


def render_audio(hits, total_sec, out_wav):
    """把每一击叠加进立体声缓冲，再加一点早期反射模拟房间感。"""
    n_total = int(round(total_sec * SR))  # 严格按「音乐长度 + 尾巴」分配采样数，不留多余静音
    mix = np.zeros((n_total, 2), dtype=np.float64)
    cache = {}
    for t, inst in hits:
        if inst not in cache:
            cache[inst] = VOICES[inst]()
        smp = cache[inst]
        meta = STAFF_MAP[inst]
        start = int(t * SR)
        end = min(start + len(smp), n_total)
        seg = smp[: end - start] * meta["gain"]
        pan = meta["pan"]
        gl = np.sqrt((1.0 - pan) / 2.0)
        gr = np.sqrt((1.0 + pan) / 2.0)
        mix[start:end, 0] += seg * gl * 1.414
        mix[start:end, 1] += seg * gr * 1.414
    # 早期反射：几组不同延迟的复制，制造轻微空间感而不糊掉瞬态
    wet = mix.copy()
    for delay_ms, gain, spread in ((13, 0.16, 7), (23, 0.12, 11), (37, 0.09, 17), (53, 0.06, 23)):
        d = int(delay_ms / 1000.0 * SR)
        s = int(spread / 1000.0 * SR)
        wet[d:, 0] += mix[:-d, 1] * gain
        wet[d + s:, 1] += mix[: -d - s, 0] * gain
    mix = mix * 0.86 + wet * 0.34
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = mix / peak * 1.15
    mix = np.tanh(mix * 0.92) * 0.94  # 软削波，避免削顶失真
    sf.write(out_wav, mix.astype(np.float32), SR, subtype="PCM_16")


def decompose(slots_bool):
    """把一个声部在某一拍内的 4 个 16 分格拆成尽量大的时值（音符或休止）。"""
    out = []
    i = 0
    while i < 4:
        nxt = next((j for j in range(i + 1, 4) if slots_bool[j]), 4)
        run = nxt - i
        if slots_bool[i]:
            out.append(("8d" if run == 3 else {1: "16", 2: "8", 4: "q"}[run], i, True))
            i += run
        else:
            if run >= 4:
                out.append(("qr", i, False))
                i += 4
            elif run == 3:
                out.append(("8r", i, False))
                out.append(("16r", i + 2, False))
                i += 3
            elif run == 2:
                out.append(("8r", i, False))
                i += 2
            else:
                out.append(("16r", i, False))
                i += 1
    return out


def bar_to_voices(bar):
    """把一小节的命中掩码按声部整理成 VexFlow 需要的音符 token 列表。"""
    per_voice = {1: [False] * 16, 2: [False] * 16}
    keys = {1: [None] * 16, 2: [None] * 16}
    insts = {1: [None] * 16, 2: [None] * 16}
    for slot, items in bar["slots"].items():
        for inst in items:
            meta = STAFF_MAP[inst]
            v = meta["voice"]
            per_voice[v][slot] = True
            keys[v][slot] = (keys[v][slot] or []) + [meta["key"]]
            insts[v][slot] = (insts[v][slot] or []) + [inst]
    result = {}
    for v in (1, 2):
        tokens = []
        for beat in range(4):
            chunk = per_voice[v][beat * 4:(beat + 1) * 4]
            for dur, off, hit in decompose(chunk):
                slot = beat * 4 + off
                token = {"s": slot, "d": dur, "hit": bool(hit)}
                if hit:
                    token["keys"] = sorted(keys[v][slot], key=lambda k: _pitch_rank(k))
                    token["insts"] = insts[v][slot]
                else:
                    token["keys"] = ["b/4" if v == 1 else "d/4"]
                tokens.append(token)
        result[v] = tokens
    return result


def _pitch_rank(key):
    """把 VexFlow 的 key（如 g/5/x2）折算成可排序的音高序号，保证和弦内音从低到高排列。"""
    name, octave = key.split("/")[0], int(key.split("/")[1])
    order = {"c": 0, "d": 1, "e": 2, "f": 3, "g": 4, "a": 5, "b": 6}
    return octave * 7 + order[name]


def ffmpeg_bin():
    """优先用工作区内的 ffmpeg，找不到再退回 PATH。"""
    local = Path(__file__).resolve().parents[1] / ".tools" / "ffbin" / "bin" / "ffmpeg.exe"
    if local.exists():
        return str(local)
    return "ffmpeg"


def main():
    root = Path(__file__).resolve().parents[1]
    proj = root / "videos" / "demo-drum-score"
    assets = proj / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    cfg = json.loads((root / "score" / "groove.json").read_text(encoding="utf-8"))
    beat_sec = 60.0 / cfg["bpm"]
    bars = expand(cfg["arrangement"], cfg["patterns"])
    music_sec = len(bars) * cfg["beatsPerBar"] * beat_sec
    total_sec = music_sec + cfg.get("tailSec", 1.0)

    hits = hit_times(bars, beat_sec)
    wav = assets / "bgm.wav"
    render_audio(hits, total_sec, wav)

    mp3 = assets / "bgm.mp3"
    subprocess.run(
        [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav),
         "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)],
        check=True,
    )

    # 生成谱面数据：每小节两个声部的 token 序列 + 每小节起始时间
    out_bars = []
    for bi, bar in enumerate(bars):
        voices = bar_to_voices(bar)
        out_bars.append({
            "index": bar["bar"],
            "t0": round(bi * cfg["beatsPerBar"] * beat_sec, 6),
            "v1": voices[1],
            "v2": voices[2],
        })

    payload = {
        "meta": {
            "title": cfg["title"],
            "subtitle": cfg["subtitle"],
            "bpm": cfg["bpm"],
            "beatsPerBar": cfg["beatsPerBar"],
            "beatUnit": cfg["beatUnit"],
            "barsPerSystem": cfg.get("barsPerSystem", 2),
            "beatSec": round(beat_sec, 6),
            "musicSec": round(music_sec, 6),
            "durationSec": round(total_sec, 6),
            "bars": len(bars),
        },
        "bars": out_bars,
    }
    data_js = proj / "assets" / "score-data.js"
    data_js.write_text(
        "// 由 tools/build_score.py 自动生成，请勿手改\nwindow.SCORE = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(f"bars={len(bars)} music={music_sec:.3f}s total={total_sec:.3f}s hits={len(hits)}")
    print(f"wav={wav} mp3={mp3} data={data_js}")


if __name__ == "__main__":
    main()
