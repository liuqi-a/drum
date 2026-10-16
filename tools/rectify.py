# 用途：把手机拍的谱页做透视矫正（取纸张四角做投影变换），输出拉正后的页面图
import sys

import cv2
import numpy as np


def order_points(pts):
    # 按 左上/右上/右下/左下 的顺序整理四个角点
    rect = np.zeros((4, 2), dtype='float32')
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    d = np.diff(pts, axis=1).ravel()
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect


def rectify(path, out_path, mask_path=None):
    # 纸张判定：亮且低饱和（排除桌面与蓝色墙面）
    img = cv2.imread(path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    s = hsv[:, :, 1]
    mask = ((v > 120) & (s < 70)).astype(np.uint8) * 255
    kernel = np.ones((31, 31), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise RuntimeError('没有找到纸张区域')
    c = max(cnts, key=cv2.contourArea)
    rect = cv2.minAreaRect(c)
    box = order_points(cv2.boxPoints(rect))
    tl, tr, br, bl = box
    wA = np.linalg.norm(br - bl)
    wB = np.linalg.norm(tr - tl)
    hA = np.linalg.norm(tr - br)
    hB = np.linalg.norm(tl - bl)
    W = int(max(wA, wB))
    H = int(max(hA, hB))
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype='float32')
    M = cv2.getPerspectiveTransform(box, dst)
    out = cv2.warpPerspective(img, M, (W, H))
    cv2.imwrite(out_path, out)
    if mask_path:
        cv2.imwrite(mask_path, mask)
    print('纸张四角:', box.astype(int).tolist())
    print('输出尺寸: %dx%d' % (W, H))
    print('长宽比: %.4f (A4 竖版约 0.7071)' % (W / H))
    return out


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2]
    mask_out = sys.argv[3] if len(sys.argv) > 3 else None
    rectify(src, dst, mask_out)
