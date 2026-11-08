# -*- coding: utf-8 -*-
"""
run_photo.py
对真实照片（不是合成数据）跑所有方法，只做定性对比。

真实照片没有真值，所以不能算 PSNR / SSIM，只算无参考指标
（NIQE、熵、对比度、平均梯度），并输出对比图。

用法：
    python run_photo.py --input my_photo.jpg --out results/photo
    python run_photo.py --input ./photos --out results/photo
"""
from __future__ import annotations

import argparse
import glob
import os

import cv2
import numpy as np

import enhance
import metrics
from run_bench import _load_font, _save_grid


def collect(path):
    if os.path.isdir(path):
        out = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.JPG"):
            out += glob.glob(os.path.join(path, ext))
        return sorted(out)
    return [path]


def run_one(img_path, out_dir, niqe_ref_dir="data/clean"):
    img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"读不到图片：{img_path}")
    # 太大的图先缩一下，不然 MSR 会很慢
    h, w = img.shape[:2]
    if max(h, w) > 1080:
        s = 1080 / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)

    refs = [cv2.imread(p) for p in sorted(glob.glob(os.path.join(niqe_ref_dir, "*.png")))]
    refs = [r for r in refs if r is not None]
    niqe = metrics.NIQE(refs) if refs else None

    tiles = [(img, "输入照片")]
    print(f"\n{os.path.basename(img_path)}  尺寸 {img.shape[1]}x{img.shape[0]}")
    print(f"  {'method':<16}{'NIQE':>8}{'熵':>8}{'对比度':>8}{'平均梯度':>10}")
    for mname, fn in enhance.METHODS.items():
        if mname == "None(原图)":
            continue
        t0 = cv2.getTickCount()
        e = fn(img.copy())
        ms = (cv2.getTickCount() - t0) / cv2.getTickFrequency() * 1000
        ni = f"{niqe.score(e):8.2f}" if niqe else "     n/a"
        print(f"  {mname:<16}{ni}{metrics.entropy(e):8.3f}"
              f"{metrics.contrast(e):8.1f}{metrics.mean_gradient(e):10.2f}   {ms:.0f}ms")
        tiles.append((e, mname))
        cv2.imwrite(os.path.join(out_dir, f"{os.path.splitext(os.path.basename(img_path))[0]}__{mname.replace('+', '_')}.png"), e)

    _save_grid(tiles, os.path.join(out_dir, f"photo_{os.path.splitext(os.path.basename(img_path))[0]}.jpg"),
               _load_font())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="单张图片或图片文件夹")
    ap.add_argument("--out", default="results/photo")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for p in collect(a.input):
        run_one(p, a.out)
