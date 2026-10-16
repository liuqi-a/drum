# 用途：客观测量谱面纵向位置随时间的变化（找第一条五线谱线的 y），判断连续滚动还是分页跳转
$ErrorActionPreference = 'Continue'
$root = 'C:\Users\000\Desktop\codex APPly\drum'
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
$fr = Join-Path $root 'refs\frames'
$tmp = Join-Path $fr 'gray'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

function FirstStaffLine {
  param($png)
  $raw = Join-Path $tmp 'p.gray'
  # 横向压成 4 像素、纵向 480 行并转灰度，便于逐行判断明暗
  & $ff -hide_banner -loglevel error -i $png -vf 'scale=4:480,format=gray' -f rawvideo -y $raw
  $b = [IO.File]::ReadAllBytes($raw)
  $hits = @()
  for ($y = 16; $y -lt 480; $y++) {
    $s = 0
    for ($x = 0; $x -lt 4; $x++) { $s += $b[$y * 4 + $x] }
    if (($s / 4) -lt 150) { $hits += $y }
    if ($hits.Count -ge 3) { break }
  }
  return ($hits -join '/')
}

$names = @('seq00', 'seq01', 'seq02', 'seq03', 'seq04', 'seq05', 'seq06', 'seq07')
$names += @('scroll00', 'scroll01', 'scroll02', 'scroll03', 'scroll04', 'scroll05')
$names += @('scroll06', 'scroll07', 'scroll08', 'scroll09', 'scroll10', 'scroll11')

foreach ($n in $names) {
  $png = Join-Path $fr ($n + '.png')
  if (-not (Test-Path $png)) { continue }
  $y = FirstStaffLine $png
  "{0}: darkRows(y>=16)={1}" -f $n, $y
}
