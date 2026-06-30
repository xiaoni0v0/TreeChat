"""生成 TreeChat 图标 icon.ico（需要 Pillow）"""

import math

from PIL import Image, ImageDraw

BG = (14, 17, 22, 255)  # #0e1116
LINE = (58, 74, 94, 255)  # #3a4a5e
ACCENT = (79, 157, 255, 255)  # #4f9dff
PURPLE = (124, 92, 255, 255)  # #7c5cff
TRANSP = (0, 0, 0, 0)


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), TRANSP)
    d = ImageDraw.Draw(img)
    s = size / 300.0  # 参考设计尺寸 300×300

    # ── 圆角背景 ──────────────────────────────
    pad = int(6 * s)
    r = int(56 * s)
    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=r,
        fill=BG,
        outline=(42, 51, 64, 255),
        width=max(1, int(1.5 * s)),
    )

    # ── 坐标（相对 300×300 设计稿） ──────────
    # 树节点中心（设计稿坐标系，原点在图标左上角，图标内容区 20..280）
    ROOT = (150, 76)
    MID_L = (72, 160)
    MID_R = (228, 160)
    LEAF_LL = (32, 244)
    LEAF_LR = (112, 244)
    LEAF_R = (228, 244)

    def sc(p):
        """把 300×300 坐标换算到 size×size"""
        return (p[0] * s, p[1] * s)

    def line(a, b):
        ax, ay = sc(a)
        bx, by = sc(b)
        # 从圆边缘出发，避免线压住圆
        dx, dy = bx - ax, by - ay
        dist = math.hypot(dx, dy) or 1
        ra = get_r(a) * s
        rb = get_r(b) * s
        sx = ax + dx / dist * ra
        sy = ay + dy / dist * ra
        ex = bx - dx / dist * rb
        ey = by - dy / dist * rb
        w = max(1, int(2.2 * s))
        d.line([(sx, sy), (ex, ey)], fill=LINE, width=w)

    radii = {ROOT: 24, MID_L: 18, MID_R: 18, LEAF_LL: 14, LEAF_LR: 14, LEAF_R: 14}

    def get_r(p):
        return radii.get(p, 14)

    def circle(center, radius, color):
        cx, cy = sc(center)
        r2 = radius * s
        d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=color)

    # 连线
    line(ROOT, MID_L)
    line(ROOT, MID_R)
    line(MID_L, LEAF_LL)
    line(MID_L, LEAF_LR)
    line(MID_R, LEAF_R)

    # 节点
    circle(MID_L, 18, ACCENT)
    circle(MID_R, 18, ACCENT)
    circle(LEAF_LL, 14, PURPLE)
    circle(LEAF_LR, 14, ACCENT)
    circle(LEAF_R, 14, PURPLE)
    # 根节点最后画（在最上层）
    circle(ROOT, 24, ACCENT)

    # 根节点气泡尾巴
    rx, ry = sc(ROOT)
    tail_h = 14 * s
    tw = 10 * s
    br = 24 * s
    pts = [
        (rx - tw, ry + br - 2),
        (rx + tw, ry + br - 2),
        (rx, ry + br + tail_h),
    ]
    d.polygon(pts, fill=ACCENT)

    return img


def main():
    sizes = [256, 128, 64, 48, 32, 16]
    images = [draw_icon(sz) for sz in sizes]
    out = "icon.ico"
    images[0].save(
        out,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=images[1:],
    )
    print("icon.ico saved (%d sizes)" % len(sizes))


if __name__ == "__main__":
    main()
