# 动态图谱 — 参考参数

## CHARTS（绿光 PDF 行小节数）

```python
CHARTS = {1: [7, 5, 4, 3, 3, 5, 5, 3, 3, 3], 2: [3, 3, 3, 3, 3, 3, 1]}
# 页1 合计 41；页2 配置合计 19，实测常检出 59 小节（末行可能缺 1）
TOTAL_BARS = 60
```

换谱必须按 PDF 行首小节号重读，勿照搬。

## 工具链速查

```powershell
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
```

- MuseScore：`tools/ms4/MuseScore 4/bin/MuseScore4.exe`，导出常用 `-r 300 -T 10`
- 依赖：`numpy` / `soundfile` / `Pillow` / `cv2` / `pymupdf` / `imageio_ffmpeg`；不要为现有脚本强装 `librosa`
- 多数分析脚本**第一个参数是 ffmpeg 路径**

## 相关脚本

| 脚本 | 作用 |
| --- | --- |
| `tools/render_full.py` | 全曲成片主入口（倒数、按小节光标、首音符起点、桌面拷贝） |
| `tools/ref_tempo.py` | 测 BPM / 鼓组进入点 |
| `tools/ref_cursor.py` | 追参考视频蓝光标 |
| `tools/ref_analyze.py` | 谱面几何 + 音频网格 |
| `tools/make_mscx.py` | JSON → MuseScore `.mscx` |
| `tools/build_lvguang.py` | 绿光谱面数据生成（另一条数据链） |

## 硬约束摘要

- 音频与谱面时间轴同源；时间用 BPM+拍号
- 编制完成 → 桌面必须有同名 MP4
- 不横向滚谱；固定版式内扫行跳转
- 谱面权威、音频校验；引子段音频推断不可信

## 烟嗓版对齐备忘

- 音频：`refs/audio/绿光_烟嗓版.m4a`
- PDF：`refs/score/绿光（R&B）.pdf`
- BPM=103.5，PHASE=0.38，COUNTDOWN=3.0
- 成片示例名：`绿光鼓谱_烟嗓版_60小节_倒数3s.mp4`
