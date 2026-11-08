# -*- coding: utf-8 -*-
"""
make_report_figs.py
专为"放进 Word 并缩放到 15 cm 宽"这一场景重画插图。

上一版图直接用在报告里效果很差：网格图的单元格只有 5 cm 宽，
上面写的 9pt 标签缩小后不到 3pt，完全看不清。所以这里：
  * 每个面板只放少量内容，减少子图数量；
  * 横轴文字改成短标签，必要时旋转；
  * 图尺寸调小但字号调大，让"缩放比"尽量接近 1。
输出到 results/figures/r_*.png。
"""
import os

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

import enhance
import metrics
from run_bench import load_split, _load_font

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 11

OUT = "results/figures"


def r_samples():
    """数据集样例：2 行 × 3 列（3 组「真值 / 低照度」并排更省宽度）。
    原版 4 列塞进 15 cm 后单元格只有 3.5 cm，标签看不清，所以减少列数。"""
    items = load_split("data", "test")[:3]
    fig, axes = plt.subplots(2, 3, figsize=(8.6, 5.2))
    for i, (n, low, clean) in enumerate(items):
        im = clean if i == 0 else None
        axes[0, i].imshow(cv2.cvtColor(clean, cv2.COLOR_BGR2RGB))
        axes[0, i].set_title(f"真值  ({clean.mean():.0f})", fontsize=11)
        axes[1, i].imshow(cv2.cvtColor(low, cv2.COLOR_BGR2RGB))
        axes[1, i].set_title(f"低照度  ({low.mean():.0f})", fontsize=11)
        for a in (axes[0, i], axes[1, i]):
            a.axis("off")
    fig.tight_layout(h_pad=0.6)
    fig.savefig(os.path.join(OUT, "r_samples.jpg"), dpi=190, pil_kwargs={"quality": 92})
    plt.close(fig)


def r_hist():
    """把「输入图 / 直方图 / Gamma 曲线」拆成 1 行 2 列 + 单独一条，
    原来的三联图挤在 15 cm 宽里每格只有 5 cm，坐标轴字完全看不清。"""
    items = load_split("data", "test")
    # 选一张中等暗度的，直方图对比更明显
    items_sorted = sorted(items, key=lambda t: t[1].mean())
    n, low, clean = items_sorted[len(items_sorted) // 3]
    y_low, y_gt = enhance.to_luma(low), enhance.to_luma(clean)

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.5))
    axes[0].hist(y_gt.ravel(), bins=64, range=(0, 255), color="#7f9fbf", label="真值")
    axes[0].hist(y_low.ravel(), bins=64, range=(0, 255), color="#c0504d",
                 alpha=0.8, label="低照度")
    axes[0].set_xlim(0, 255)
    axes[0].set_xlabel("灰度值", fontsize=11)
    axes[0].set_ylabel("像素数", fontsize=11)
    axes[0].set_title("亮度直方图", fontsize=12)
    axes[0].legend(fontsize=10)

    x = np.linspace(0, 1, 256)
    axes[1].plot([0, 255], [0, 255], "--", color="#c8c8c8", lw=1.2, label="恒等 g=1")
    for g, c, lb in [(1 / 2.4, "#4f81bd", "g=0.42"), (0.32, "#c0504d", "g=0.32")]:
        axes[1].plot(x * 255, 255 * x ** g, color=c, lw=2, label=lb)
    # 只标一段竖箭头示意"暗部被陡峭拉伸"，说明写在图注里，
    # 图上不叠文字，避免压住曲线反而看不清。
    axes[1].annotate("", xy=(6, 74), xytext=(6, 1),
                     arrowprops=dict(arrowstyle="<->", color="#8064a2", lw=2))
    axes[1].set_xlabel("输入灰度", fontsize=11)
    axes[1].set_ylabel("输出灰度", fontsize=11)
    axes[1].set_title("Gamma 映射曲线", fontsize=12)
    axes[1].legend(fontsize=10)
    axes[1].grid(alpha=0.25)
    axes[1].set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "r_hist.jpg"), dpi=190, pil_kwargs={"quality": 92})
    plt.close(fig)

def r_ablation():
    items = load_split("data", "test")
    # 标签控制在 5 个字以内，否则 4 个标签在两个子图里会互相压住
    cfg = [
        ("①固定 γ", False, False, 0.0),
        ("②自适应 γ", True, False, 0.0),
        ("③引导滤波", True, True, 0.0),
        ("④细节回加", True, True, 0.15),
    ]
    ps, ss = [], []
    for _, l, c in items:
        pass
    for label, adaptive, denoise, detail in cfg:
        p_, s_ = [], []
        for _, low, clean in items:
            y = enhance.to_luma(low)
            g = enhance.adaptive_gamma_exponent(y) if adaptive else 0.32
            lit = np.power(np.clip(y / 255.0, 0, 1), g) * 255.0
            if denoise:
                sig = enhance._noise_sigma(lit)
                r = int(np.clip(6 * (1 + sig / 8), 2, 24))
                gd = cv2.GaussianBlur(lit, (0, 0), 1.5)
                sm = enhance._guided_filter(gd, lit, r=r, eps=1e-2)
                lit = sm + detail * (lit - sm) if detail > 0 else sm
            e = enhance.with_luma(low, np.clip(lit, 0, 255))
            p_.append(metrics.psnr(clean, e))
            s_.append(metrics.ssim(clean, e))
        ps.append(np.mean(p_))
        ss.append(np.mean(s_))

    labels = [c[0] for c in cfg]
    x = np.arange(len(cfg))
    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.1))

    for ax, vals, col, ttl, fmt in [
            (axes[0], ps, "#4f81bd", "PSNR (dB)", "{:.2f}"),
            (axes[1], ss, "#9bbb59", "SSIM", "{:.3f}")]:
        bars = ax.bar(x, vals, color=col, width=0.58, edgecolor="white")
        for i, v in enumerate(vals):
            ax.text(i, v * 1.015, fmt.format(v), ha="center", va="bottom", fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_ylabel(ttl, fontsize=11)
        ax.set_ylim(0, max(vals) * 1.16)
        ax.grid(axis="y", alpha=0.25)
        ax.set_axisbelow(True)
    axes[0].set_title("(a) PSNR", fontsize=12)
    axes[1].set_title("(b) SSIM", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "r_ablation.png"), dpi=210, bbox_inches="tight")
    plt.close(fig)
    print("  ablation:", [f"{a:.2f}/{b:.3f}" for a, b in zip(ps, ss)])


def r_scatter():
    items = load_split("data", "test")
    pts = []
    for name, fn in enhance.METHODS.items():
        if name == "None(原图)":
            continue
        ss, ts = [], []
        for _, low, clean in items:
            t0 = cv2.getTickCount()
            e = fn(low.copy())
            ts.append((cv2.getTickCount() - t0) / cv2.getTickFrequency() * 1000)
            ss.append(metrics.ssim(clean, e))
        pts.append((name, np.mean(ts), np.mean(ss)))

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    tmax = max(p[1] for p in pts)
    for name, t, s in pts:
        me = "本文" in name
        ax.scatter(t, s, s=180 if me else 80, color="#c0504d" if me else "#4f81bd",
                   zorder=3, edgecolor="white", linewidth=1.5)
        # 最右侧的点标签往左放，否则会顶到图边被裁
        if t > tmax * 0.6:
            off = (-38, 6)
        elif me:
            off = (9, -14)
        else:
            off = (8, 6)
        ax.annotate(name, (t, s), textcoords="offset points", xytext=off,
                    fontsize=10.5, fontweight="bold" if me else "normal")
    ax.set_xlabel("单张耗时 / ms（对数刻度，越左越快）", fontsize=11)
    ax.set_ylabel("SSIM —— 越高越好", fontsize=11)
    ax.set_xscale("log")
    ax.set_ylim(0.12, 0.80)
    ax.grid(alpha=0.28)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "r_scatter.png"), dpi=210, bbox_inches="tight")
    plt.close(fig)


def r_curves():
    items = load_split("data", "test")
    means = np.array([l.mean() for _, l, _ in items])
    q1, q2 = np.percentile(means, [33, 66])
    groups = [("极暗\n<%.0f" % q1, means < q1),
              ("中等\n%.0f~%.0f" % (q1, q2), (means >= q1) & (means < q2)),
              ("偏亮\n>%.0f" % q2, means >= q2)]
    show = ["HE", "CLAHE", "Gamma", "Gamma+CLAHE", "MSR", "本文方法"]
    colors = {"HE": "#a6a6a6", "CLAHE": "#e8a33d", "Gamma": "#4f81bd",
              "Gamma+CLAHE": "#9bbb59", "MSR": "#8064a2", "本文方法": "#c0504d"}
    xs = np.arange(3)
    fig, ax = plt.subplots(figsize=(6.6, 3.7))
    for m in show:
        ys = []
        for _, mask in groups:
            fn = enhance.METHODS[m]
            v = [metrics.ssim(c, fn(l.copy())) for (_, l, c), k in zip(items, mask) if k]
            ys.append(np.mean(v) if v else np.nan)
        me = m == "本文方法"
        ax.plot(xs, ys, marker="o", ms=8 if me else 5, lw=3 if me else 1.5,
                color=colors[m], label=m, zorder=3 if me else 2)
    ax.set_xticks(xs)
    ax.set_xticklabels([g[0] for g in groups], fontsize=11)
    ax.set_ylabel("SSIM（档内平均）", fontsize=10.5)
    ax.set_xlabel("按输入平均亮度分档", fontsize=10.5)
    ax.set_ylim(0, 0.92)
    # 图例放到坐标区外面，否则会压住"本文方法"那条红线
    ax.legend(fontsize=9.5, ncol=3, loc="lower left",
              bbox_to_anchor=(0.0, 1.01, 1.0, 0.15), mode="expand",
              frameon=False, borderaxespad=0.2)
    ax.grid(alpha=0.25)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "r_curves.png"), dpi=210, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def r_compare(names=("test_026", "test_029"), cols=3):
    """对比网格：每个方法一格，标签只写方法名，指标另外用表呈现，
    这样格子可以大一些、标签可以清楚一些。"""
    font = _load_font(20)
    items = load_split("data", "test")
    for nm in names:
        hit = [t for t in items if os.path.splitext(t[0])[0] == nm]
        if not hit:
            continue
        name, low, clean = hit[0]
        tiles = [(clean, "真值"), (low, "低照度输入")]
        for mname, fn in enhance.METHODS.items():
            if mname == "None(原图)":
                continue
            tiles.append((fn(low.copy()), mname))

        h, w = clean.shape[:2]
        pad, bar = 8, 34
        rows = int(np.ceil(len(tiles) / cols))
        LM = 10  # 左边距，防止标签被裁
        canvas = Image.new("RGB", (cols * (w + pad) + pad + LM,
                                  rows * (h + bar + pad) + pad), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        for i, (t, label) in enumerate(tiles):
            r, c = divmod(i, cols)
            x0 = c * (w + pad) + pad // 2 + LM
            y0 = r * (h + bar + pad) + bar + pad // 2
            canvas.paste(Image.fromarray(cv2.cvtColor(t, cv2.COLOR_BGR2RGB)), (x0, y0))
            draw.text((x0, y0 - bar + 4), label, fill=(20, 20, 20), font=font)
        canvas.save(os.path.join(OUT, f"r_{nm}.jpg"), quality=90, optimize=True)
        print("  ", nm, canvas.size)


def r_photo():
    img = cv2.imread("demo_photo/night_demo.jpg")
    tiles = [(img, "输入照片")]
    # 一共 7 个方法 + 输入 = 8 格，正好填满 2×4
    for m in ["HE", "CLAHE", "Gamma", "Gamma+CLAHE", "SSR", "MSR", "本文方法"]:
        tiles.append((enhance.METHODS[m](img.copy()), m))
    font = _load_font(22)
    h, w = img.shape[:2]
    pad, bar = 8, 36
    LM = 12
    COLS, ROWS = 2, 4
    canvas = Image.new("RGB", (COLS * (w + pad) + pad + LM,
                               ROWS * (h + bar + pad) + pad), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    for i, (t, label) in enumerate(tiles):
        r, c = divmod(i, COLS)
        x0 = c * (w + pad) + pad // 2 + LM
        y0 = r * (h + bar + pad) + bar + pad // 2
        canvas.paste(Image.fromarray(cv2.cvtColor(t, cv2.COLOR_BGR2RGB)), (x0, y0))
        draw.text((x0, y0 - bar + 5), label, fill=(20, 20, 20), font=font)
    canvas.save(os.path.join(OUT, "r_photo.jpg"), quality=90, optimize=True)
    print("  photo", canvas.size)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    r_samples()
    r_hist()
    r_ablation()
    r_scatter()
    r_curves()
    r_compare()
    r_photo()
    print("done")
