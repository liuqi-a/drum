# 用途：下载三个参考视频的低码率版本，用于逐帧分析版式与动画
$ErrorActionPreference = 'Continue'
$root = 'C:\Users\000\Desktop\codex APPly\drum'
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
$ffdir = Split-Path $ff
"ffmpeg dir: $ffdir"
$out = Join-Path $root 'refs\video'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$urls = @(
  'https://www.bilibili.com/video/BV1hDkvBWEG7/',
  'https://www.bilibili.com/video/BV1MisVzYERQ/',
  'https://www.bilibili.com/video/BV1ZXsazYEsF/'
)
foreach ($u in $urls) {
  "=== downloading $u ==="
  python -m yt_dlp --no-playlist --no-warnings --ffmpeg-location $ffdir --referer 'https://www.bilibili.com/' -f 'bv*[height<=480]+ba/b[height<=480]/bv*+ba/b' -o "$out\%(id)s.%(ext)s" $u
}
"=== result ==="
Get-ChildItem $out | ForEach-Object { "{0}  {1}" -f $_.Length, $_.Name }
