# 动态鼓谱（drum）

把歌曲做成「动态鼓谱」视频：**固定版式谱面 + 竖直播放光标扫行 + 与音频同步**。  
对标 B 站 UP「罗曼音乐_Roman_Music」一类成片。

> Agent / 协作约定见 [`AGENTS.md`](AGENTS.md)；技术决策与实测参数见 [`docs/动态鼓谱-技术笔记.md`](docs/动态鼓谱-技术笔记.md)。

## 仓库里有什么

| 路径 | 说明 |
| --- | --- |
| `tools/*.py` | 读谱、测速、造 mscx、全曲渲染（主入口 `render_full.py`） |
| `score/`、`refs/score/*.json` | 谱面数据（十六分网格 JSON 等） |
| `docs/` | 技术笔记 |
| `videos/demo-drum-score/` | HyperFrames 8 小节 demo 工程 |
| `.cursor/` | Cursor rules / skills |

**未纳入 Git 的大文件（需本机自备）：** MuseScore 便携版、`ffmpeg` 压缩包、参考音视频、渲染成片。见 `.gitignore`。

## 环境要求

- Python 3.12+（项目实测 3.14）：`numpy` `soundfile` `Pillow` `opencv-python` `pymupdf` `imageio-ffmpeg`
- Node / npm（仅 HyperFrames demo）
- MuseScore Studio 4（本机安装或放到 `tools/ms4/`）

ffmpeg 一般不在 PATH，脚本内通过 `imageio_ffmpeg` 取路径：

```powershell
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
```

## 快速渲染（全曲 PDF 路线）

```powershell
# 准备：谱面 PDF、对齐好的音频；在 render_full.py 顶部核对 BPM / PHASE / COUNTDOWN / CHARTS
python tools/render_full.py `
  "refs/score/你的谱.pdf" `
  "refs/audio/你的歌.m4a" `
  "refs/out/成片.mp4" `
  <谱面段秒数>

# 编制完成后会自动复制一份到桌面
```

HyperFrames demo：

```powershell
Set-Location videos/demo-drum-score
npm run check
npx hyperframes preview --background
npm run render
```

## 数据约定（节选）

每小节用 16 字符表示十六分网格，`x` 命中、`.` 休止。时间一律用「拍号 + BPM」换算，不要写死秒数。

## License

代码与文档默认保留作者权利；参考曲目与谱面版权归原作者。请勿将未获授权的音视频素材再分发。
