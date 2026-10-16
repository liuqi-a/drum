# 用途：给整页谱照片叠加坐标网格（每 100 像素一条线并标号），便于肉眼确定各谱行的纵坐标范围
import sys

from PIL import Image, ImageDraw


def main():
    src, out = sys.argv[1], sys.argv[2]
    img = Image.open(src).convert('RGB')
    w, h = img.size
    draw = ImageDraw.Draw(img)
    for y in range(0, h, 100):
        color = (255, 0, 0) if y % 500 == 0 else (0, 160, 255)
        draw.line([(0, y), (w, y)], fill=color, width=3 if y % 500 == 0 else 1)
        draw.text((6, y + 4), str(y), fill=(255, 0, 0))
    for x in range(0, w, 200):
        draw.line([(x, 0), (x, h)], fill=(0, 180, 90), width=1)
        draw.text((x + 4, 6), str(x), fill=(0, 130, 60))
    scale = 1100.0 / w
    img = img.resize((1100, int(h * scale)), Image.LANCZOS)
    img.save(out)
    print('已保存:', out, img.size)


if __name__ == '__main__':
    main()
