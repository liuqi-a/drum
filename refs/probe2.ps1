# 用途：补抽片头/片尾帧、滚动连续性帧，并测量播放头颜色与宽度
$ErrorActionPreference = 'Continue'
$root = 'C:\Users\000\Desktop\codex APPly\drum'
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
$vid = Join-Path $root 'refs\video'
$fr = Join-Path $root 'refs\frames'

function Grab {
  param($input_file, $time, $out_file)
  & $ff -hide_banner -loglevel error -ss $time -i $input_file -frames:v 1 -y $out_file
}

# 1) 片头 / 片尾
Grab (Join-Path $vid 'BV1hDkvBWEG7.f100023.mp4') 0.2  (Join-Path $fr 'intro_kylin.png')
Grab (Join-Path $vid 'BV1hDkvBWEG7.f100023.mp4') 185.5 (Join-Path $fr 'outro_kylin.png')
Grab (Join-Path $vid 'BV1MisVzYERQ.f30032.mp4') 216 (Join-Path $fr 'outro_aini.png')

# 2) 纵向滚动连续性：0.25s × 12 帧
$i = 0
foreach ($t in @(19.75, 20.0, 20.25, 20.5, 20.75, 21.0, 21.25, 21.5, 21.75, 22.0, 22.25, 22.5)) {
  Grab (Join-Path $vid 'BV1hDkvBWEG7.f100023.mp4') $t (Join-Path $fr ("scroll{0:d2}.png" -f $i))
  $i++
}

# 3) 播放头颜色剖面：在 seq2 帧上取一行原始像素
$seq2 = Join-Path $fr 'BV1hDkvBWEG7_seq2.png'
$rowFile = Join-Path $fr 'row_inside.rgb'
& $ff -hide_banner -loglevel error -i $seq2 -vf 'crop=90:1:200:205,format=rgb24' -f rawvideo -y $rowFile
$rowFile2 = Join-Path $fr 'row_blank.rgb'
& $ff -hide_banner -loglevel error -i $seq2 -vf 'crop=90:1:200:60,format=rgb24' -f rawvideo -y $rowFile2

foreach ($pair in @(@($rowFile, 'y=205 (播放头所在行)'), @($rowFile2, 'y=60 (空白背景行)'))) {
  $bytes = [IO.File]::ReadAllBytes($pair[0])
  "=== " + $pair[1] + " ==="
  $out = @()
  for ($k = 0; $k -lt $bytes.Length; $k += 3) {
    $x = 200 + [int]($k / 3)
    $out += ("{0}:{1},{2},{3}" -f $x, $bytes[$k], $bytes[$k + 1], $bytes[$k + 2])
  }
  ($out -join '  ')
}
