# -*- coding: utf-8 -*-
"""
tune.py
在 **train 划分**上做参数网格搜索，把结果打印出来，方便抄回 enhance.py 的默认值。

注意：只在 train 上搜索，test 只用来出最终报告的数字，
否则测出来的成绩是"调参调出来的"，不能算数。

用法：
    python tune.py --data data --what gamma
    python tune.py --data data --what all
"""
from __future__ import annotations

import argparse
import itertools

import cv2
import numpy as np

import enhance
import metrics
from run_bench import load_split


def mean_scores(data_dir, fn, grid, limit=None):
    items = load_split(data_dir, "train")
    if limit:
        items = items[:limit]
    results = []
    for params in grid:
        ps, ss, lo, ni = [], [], [], []
        for name, low, clean in items:
            e = fn(low.copy(), **params)
            ps.append(metrics.psnr(clean, e))
            ss.append(metrics.ssim(clean, e))
            lo.append(metrics.loe(low, e))
        results.append((params, np.mean(ps), np.mean(ss), np.mean(lo)))
    results.sort(key=lambda r: -r[1])
    return results


def show(tag, results, topk=6):
    print(f"\n=== {tag} （按 PSNR 排序，前 {min(topk, len(results))} 组）===")
    print(f"{'params':<44}{'PSNR':>8}{'SSIM':>9}{'LOE':>8}")
    for p, a, b, c in results[:topk]:
        ps = ", ".join(f"{k}={v}" for k, v in p.items())
        print(f"{ps:<44}{a:8.2f}{b:9.4f}{c:8.1f}")
    best = results[0]
    print(f"最优：{best[0]}  -> PSNR={best[1]:.2f} SSIM={best[2]:.4f} LOE={best[3]:.1f}")
    return best


def main(data_dir="data", what="all", limit=None):
    if what in ("all", "gamma"):
        grid = [dict(g=g) for g in [0.25, 0.28, 0.30, 0.32, 0.35, 0.38, 0.42, 0.45, 0.5]]
        show("Gamma 的 g", mean_scores(data_dir, enhance.gamma, grid, limit))
        # 打印每个 g 下增强图的平均亮度，看是否过曝
        items = load_split(data_dir, "train")[:6]
        print("\n不同 g 下的平均亮度（参考：真值约 120）：")
        for g in [0.25, 0.30, 0.35, 0.42]:
            ms = [enhance.gamma(l.copy(), g=g).mean() for _, l, _ in items]
            print(f"  g={g:.2f}  enh_mean={np.mean(ms):6.1f}")

    if what in ("all", "clahe"):
        grid = [dict(clip=c, tiles=t) for c in [1.5, 2.0, 3.0, 4.0]
                for t in [4, 8, 16]]
        show("CLAHE 的 clip / tiles", mean_scores(data_dir, enhance.clahe, grid, limit))

    if what in ("all", "gc"):
        grid = [dict(g=g, clip=c, tiles=8) for g in [0.28, 0.32, 0.36, 0.40]
                for c in [1.5, 2.0, 3.0]]
        show("Gamma+CLAHE", mean_scores(data_dir, enhance.gamma_clahe, grid, limit))

    if what in ("all", "ssr"):
        grid = [dict(sigma=s) for s in [5, 15, 30, 80]]
        show("SSR 的 sigma", mean_scores(data_dir, enhance.ssr, grid, limit))

    if what in ("all", "msr"):
        grid = [dict(sigmas=s) for s in [(5, 15, 30), (15, 80, 250), (10, 30, 90)]]
        show("MSR 的多尺度", mean_scores(data_dir, enhance.msr, grid, limit))

    if what in ("all", "gif"):
        grid = [dict(r=r, eps=e) for r in [8, 16, 32, 64] for e in [1e-3, 1e-2, 1e-1]]
        show("Retinex+GIF 的 r / eps", mean_scores(data_dir, enhance.proposed, grid, limit))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--what", default="all")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    main(a.data, a.what, a.limit)
