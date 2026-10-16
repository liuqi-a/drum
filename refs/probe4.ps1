# 用途：检查画面四周边缘与背景底色（判断是否有录屏残留的黑边/UI）
$ErrorActionPreference = 'Continue'
$fr = 'C:\Users\000\Desktop\codex APPly\drum\refs\frames'
$b = [IO.File]::ReadAllBytes((Join-Path $fr 'seq2.rgb'))
$w = 852; $h = 480
function Px { param($x, $y) $i = ($y * $w + $x) * 3; "{0},{1} => {2},{3},{4}" -f $x, $y, $b[$i], $b[$i + 1], $b[$i + 2] }
"--- 四角与中心 ---"
Px 0 0; Px 851 0; Px 0 479; Px 851 479
Px 426 0; Px 426 479; Px 0 240; Px 851 240
"--- 左边缘竖列 (x=2) ---"
foreach ($y in @(0, 2, 5, 10, 20, 40, 100, 240, 400, 470, 475, 478)) { Px 2 $y }
"--- 底边缘横行 (y=478) ---"
foreach ($x in @(0, 10, 100, 300, 500, 700, 850)) { Px $x 478 }
"--- 整体主色统计 ---"
$hist = @{}
for ($i = 0; $i -lt $b.Length; $i += 3) {
  $key = "{0},{1},{2}" -f $b[$i], $b[$i + 1], $b[$i + 2]
  if ($hist.ContainsKey($key)) { $hist[$key]++ } else { $hist[$key] = 1 }
}
$hist.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 8 | ForEach-Object { "  {0}  x{1}" -f $_.Key, $_.Value }
