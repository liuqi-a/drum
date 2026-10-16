# 用途：生成关键区域放大图（标题栏/播放头/记谱细节）与音频频谱图
$ErrorActionPreference = 'Continue'
$root = 'C:\Users\000\Desktop\codex APPly\drum'
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
$fr = Join-Path $root 'refs\frames'
$vid = Join-Path $root 'refs\video'

# 1) 标题栏区域放大 2 倍
& $ff -hide_banner -loglevel error -i (Join-Path $fr 'BV1MisVzYERQ_t12.png') -vf 'crop=852:100:0:0,scale=iw*2:ih*2:flags=lanczos' -y (Join-Path $fr 'zoom_title.png')
# 2) 播放头放大 4 倍
& $ff -hide_banner -loglevel error -i (Join-Path $fr 'BV1hDkvBWEG7_seq2.png') -vf 'crop=70:140:195:190,scale=iw*4:ih*4:flags=neighbor' -y (Join-Path $fr 'zoom_playhead.png')
# 3) 记谱细节放大 3 倍
& $ff -hide_banner -loglevel error -i (Join-Path $fr 'BV1hDkvBWEG7_t12.png') -vf 'crop=350:100:50:170,scale=iw*3:ih*3:flags=lanczos' -y (Join-Path $fr 'zoom_notation.png')
# 4) 音频频谱图（前 30 秒，判断是否为原曲）
& $ff -hide_banner -loglevel error -ss 0 -t 30 -i (Join-Path $vid 'BV1MisVzYERQ.f30280.m4a') -lavfi 'showspectrumpic=s=1000x420:legend=disabled:scale=log' -y (Join-Path $fr 'spec_aini_30s.png')
"done"
Get-ChildItem $fr -Filter 'zoom_*.png' | ForEach-Object { "{0} {1}" -f $_.Length, $_.Name }
Get-ChildItem $fr -Filter 'spec_*.png' | ForEach-Object { "{0} {1}" -f $_.Length, $_.Name }
