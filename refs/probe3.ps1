# 用途：整帧像素分析——精确定位播放头（蓝色竖条）的包围盒、颜色与相对谱表高度
$ErrorActionPreference = 'Continue'
$root = 'C:\Users\000\Desktop\codex APPly\drum'
$ff = python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
$fr = Join-Path $root 'refs\frames'

function Dump-Frame {
  param($png, $rgb)
  & $ff -hide_banner -loglevel error -i $png -vf 'format=rgb24' -f rawvideo -y $rgb
}

function Get-Dims {
  param($png)
  $line = (& $ff -hide_banner -i $png -vf showinfo -f null - 2>&1 | Select-String 's:\d+x\d+' | Select-Object -First 1).Line
  $m = [regex]::Match($line, 's:(\d+)x(\d+)')
  return @([int]$m.Groups[1].Value, [int]$m.Groups[2].Value)
}

$png = Join-Path $fr 'BV1hDkvBWEG7_seq2.png'
$dims = Get-Dims $png
$w = $dims[0]; $h = $dims[1]
"frame: ${w}x${h}"
$rgb = Join-Path $fr 'seq2.rgb'
Dump-Frame $png $rgb
$b = [IO.File]::ReadAllBytes($rgb)
"bytes: " + $b.Length

# 扫描蓝色像素（B 明显大于 R 且整体偏亮），求包围盒并统计主色
$minX = $w; $maxX = -1; $minY = $h; $maxY = -1
$hist = @{}
$count = 0
for ($y = 0; $y -lt $h; $y++) {
  $base = $y * $w * 3
  for ($x = 0; $x -lt $w; $x++) {
    $i = $base + $x * 3
    $r = $b[$i]; $g = $b[$i + 1]; $bl = $b[$i + 2]
    if (($bl - $r) -gt 12 -and $bl -ge 180) {
      $count++
      if ($x -lt $minX) { $minX = $x }
      if ($x -gt $maxX) { $maxX = $x }
      if ($y -lt $minY) { $minY = $y }
      if ($y -gt $maxY) { $maxY = $y }
      $key = "$r,$g,$bl"
      if ($hist.ContainsKey($key)) { $hist[$key]++ } else { $hist[$key] = 1 }
    }
  }
}
"blue pixels: $count"
"bbox: x $minX..$maxX  y $minY..$maxY  (width " + ($maxX - $minX + 1) + ", height " + ($maxY - $minY + 1) + ")"
"top colors:"
$hist.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 6 | ForEach-Object { "  {0}  x{1}" -f $_.Key, $_.Value }

# 背景主色（取左上角空白区）
"bg sample: {0},{1},{2}" -f $b[0], $b[1], $b[2]
