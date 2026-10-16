# 用途：对参考视频抽帧（整体版式 + 连续帧看滚动/高亮机制）
$ErrorActionPreference = 'Continue'
$root = 'C:\Users\000\Desktop\codex APPly\drum'
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
$vid = Join-Path $root 'refs\video'
$fr = Join-Path $root 'refs\frames'
New-Item -ItemType Directory -Force -Path $fr | Out-Null

function Grab-Frame {
  param($input_file, $time, $out_file)
  & $ff -hide_banner -loglevel error -ss $time -i $input_file -frames:v 1 -y $out_file
}

$videos = Get-ChildItem $vid -Filter '*.mp4'
foreach ($v in $videos) {
  $id = ($v.BaseName -split '\.')[0]
  # 视频基本信息
  "=== $($v.Name) ==="
  $probe = & $ff -hide_banner -i $v.FullName 2>&1 | Select-String 'Duration|Stream #0:0'
  $probe | ForEach-Object { $_.Line.Trim() }
  # 整体版式：按时间点采样
  foreach ($t in @(1, 6, 12, 25, 45)) {
    Grab-Frame -input_file $v.FullName -time $t -out_file (Join-Path $fr "$id`_t$t.png")
  }
  # 连续帧：观察滚动方向与高亮（间隔 0.5s，共 8 帧）
  $i = 0
  foreach ($t in @(12.0, 12.5, 13.0, 13.5, 14.0, 14.5, 15.0, 15.5)) {
    Grab-Frame -input_file $v.FullName -time $t -out_file (Join-Path $fr "$id`_seq$i.png")
    $i++
  }
}
"=== 抽帧结果 ==="
Get-ChildItem $fr | ForEach-Object { $_.Name } | Sort-Object
