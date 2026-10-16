# AGENTS.md —— 动态鼓谱（drum）

本项目把歌曲做成「动态鼓谱」视频：**固定版式的鼓谱 + 竖直播放光标逐行扫过 + 命中音符变蓝高亮 + 与音频严格同步**。
参考形态来自 B 站 UP 主「罗曼音乐_Roman_Music」的动态鼓谱视频。

## 动手前必读（按顺序）

1. 本文件：项目级约定、工具链现状、已知陷阱。
2. `docs/动态鼓谱-技术笔记.md`：**唯一的技术决策记录**。已实测的客观参数、三条渲染路线的取舍、待定问题都在里面。它的结论可直接引用，不要凭肉眼重新测一遍。
3. 改动落在 `videos/demo-drum-score/` 时，**先读该子目录的 `AGENTS.md`**：那是 HyperFrames 合成工程，规则更严，且子目录说明优先于本文件。

## 目录地图

| 路径 | 职责 |
| --- | --- |
| `docs/动态鼓谱-技术笔记.md` | 技术笔记与决策基线（版式实测、路线对比、下一步） |
| `refs/video`、`refs/audio`、`refs/hq` | 参考视频与原曲音频，命名形如 `BV1MisVzYERQ.f30032.mp4`（f 后为 B 站清晰度流 id） |
| `refs/frames`、`refs/hq/frames`、`refs/score` | 抽帧与谱面截图，是「读谱」的客观证据来源 |
| `refs/*.ps1` | 素材获取与探测脚本：`download.ps1`（下载）、`frames.ps1`（抽帧）、`probe*.ps1` |
| `refs/drums_default.json` | MuseScore 默认鼓组映射表（音高 / 符头 / 谱表位置） |
| `score/*.json` | 谱面数据，自研十六分格格式（见下方「数据格式约定」） |
| `tools/*.py` | 全部分析与生成脚本（读谱、测速、追光标、生成 mscx、合成音频） |
| `tools/ms4/` | MuseScore Studio 4.7.5 便携版：`tools/ms4/MuseScore 4/bin/MuseScore4.exe` |
| `.tools/` | 本地依赖：ffmpeg 压缩包、vendored node 模块 |
| `videos/demo-drum-score/` | HyperFrames 视频工程（`index.html` + `assets/`），带独立 `AGENTS.md` |

## 工具链现状（已实测）

| 工具 | 状态 |
| --- | --- |
| Python | 3.14.7；`numpy` / `soundfile` / `Pillow` / `cv2` / `pymupdf` / `imageio-ffmpeg` / `yt-dlp` 已装；`librosa` **未装**（现有脚本不需要它，别为它引入依赖） |
| ffmpeg | 7.1，**不在 PATH**，必须先把路径取出来传给脚本 |
| MuseScore | 便携版 `tools/ms4/MuseScore 4/bin/MuseScore4.exe`，命令行形如 `MuseScore4.exe -o out.svg in.mscz` |
| Node / npm | v24.21.0 / 11.19.0 |
| HyperFrames CLI | 由 `package.json` 固定 `hyperframes@0.8.156`；升级前先跑 `npx hyperframes@latest upgrade --project . --check`（只读探测） |

几乎每个 `tools/*.py` 的**第一个参数都是 ffmpeg 可执行文件路径**，统一这样取：

```powershell
# 取出 ffmpeg 的真实路径，后面所有分析脚本的第一个参数都用它
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
```

## 常用命令

```powershell
# 参考素材：下载三部参考视频的低码率版本（脚本内硬编码了项目根路径）
powershell -File refs/download.ps1
# 按时间点抽帧，产出 refs/frames 下的截图，供读谱与版式测量
powershell -File refs/frames.ps1
```

```powershell
# 测真实 BPM 与鼓组首次进入点
python tools/ref_tempo.py $ff "refs/hq/BV1MisVzYERQ.f30280.m4a" 0 30
# 逐帧追踪蓝色播放光标，反推小节原点与速度
python tools/ref_cursor.py $ff "refs/video/BV1MisVzYERQ.f30032.mp4" 1 12 0.1
# 谱面几何（五线谱行 / 小节线 x）+ 音频十六分网格对齐
python tools/ref_analyze.py $ff "refs/hq/frames/hq_t1.png" "refs/hq/BV1MisVzYERQ.f30280.m4a" 100 1.0
# 机器识谱：符头检测后映射到小节内的十六分格子
python tools/ref_notes.py $ff "refs/hq/frames/rd_bar3.png"
# 从原曲音频逐小节测鼓点，输出谱面 JSON
python tools/transcribe.py "refs/hq/BV1MisVzYERQ.f30280.m4a" "score/out.json"
```

```powershell
# 谱面生产：JSON → MuseScore .mscx（参数顺序：音符 JSON、鼓组映射、输出 mscx）
python tools/build_lvguang.py "score/lvguang.json"
python tools/make_mscx.py "score/lvguang.json" "refs/drums_default.json" "score/lvguang.mscx"
# 导出成图或矢量（-r 提高 PNG 分辨率，-T 裁掉四周空白）
& "tools/ms4/MuseScore 4/bin/MuseScore4.exe" -r 300 -T 10 -o "score/lvguang.png" "score/lvguang.mscx"
```

```powershell
# 视频合成链路（在子工程目录里执行，全部走固定版本 CLI）
Set-Location videos/demo-drum-score
npm run check      # 必须跑：lint + 运行时 + 版式 + 动作 + 对比度，一把过
npx hyperframes preview --background   # 给用户看画面的持久预览，别用 npm run dev 后台包装
npm run render     # 渲染 MP4
```

## 数据格式约定

```jsonc
// score/*.json：每个乐器用 16 个字符描述一小节的十六分网格，'x' 命中、'.' 休止
{
  "bpm": 92,              // 速度
  "beatsPerBar": 4,       // 每小节拍数
  "patterns": {
    "A": {
      "hh":    "x.x.x.x.x.x.x.x.",   // 踩镲
      "snare": "....x.......x...",   // 军鼓
      "kick":  "x.......x.x....."    // 底鼓
    }
  },
  "arrangement": [{ "bar": 1, "pattern": "A", "crash": true }]
}
```

- **音频与谱面必须同源**：`tools/build_score.py` 从同一份网格同时产出 `assets/bgm.wav|mp3` 和 `assets/score-data.js`，因此光标与声音天生同步、没有对轴误差。任何情况下都不要让两条产物分别生成。
- `videos/demo-drum-score/assets/score-data.js` 由脚本生成，首行写明「自动生成，请勿手改」——要改数据就改上游 JSON 再重跑脚本。
- 谱面坐标换算一律走「拍号 + BPM」，别写死秒数：`tSec = (bar - 1) * beatsPerBar * (60 / bpm) + beat * (60 / bpm)`。
- 鼓件到谱表位置的映射是 `tools/make_mscx.py` 的 `POS_OF_PITCH` / `STAFF_MAP`，新增鼓件先改这两处。

## 硬约束

**HyperFrames 合成（`videos/demo-drum-score/` 内）**

- 确定性是底线：禁止 `Date.now()`、`Math.random()`、网络请求、输入状态；同一时间点重复渲染必须得到同一帧。
- 每个合成只注册**一个暂停的根时间轴**，键名必须等于根节点的 `data-composition-id`：

```js
// 注册唯一根时间轴；键名与根节点 data-composition-id 完全一致，多余的时间轴会破坏 seek
window.__timelines["main"] = gsap.timeline({ paused: true });
```

- 手动加进根时间轴的场景时间轴**不能再 paused**（父级被 seek 时不会推进子级）。
- 不要对 `class="clip"` 的元素 tween `display` / `visibility` / `autoAlpha`，要动就动子节点；也别用 CSS `transform` 设初值后又让 GSAP 动同一属性（会触发 `gsap_css_transform_conflict`）。
- **改完必须跑 `npm run check`**，错误清零、警告过目后才能算完成。
- 查文档不要猜 URL：用 `npx hyperframes docs <topic>`（离线）或 `https://hyperframes.heygen.com/llms.txt`。
- 官方 registry 里**没有乐谱类素材块**（以 music notation 检索返回空），谱面必须自己造。

**通用**

- **编制/渲染完成必须把成片 MP4 复制到用户桌面**（与 `refs/out/` 同名文件一份）。`tools/render_full.py` 已内置 `save_to_desktop`；若走其它渲染脚本或 HyperFrames `npm run render`，收尾同样要拷一份到桌面并告知路径。
- `refs/*.ps1` 里**硬编码了项目绝对路径**，搬动项目目录后这些脚本会失效，需要用变量或相对路径重写。
- 大体积素材（`tools/ms4/*.msi` 约 128MB、参考视频/音频）属于本地资产，不要重命名或重排结构，也不要当源码处理。
- 参考视频的机制是「**固定版式内光标扫行后跳到下一行行首**」，不是连续横向滚动；实现时不要做滚动。

## 已知陷阱（踩过的）

- **音频推断会被污染**：鼓组尚未进入的小节里，分频段检测会把大乐器和人声当成鼓。**谱面图是唯一权威依据，音频只用来校验时间轴**。
- `tools/ref_notes.py` 的鼓件行 y 范围只标定了一部分，曾有「底鼓行检不出」的记录；改识别逻辑前先确认标定值，并对着 `refs/hq/frames/rd_bar3.png`、`rd_bar456.png`、`rd_bar78.png` 复核。
- 音源是 B 站上限的 **67 kbps AAC**：做鼓声增强会把底噪与编码伪影一起抬起来。要正式出品就换更高品质来源。
- `tools/synth.py` 在笔记里被引用过，但该文件从未存在。
- MuseScore 出谱时记得用 `-T` 裁边、`-r` 提分辨率，否则做视频素材时四周留白与清晰度都不够。

## 当前进度（以笔记 §7 为准）

两条线并行，动手前先扫一眼 `tools/` 与 `score/` 里**最新修改的文件**，确认此刻在跑哪条：

- demo 引擎线：8 小节小样打通「谱面 + 光标扫行 + 命中高亮 + 音频」整条管线，已产出 `videos/demo-drum-score/`。
- 全曲数据线：`tools/build_lvguang.py` → `tools/make_mscx.py` → MuseScore 导出，把整首歌（85 小节）的鼓谱数据生成出来。

笔记 §7.6 列出的下一步（标定鼓件行 → 人工复核识谱结果 → 产出小节数据 → 音频鼓声增强 → 定稿渲染路线 → 搭合成）仍是有序待办。

## 工作守则

1. 先读笔记再动手；实测与笔记冲突时以实测为准，并把新结论写回笔记（笔记是长期记忆，聊天记录不是）。
2. 客观证据优先：能脚本量出来的（BPM、小节线 x、光标位置）就不要肉眼判断；反过来，音频推断与谱面对不上时相信谱面。
3. 小步验证：一次只动一条链路（读谱 / 谱面生产 / 视频合成），改完立刻跑对应检查，再往下走。
4. 新增脚本沿用现有风格：文件头 `# 用途：…` 抬头注释 + 中文注释，命令行参数走 `sys.argv`（不要引 argparse 以外的重依赖）。
5. 全程简体中文回复；路径、命令、标识符、日志保持原文不翻译。
