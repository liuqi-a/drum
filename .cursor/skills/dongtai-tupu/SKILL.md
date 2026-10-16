---
name: dongtai-tupu
description: >-
  动态图谱（动态鼓谱）视频编制流程：PDF/MuseScore 谱面 + 播放光标扫行 + 音频同步 + 片头倒数，
  输出 MP4 并复制到桌面。在用户提到动态鼓谱、动态图谱、鼓谱视频、光标扫谱、render_full、
  绿光鼓谱，或要做/改/渲这类视频时使用。
---

# 动态图谱

把歌曲做成「动态鼓谱」视频：固定版式谱面 + 竖直播放光标逐行扫过 + 与音频同步。  
本 skill 名称：**动态图谱**。作业目录默认为本机 `drum` 工程（含 `AGENTS.md`、`tools/render_full.py`）。

## 动手前（必读顺序）

1. 工程根 `AGENTS.md`
2. `docs/动态鼓谱-技术笔记.md`（实测参数与路线结论，勿凭肉眼重测）
3. 若改 `videos/demo-drum-score/`，再读该目录 `AGENTS.md`（HyperFrames，优先）

## 两条管线（先确认跑哪条）

| 线 | 入口 | 用途 |
| --- | --- | --- |
| A. 全曲 PDF 成片（主） | `tools/render_full.py` | PDF 底图 + 光标 + 音频 → MP4 |
| B. HyperFrames demo | `videos/demo-drum-score/` | 8 小节小样引擎 |

一次只动一条线；改完立刻跑对应检查/重渲。

## 管线 A：全曲编制（现行定稿）

### 输入

- 谱面 PDF（如 `refs/score/绿光（R&B）.pdf`）
- 对齐好的音频（如 `refs/audio/绿光_烟嗓版.m4a`）
- 参数在 `render_full.py` 顶部：`BPM` / `PHASE` / `COUNTDOWN` / `CHARTS`

### 光标与时间轴硬规则

- **每小节 = `BAR` 秒**，在该小节 `[xa, xb]` 内匀速；禁止「整行匀速」（多小节行会忽快忽慢）
- **每行起点** = 该行**第一个音符**，跳过打击乐谱号双竖线与拍号（`first_note_x`）
- **片头倒数**：定格画面 `COUNTDOWN` 秒（现行 3s），白字 `3→2→1`；倒数结束 = 第 1 小节强拍（`PHASE`），再开扫；音频用 `adelay` 对齐
- 版式/框架不动时，只调光标速度或相位，勿改滚动为连续横滚

### 渲染命令

```powershell
$ff 可忽略；脚本内自取 imageio_ffmpeg
$pdf   = "refs/score/绿光（R&B）.pdf"
$audio = "refs/audio/绿光_烟嗓版.m4a"
$out   = "refs/out/绿光鼓谱_xxx.mp4"
$scoreDur = 60 * (4 * 60 / 103.5) + 2   # 谱面段时长；倒数由脚本另加
python tools/render_full.py $pdf $audio $out $scoreDur
```

ffmpeg **不在 PATH**，其它分析脚本第一个参数用：

```powershell
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
```

### 完成后强制

1. 成片在 `refs/out/`
2. **必须复制到用户桌面**（同名文件）。`render_full.py` 的 `save_to_desktop()` 已做；其它入口也要拷并告知桌面路径
3. 用系统播放器打开给用户看关键段（片头倒数衔接、换行首音符）

## 管线 B：HyperFrames demo

```powershell
Set-Location videos/demo-drum-score
npm run check
npx hyperframes preview --background   # 勿用 npm run dev 后台包装
npm run render
# 渲染完成后把 renders/*.mp4 拷到桌面
```

确定性：禁止 `Date.now()` / `Math.random()` / 网络；唯一根时间轴键名 = `data-composition-id`。

## 谱面数据约定

```jsonc
{ "bpm": 92, "beatsPerBar": 4,
  "patterns": { "A": { "hh": "x.x.x.x.x.x.x.x.", "snare": "....x.......x...", "kick": "x.......x.x....." } },
  "arrangement": [{ "bar": 1, "pattern": "A", "crash": true }] }
```

时间一律 `拍号 + BPM` 换算，勿写死秒数。音频推断服从谱面图。

## 常见改需求怎么做

| 用户说 | 改哪里 |
| --- | --- |
| 光标某段忽快忽慢 | 确认是按小节扫，不是整行匀速；查该行 `CHARTS` / 小节宽 |
| 换行从双竖线起扫 | 查 `first_note_x`，勿把 `xa` 设回谱号左缘 |
| 片头倒数秒数/对准强拍 | `COUNTDOWN`、`PHASE`、音频 `adelay` |
| 整曲速度 | `BPM`（会动 `BAR`）；改完重渲 |
| 只要成片不要工程内路径 | 仍写 `refs/out/`，并桌面副本 |

## 禁止

- 连续横向滚谱（参考是固定版式内扫行后跳下一行）
- 编制完成不落桌面 MP4
- 未读技术笔记就重测已有 BPM/版式参数
- 为脚本引入 `librosa` 等未列依赖

## 验收清单

- [ ] 倒数结束瞬间光标从第 1 小节首音符开扫，与强拍对齐
- [ ] 每一行光标都从首音符起，不从谱号双竖线起
- [ ] 各小节光标历时一致（每小节 `BAR`）
- [ ] `refs/out/` 与**桌面**各有一份同名 MP4，已告知路径
