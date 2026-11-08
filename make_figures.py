# -*- coding: utf-8 -*-
"""
make_figures.py
生成报告需要的图：
    fig1_samples.png       数据集样例（真值 / 低照度）
    fig2_histogram.png     低照度前后的亮度直方图 + Gamma 曲线
    fig3_ablation.png      消融实验的柱状图
    fig4_scatter.png       SSIM vs 耗时 散点（性价比）
    fig5_curves.png        不同方法对"暗度"的敏感程度曲线

同时输出 ablation.csv，供报告中的表格使用。

用法：python make_figures.py --data data --out results/figures
"""
from __future__ import annotations

import argparse
import csv
import glob
import os

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import enhance
import metrics
from run_bench import load_split

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def fig_samples(data_dir, out):
    items = load_split(data_dir, "test")[:4]
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.4))
    for i, (n, low, clean) in enumerate(items):
        axes[0, i].imshow(cv2.cvtColor(clean, cv2.COLOR_BGR2RGB))
        axes[0, i].set_title(f"真值  {n}", fontsize=10)
        axes[1, i].imshow(cv2.cvtColor(low, cv2.COLOR_BGR2RGB))
        axes[1, i].set_title(f"低照度 (均值 {low.mean():.1f})", fontsize=10)
        for a in (axes[0, i], axes[1, i]):
            a.axis("off")
    axes[0, 0].set_ylabel("真值", fontsize=11)
    axes[1, 0].set_ylabel("输入", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig1_samples.jpg"), dpi=170, pil_kwargs={"quality": 90})
    plt.close(fig)


def fig_histogram(data_dir, out):
    """一张图说明问题：低照度像素全挤在低灰度端，直方图是尖峰。"""
    n, low, clean = load_split(data_dir, "test")[2]
    y_low = enhance.to_luma(low)
    y_gt = enhance.to_luma(clean)
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))

    axes[0].imshow(cv2.cvtColor(low, cv2.COLOR_BGR2RGB))
    axes[0].set_title("低照度输入", fontsize=11)
    axes[0].axis("off")

    axes[1].hist(y_gt.ravel(), bins=64, range=(0, 255), color="#7f9fbf",
                 label="真值亮度分布")
    axes[1].hist(y_low.ravel(), bins=64, range=(0, 255), color="#c0504d",
                 alpha=0.75, label="低照度亮度分布")
    axes[1].set_xlim(0, 255)
    axes[1].set_xlabel("灰度值")
    axes[1].set_ylabel("像素数")
    axes[1].set_title("亮度直方图对比", fontsize=11)
    axes[1].legend(fontsize=9)

    x = np.linspace(0, 1, 256)
    for g, c in [(1.0, "#999999"), (1 / 2.4, "#4f81bd"), (1 / 1.6, "#9bbb59"),
                 (0.32, "#c0504d")]:
        axes[2].plot(x * 255, 255 * x ** g, color=c, label=f"g={g:.2f}")
    axes[2].plot([0, 255], [0, 255], "--", color="#dddddd", lw=1)
    axes[2].set_xlabel("输入灰度")
    axes[2].set_ylabel("输出灰度")
    axes[2].set_title("Gamma 曲线形状", fontsize=11)
    axes[2].legend(fontsize=9)
    axes[2].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig2_histogram.jpg"), dpi=170, pil_kwargs={"quality": 90})
    plt.close(fig)


# ---------------------------------------------------------------------------
# 消融实验：从"仅提亮"逐步加到"完整方法"，看每一步贡献多少
# ---------------------------------------------------------------------------
def _pipe(y, g, nr, neps, pre_blur, detail, denoise=True, adaptive=True):
    if adaptive:
        g_use = enhance.adaptive_gamma_exponent(y)
    else:
        g_use = g
    lit = np.power(np.clip(y / 255.0, 0, 1), g_use) * 255.0
    if denoise:
        sigma = enhance._noise_sigma(lit)
        r = int(np.clip(nr * (1.0 + sigma / 8.0), 2, 24))
        guide = cv2.GaussianBlur(lit, (0, 0), pre_blur)
        sm = enhance._guided_filter(guide, lit, r=r, eps=neps)
        lit = sm + detail * (lit - sm) if detail > 0 else sm
    return np.clip(lit, 0, 255)


def ablation(data_dir, out):
    items = load_split(data_dir, "test")
    configs = [
        ("①固定Gamma g=0.32\n(仅提亮)", dict(adaptive=False, denoise=False, g=0.32,
                                         nr=6, neps=1e-2, pre_blur=1.5, detail=0)),
        ("②自适应Gamma\n(仅提亮)", dict(adaptive=True, denoise=False, g=0.32,
                                     nr=6, neps=1e-2, pre_blur=1.5, detail=0)),
        ("③自适应+引导滤波\n去噪", dict(adaptive=True, denoise=True, g=0.32,
                                    nr=6, neps=1e-2, pre_blur=1.5, detail=0)),
        ("④完整方法\n(本文默认)", dict(adaptive=True, denoise=True, g=0.32,
                                    nr=6, neps=1e-2, pre_blur=1.5, detail=0.0)),
        ("⑤附带项:细节回加\n0.15", dict(adaptive=True, denoise=True, g=0.32,
                                    nr=6, neps=1e-2, pre_blur=1.5, detail=0.15)),
    ]
    rows = []
    for label, cfg in configs:
        ps, ss, ni, lo = [], [], [], []
        for _, low, clean in items:
            y = enhance.to_luma(low)
            ye = _pipe(y, **cfg)
            e = enhance.with_luma(low, ye)
            ps.append(metrics.psnr(clean, e))
            ss.append(metrics.ssim(clean, e))
            lo.append(metrics.loe(low, e))
        rows.append(dict(name=label.replace("\n", " "), PSNR=np.mean(ps),
                         SSIM=np.mean(ss), LOE=np.mean(lo)))

    with open(os.path.join(out, "ablation.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["name", "PSNR", "SSIM", "LOE"])
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))
    names = [r["name"] for r in rows]
    xs = np.arange(len(rows))
    ax = axes[0]
    ax.bar(xs, [r["PSNR"] for r in rows], color="#4f81bd", width=0.55)
    ax.set_xticks(xs)
    ax.set_xticklabels(names, fontsize=7.5, rotation=16, ha="right")
    ax.set_ylabel("PSNR (dB)")
    ax.set_title("消融：PSNR", fontsize=11)
    for i, r in enumerate(rows):
        ax.text(i, r["PSNR"] + 0.25, f"{r['PSNR']:.2f}", ha="center", fontsize=9)
    ax.set_ylim(0, max(r["PSNR"] for r in rows) * 1.2)

    ax = axes[1]
    ax.bar(xs, [r["SSIM"] for r in rows], color="#9bbb59", width=0.55)
    ax.set_xticks(xs)
    ax.set_xticklabels(names, fontsize=7.5, rotation=16, ha="right")
    ax.set_ylabel("SSIM")
    ax.set_title("消融：SSIM", fontsize=11)
    for i, r in enumerate(rows):
        ax.text(i, r["SSIM"] + 0.012, f"{r['SSIM']:.3f}", ha="center", fontsize=9)
    ax.set_ylim(0, max(r["SSIM"] for r in rows) * 1.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig3_ablation.png"), dpi=170)
    plt.close(fig)
    for r in rows:
        print(f"  {r['name']:<28} PSNR={r['PSNR']:.2f} SSIM={r['SSIM']:.4f} LOE={r['LOE']:.1f}")
    return rows


def fig_scatter(data_dir, out):
    """各方法的 SSIM-耗时 折中图。左上角是最理想的位置。"""
    items = load_split(data_dir, "test")
    pts = []
    for mname, fn in enhance.METHODS.items():
        if mname == "None(原图)":
            continue
        ss, ts = [], []
        for _, low, clean in items:
            t0 = cv2.getTickCount()
            e = fn(low.copy())
            ts.append((cv2.getTickCount() - t0) / cv2.getTickFrequency() * 1000)
            ss.append(metrics.ssim(clean, e))
        pts.append((mname, np.mean(ts), np.mean(ss)))

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for name, t, s in pts:
        color = "#c0504d" if ("本文" in name) else "#4f81bd"
        ax.scatter(t, s, s=110 if "本文" in name else 60, color=color,
                   zorder=3, edgecolor="white", linewidth=1.2)
        ax.annotate(name, (t, s), textcoords="offset points", xytext=(7, 5), fontsize=9)
    ax.set_xlabel("单张耗时 (ms)  —— 越左越好")
    ax.set_ylabel("SSIM —— 越高越好")
    ax.set_xscale("log")
    ax.grid(alpha=0.25)
    ax.set_title("SSIM 与耗时的折中关系（左上为最优）", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig4_scatter.png"), dpi=170)
    plt.close(fig)


def fig_curves(data_dir, out):
    """把测试集按输入的暗度分成三档，画各方法在每档上的平均 SSIM。

    一开始想画"逐图 SSIM vs 输入均值"的折线，但那样每个点是不同的图，
    内容本身不同，折线会出现毫无意义的跳变——看起来像方法不稳定，
    其实只是换了一张图。所以改成按暗度分档取平均，才是可比的。"""
    items = load_split(data_dir, "test")
    means = np.array([low.mean() for _, low, _ in items])
    q1, q2 = np.percentile(means, [33, 66])
    groups = [("暗 (mean<%.0f)" % q1, means < q1),
              ("中 (%.0f~%.0f)" % (q1, q2), (means >= q1) & (means < q2)),
              ("较亮 (>%.0f)" % q2, means >= q2)]

    show = ["HE", "CLAHE", "Gamma", "Gamma+CLAHE", "MSR", "本文方法"]
    data = {m: [] for m in show}
    for _, mask in groups:
        for m in show:
            fn = enhance.METHODS[m]
            vals = [metrics.ssim(clean, fn(low.copy()))
                    for (_, low, clean), mk in zip(items, mask) if mk]
            data[m].append(np.mean(vals) if vals else np.nan)

    xs = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    colors = {"HE": "#8c8c8c", "CLAHE": "#e8a33d", "Gamma": "#4f81bd",
              "Gamma+CLAHE": "#9bbb59", "MSR": "#8064a2", "本文方法": "#c0504d"}
    for m in show:
        ax.plot(xs, data[m], marker="o", ms=6,
                lw=2.2 if m == "本文方法" else 1.4, color=colors[m], label=m)
    ax.set_xticks(xs)
    ax.set_xticklabels([g[0] for g in groups], fontsize=9.5)
    ax.set_ylabel("平均 SSIM")
    ax.set_title("按输入暗度分档后的平均表现（检验方法是否在暗图上崩掉）", fontsize=10.5)
    ax.set_ylim(0, 0.9)
    ax.legend(fontsize=9, ncol=2, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig5_curves.png"), dpi=170)
    plt.close(fig)
    for g, m in zip([x[0] for x in groups], range(3)):
        print(f"  {g}: " + ", ".join(f"{k}={data[k][m]:.3f}" for k in show))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="results/figures")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fig_samples(a.data, a.out)
    print("fig1 ok")
    fig_histogram(a.data, a.out)
    print("fig2 ok")
    ablation(a.data, a.out)
    print("fig3 ok")
    fig_scatter(a.data, a.out)
    print("fig4 ok")
    fig_curves(a.data, a.out)
    print("fig5 ok")
