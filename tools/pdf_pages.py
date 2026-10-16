# 用途：把 PDF 每页渲染成高分辨率 PNG（300dpi 起），作为逐行读谱的清晰底图
import os
import sys

import pymupdf


def main():
    pdf = sys.argv[1]
    outdir = sys.argv[2]
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    os.makedirs(outdir, exist_ok=True)
    doc = pymupdf.open(pdf)
    print('PDF 页数:', doc.page_count)
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(dpi=dpi)
        path = os.path.join(outdir, 'page%02d.png' % i)
        pix.save(path)
        print('第 %d 页 -> %s (%dx%d)' % (i, path, pix.width, pix.height))
    doc.close()


if __name__ == '__main__':
    main()
