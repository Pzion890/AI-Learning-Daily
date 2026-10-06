# -*- coding: utf-8 -*-
"""对话式建模第一课：铭牌生成器
底板60x40x3mm + "针灸推拿"黑体浮雕字高2mm → 输出 .stl
"""
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------- 参数（想改字/尺寸就改这里） ----------
TEXT      = "针灸推拿"
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"   # 黑体
PLATE_W, PLATE_D, PLATE_H = 60.0, 40.0, 3.0  # 底板 mm
RELIEF_H  = 2.0                               # 浮雕凸起高度 mm
CELL      = 0.30                              # 每格 mm（越小越细腻）
CHAR_MM   = 13.0                              # 字号 mm
OUT_STL   = r"D:\Bambu Studio\作品\针灸推拿铭牌.stl"
OUT_PNG   = r"D:\Bambu Studio\作品\预览图.png"

# ---------- 1. 高分辨率渲染文字，再降采样（抗锯齿） ----------
NX, NY = int(PLATE_W / CELL), int(PLATE_D / CELL)   # 200 x 133
SS = 4                                               # 超采样倍数
big = Image.new("L", (NX * SS, NY * SS), 255)
d = ImageDraw.Draw(big)
font = ImageFont.truetype(FONT_PATH, size=int(CHAR_MM / CELL * SS))
d.text((NX * SS / 2, NY * SS / 2), TEXT, font=font, fill=0, anchor="mm")
small = np.array(big.resize((NX, NY), Image.BOX))
mask = small < 128                                   # True = 文字区

# 导出 2D 预览图（肉眼看字形是否正确）
Image.fromarray((mask * 255).astype(np.uint8)).resize((NX * 3, NY * 3)).save(OUT_PNG)

# ---------- 2. 每格的顶面高度 ----------
# flipud: 图像y向下、模型y向上，翻转防止文字镜像；.T: 转成 Z[列i, 行j] 索引
Z = np.where(np.flipud(mask), PLATE_H + RELIEF_H, PLATE_H).T

# ---------- 3. 堆三角形：顶面 + 侧面墙 + 底面 ----------
tris = []
def add(a, b, c):
    tris.append((a, b, c))

for i in range(NX):
    for j in range(NY):
        x0, x1 = i * CELL, (i + 1) * CELL
        y0, y1 = j * CELL, (j + 1) * CELL
        zt = Z[i, j]
        # 顶面（法线+Z）
        add((x0, y0, zt), (x1, y0, zt), (x1, y1, zt))
        add((x0, y0, zt), (x1, y1, zt), (x0, y1, zt))
        # 底面（法线-Z）
        add((x0, y0, 0), (x1, y1, 0), (x1, y0, 0))
        add((x0, y0, 0), (x0, y1, 0), (x1, y1, 0))
        # 四面侧墙：比邻居高就补墙
        zn_r = Z[i + 1, j] if i + 1 < NX else 0.0
        if zt > zn_r:
            add((x1, y0, zt), (x1, y0, zn_r), (x1, y1, zt))
            add((x1, y1, zt), (x1, y0, zn_r), (x1, y1, zn_r))
        zn_l = Z[i - 1, j] if i - 1 >= 0 else 0.0
        if zt > zn_l:
            add((x0, y0, zt), (x0, y1, zt), (x0, y0, zn_l))
            add((x0, y1, zt), (x0, y1, zn_l), (x0, y0, zn_l))
        zn_n = Z[i, j + 1] if j + 1 < NY else 0.0
        if zt > zn_n:
            add((x0, y1, zt), (x1, y1, zt), (x0, y1, zn_n))
            add((x1, y1, zt), (x1, y1, zn_n), (x0, y1, zn_n))
        zn_s = Z[i, j - 1] if j - 1 >= 0 else 0.0
        if zt > zn_s:
            add((x0, y0, zt), (x0, y0, zn_s), (x1, y0, zt))
            add((x1, y0, zt), (x0, y0, zn_s), (x1, y0, zn_s))

# ---------- 4. 写二进制 STL ----------
import os
os.makedirs(os.path.dirname(OUT_STL), exist_ok=True)
def normal(a, b, c):
    u, v = np.subtract(b, a), np.subtract(c, a)
    n = np.cross(u, v)
    L = np.linalg.norm(n)
    return n / L if L > 1e-12 else (0.0, 0.0, 0.0)

with open(OUT_STL, "wb") as f:
    f.write(b"Nameplate Claude".ljust(80, b"\0"))
    f.write(struct.pack("<I", len(tris)))
    for a, b, c in tris:
        nx, ny, nz = normal(np.array(a), np.array(b), np.array(c))
        f.write(struct.pack("<3f", nx, ny, nz))
        for p in (a, b, c):
            f.write(struct.pack("<3f", *p))
        f.write(b"\0\0")

print(f"OK 三角形数: {len(tris):,} | 文件: {OUT_STL}")
print(f"文件大小: {os.path.getsize(OUT_STL)/1e6:.1f} MB")
