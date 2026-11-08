# -*- coding: utf-8 -*-
"""
make_dataset.py
构建实验用的低照度图像数据集。

思路：真值图（clean）不依赖任何外部下载，全部由程序按"几何形状 + 纹理 + 光照梯度"
合成，这样每张图的退化过程完全可控、可复现，参考真值也一定对齐。

退化模型不是简单乘一个系数，而是按工程上更接近实际的成像链路来写：

    L(x) = gamma( (I * T)(x) * A(x) / 255 ) * 255 + 噪声

其中
    A(x)     = kappa / (1 + (r(x)/R0)^2)       —— 暗角（镜头衰减），r 为到光轴的距离
    T(x)     = 1 - shadow * exp(-d(x)^2/...)   —— 局部阴影（遮挡物投下的影子）
    gamma(·) = (·/255)^g ，g > 1 使整体偏暗、暗部被压缩
    噪声      = 泊松-高斯混合（光子数少时噪声方差随信号增大）

用法：
    python make_dataset.py --out data --n-train 24 --n-test 8
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# ----------------------------------------------------------------------------
# 1. 真值图合成
# ----------------------------------------------------------------------------
def _rand_polygon(rng, w, h, n_vert, center, radius):
    """在给定中心和半径附近生成一个凸多边形的顶点序列。"""
    angles = np.sort(rng.uniform(0, 2 * np.pi, n_vert))
    radii = radius * rng.uniform(0.65, 1.0, n_vert)
    xs = center[0] + radii * np.cos(angles)
    ys = center[1] + radii * np.sin(angles)
    return list(zip(xs.tolist(), ys.tolist()))


def _add_texture(img, rng, strength=10.0):
    """叠一层低频纹理（用大核高斯模糊的白噪声），避免画面过于"塑料"。"""
    h, w = img.shape[:2]
    noise = rng.normal(0, 1, (h, w))
    # 用可分离的卷积近似低通，速度比直接二维卷积快
    y = np.linspace(-3, 3, 31)
    k = np.exp(-0.5 * y ** 2)
    k /= k.sum()
    noise = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 0, noise)
    noise = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 1, noise)
    noise /= (np.abs(noise).max() + 1e-8)
    out = img.astype(np.float32) + strength * noise[..., None]
    return np.clip(out, 0, 255)


def _add_gradient(img, rng):
    """加一个整体照明梯度（模拟侧面打光），让直方图不那么好对付。"""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ax, ay = rng.uniform(-1, 1), rng.uniform(-1, 1)
    g = (ax * xx / w + ay * yy / h)
    g = g - g.min()
    g = g / (g.max() + 1e-8)
    gain = 0.65 + 0.5 * g
    return np.clip(img.astype(np.float32) * gain[..., None], 0, 255)


def synth_clean(rng, w=320, h=240, kind=None):
    """合成一张"真值"图。kind 可选 blend / texture / shapes / mixed。"""
    kinds = ["blend", "texture", "shapes", "mixed"]
    kind = kind or kinds[rng.integers(len(kinds))]

    # 底色：两到三种低饱和颜色，方便看出色彩偏移
    n_base = rng.integers(2, 4)
    base = rng.integers(30, 220, (n_base, 3)).astype(np.float32)
    canvas = np.zeros((h, w, 3), np.float32)
    for i in range(n_base):
        canvas += base[i] / n_base

    bg = tuple(int(np.clip(canvas, 0, 255).mean(axis=(0, 1))[c]) for c in range(3))
    layer = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(layer)

    if kind in ("blend", "mixed"):
        # 若干高斯光斑，用多次模糊叠加得到柔和过渡
        for _ in range(rng.integers(3, 6)):
            cx, cy = rng.uniform(0, w), rng.uniform(0, h)
            r = rng.uniform(w * 0.15, w * 0.55)
            col = tuple(int(v) for v in rng.integers(20, 245, 3))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=rng.uniform(6, 18)))

    if kind in ("shapes", "mixed"):
        # 高对比几何体：测试算法在边界处的光晕和过冲
        for _ in range(rng.integers(4, 9)):
            cx, cy = rng.uniform(w * 0.1, w * 0.9), rng.uniform(h * 0.1, h * 0.9)
            r = rng.uniform(w * 0.04, w * 0.18)
            col = tuple(int(v) for v in rng.integers(0, 256, 3))
            poly = _rand_polygon(rng, w, h, rng.integers(3, 7), (cx, cy), r)
            draw.polygon(poly, fill=col, outline=(0, 0, 0))
        for _ in range(rng.integers(2, 5)):
            x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
            x1, y1 = x0 + rng.uniform(-w * 0.4, w * 0.4), y0 + rng.uniform(-h * 0.4, h * 0.4)
            col = tuple(int(v) for v in rng.integers(0, 256, 3))
            draw.line([x0, y0, x1, y1], fill=col, width=int(rng.integers(2, 7)))

    if kind in ("texture", "mixed"):
        # 明暗条纹：给频域/多尺度方法留点可做的活
        period = rng.uniform(6, 26)
        alpha = rng.uniform(0.08, 0.25)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        theta = rng.uniform(0, np.pi)
        proj = xx * np.cos(theta) + yy * np.sin(theta)
        stripe = 0.5 + 0.5 * np.sin(2 * np.pi * proj / period)
        arr = np.asarray(layer).astype(np.float32)
        arr = arr * (1 - alpha) + (arr * (0.6 + 0.8 * stripe[..., None])) * alpha
        layer = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    arr = np.asarray(layer).astype(np.float32)
    arr = _add_gradient(arr, rng)
    arr = _add_texture(arr, rng, strength=rng.uniform(6, 14))

    # 轻微空域模糊模拟镜头 MTF 有限
    layer = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.6, 1.4)))
    return np.asarray(layer).astype(np.float32)


# ----------------------------------------------------------------------------
# 2. 退化（低照度）模拟
# ----------------------------------------------------------------------------
def degrade(img, rng, gamma_range=(1.6, 2.35), kappa_range=(0.40, 0.68),
            shadow_prob=0.6, read_sigma=2.0):
    """把真值图变成低照度观测图，返回 (观测, 参数记录)。

    参数范围是调过的：第一版用 gamma∈[1.8,2.8]、kappa∈[0.35,0.6]，
    结果一半以上的图均值掉到 6/255 以下，面积灰、标准差只有 2~3，
    那是"几乎全黑"，不是低照度——真实夜景即使暗，均值也在 15~40 之间，
    结构还看得见。现在把参数收紧到均值落在 8~45 这个区间。
    """
    h, w = img.shape[:2]
    g = rng.uniform(*gamma_range)
    kappa = rng.uniform(*kappa_range)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = ((xx - w / 2) ** 2 + (yy - h / 2) ** 2) / (max(w, h) / 2) ** 2
    vignette = kappa / (1.0 + 1.1 * r2)

    shade = np.ones((h, w), np.float32)
    shade_info = None
    if rng.random() < shadow_prob:
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        sx, sy = rng.uniform(w * 0.15, w * 0.4), rng.uniform(h * 0.15, h * 0.4)
        depth = rng.uniform(0.3, 0.65)
        d2 = ((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2
        shade = 1.0 - depth * np.exp(-d2)
        shade_info = dict(cx=float(cx), cy=float(cy), depth=float(depth))

    # 线性光强 -> 暗角/阴影衰减 -> gamma 压缩
    # 说明：vignette 与 shade 都是"相对照度"，先归一化到统计均值 1，
    # 避免两者相乘后把整幅图压得过暗，只保留"不均匀"这一层信息；
    # 整体亮度水平交给 gamma 与 kappa 控制。
    attn = vignette * shade
    attn = attn / (attn.mean() + 1e-8)
    lin = img / 255.0
    lin = lin * (kappa * attn)[..., None]
    obs = np.power(np.clip(lin, 1e-6, 1.0), g) * 255.0

    # 泊松-高斯噪声：暗部（光子少）相对噪声更大
    photons = obs / 255.0 * rng.uniform(60, 160)
    noisy = rng.poisson(np.clip(photons, 0, None)) / rng.uniform(60, 160) * 255.0
    noisy = 0.5 * obs + 0.5 * noisy + rng.normal(0, read_sigma, obs.shape)
    obs = np.clip(noisy, 0, 255)

    params = dict(gamma=float(g), kappa=float(kappa), shadow=shade_info)
    return obs.astype(np.float32), params


# ----------------------------------------------------------------------------
# 3. 主流程
# ----------------------------------------------------------------------------
def build(n_train=24, n_test=8, size=(320, 240), seed=2026, out="data"):
    w, h = size
    os.makedirs(os.path.join(out, "clean"), exist_ok=True)
    os.makedirs(os.path.join(out, "low"), exist_ok=True)

    rng = np.random.default_rng(seed)
    records = []
    total = n_train + n_test
    for i in range(total):
        clean = synth_clean(rng, w, h)
        low, params = degrade(clean, rng)

        split = "train" if i < n_train else "test"
        name = f"{split}_{i:03d}.png"
        Image.fromarray(clean.astype(np.uint8)).save(os.path.join(out, "clean", name))
        Image.fromarray(low.astype(np.uint8)).save(os.path.join(out, "low", name))

        records.append(dict(
            name=name, split=split, gamma=params["gamma"],
            kappa=params["kappa"], shadow=params["shadow"],
            mean_low=float(low.mean()), mean_clean=float(clean.mean()),
            std_low=float(low.std()),
        ))
        print(f"[{i+1:02d}/{total}] {name}  gamma={params['gamma']:.2f} "
              f"kappa={params['kappa']:.2f}  mean={low.mean():.1f}")

    meta = dict(
        size=list(size), seed=seed, n_train=n_train, n_test=n_test,
        note="clean 为程序合成真值，low 为按 暗角+阴影+gamma+泊松高斯噪声 退化后的观测",
        items=records,
    )
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"\n完成：{total} 对图像写入 {out}/ ，元数据 meta.json")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--n-train", type=int, default=24)
    ap.add_argument("--n-test", type=int, default=8)
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--height", type=int, default=240)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    build(a.n_train, a.n_test, (a.width, a.height), a.seed, a.out)
