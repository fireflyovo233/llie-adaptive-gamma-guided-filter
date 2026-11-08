# -*- coding: utf-8 -*-
"""
run_bench.py
在 data/ 上跑全部方法，输出汇总指标表（CSV / Markdown）和可视化网格图。

用法：
    python run_bench.py --data data --out results
    python run_bench.py --data data --out results --workers 1
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from collections import defaultdict

import cv2
import numpy as np

import enhance
import metrics


def load_split(data_dir: str, split: str):
    """按 meta.json 里的 split 字段取文件名，保证训练/测试划分固定。"""
    meta_path = os.path.join(data_dir, "meta.json")
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
        names = [it["name"] for it in meta["items"] if it["split"] == split]
    else:  # 没有元数据就按文件名前缀猜
        names = [os.path.basename(p) for p in
                 sorted(glob.glob(os.path.join(data_dir, "low", f"{split}_*.png")))]
    out = []
    for n in names:
        low = cv2.imread(os.path.join(data_dir, "low", n), cv2.IMREAD_COLOR)
        clean = cv2.imread(os.path.join(data_dir, "clean", n), cv2.IMREAD_COLOR)
        if low is not None and clean is not None:
            out.append((n, low, clean))
    return out


def build_niqe(data_dir: str):
    """用 clean 图（自然图像替代）估计 NIQE 参考分布。"""
    refs = []
    for p in sorted(glob.glob(os.path.join(data_dir, "clean", "*.png"))):
        im = cv2.imread(p, cv2.IMREAD_COLOR)
        if im is not None:
            refs.append(im)
    return metrics.NIQE(refs) if refs else None


def run(data_dir="data", out_dir="results", split="test", save_vis=True):
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "enhanced"), exist_ok=True)

    items = load_split(data_dir, split)
    if not items:
        raise SystemExit(f"{data_dir} 下没有找到 {split} 数据，请先运行 make_dataset.py")
    print(f"共 {len(items)} 张 {split} 图，方法数 {len(enhance.METHODS)}")

    niqe = build_niqe(data_dir)
    # 低照度原图自身也有一个分数，作为参照下限
    rows = []
    for name, low, clean in items:
        low_scores = metrics.all_metrics(clean, low, low, niqe)
        rows.append({"image": name, "method": "None(原图)", "time_ms": 0.0, **low_scores})
        for mname, fn in enhance.METHODS.items():
            if mname == "None(原图)":
                continue
            t0 = cv2.getTickCount()
            enh = fn(low.copy())
            t_ms = (cv2.getTickCount() - t0) / cv2.getTickFrequency() * 1000.0
            rows.append({"image": name, "method": mname, "time_ms": t_ms,
                         **metrics.all_metrics(clean, low, enh, niqe)})
            cv2.imwrite(os.path.join(out_dir, "enhanced",
                                     f"{os.path.splitext(name)[0]}__{mname.replace('+', '_').replace('(', '_').replace(')', '')}.png"),
                        enh)
        print("  done:", name)

    # ---- 汇总 ----
    keys = ["PSNR", "SSIM", "LOE", "NIQE", "Entropy", "Contrast", "AvgGrad", "time_ms"]
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for k in keys:
            agg[r["method"]][k].append(r[k])

    summary = {}
    for m, d in agg.items():
        summary[m] = {k: float(np.mean(v)) for k, v in d.items()}

    with open(os.path.join(out_dir, "per_image.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["image", "method", "time_ms"] + keys[:7])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})

    with open(os.path.join(out_dir, "summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["method"] + keys)
        for m in enhance.METHODS:
            w.writerow([m] + [f"{summary[m][k]:.4f}" for k in keys])

    md = ["| 方法 | PSNR↑ | SSIM↑ | LOE↓ | NIQE↓ | 熵↑ | 对比度↑ | 平均梯度↑ | 耗时(ms) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m in enhance.METHODS:
        s = summary[m]
        md.append(f"| {m} | {s['PSNR']:.2f} | {s['SSIM']:.4f} | {s['LOE']:.1f} | "
                  f"{s['NIQE']:.3f} | {s['Entropy']:.3f} | {s['Contrast']:.1f} | "
                  f"{s['AvgGrad']:.2f} | {s['time_ms']:.1f} |")
    table = "\n".join(md)
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print("\n" + table)

    # ---- 可视化网格：第一行是真值/输入，后面每格一个方法 ----
    if save_vis:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise SystemExit("画对比图需要 Pillow：pip install pillow")

        font = _load_font()
        for name, low, clean in items:
            tiles = [(clean, "真值 GT"), (low, "低照度输入")]
            for mname, fn in enhance.METHODS.items():
                if mname == "None(原图)":
                    continue
                e = fn(low.copy())
                sub = {r["method"]: r for r in rows if r["image"] == name}
                lab = f"{mname}  PSNR {sub[mname]['PSNR']:.2f} / SSIM {sub[mname]['SSIM']:.3f}"
                tiles.append((e, lab))
            _save_grid(tiles, os.path.join(out_dir, f"compare_{os.path.splitext(name)[0]}.jpg"), font)
        print(f"\n对比图已写入 {out_dir}/compare_*.jpg")

    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return summary, rows


def _load_font(size=15):
    """找一个能显示中文的字体。Windows / Linux / macOS 都试一遍，
    找不到就退回默认位图字体（此时中文会显示成方块，但不影响图本身）。"""
    from PIL import ImageFont
    cands = [
        "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _save_grid(tiles, path, font, cols=3):
    """把 (图像, 标签) 列表拼成网格，标签写在每格上方。"""
    import PIL.Image
    import PIL.ImageDraw
    n = len(tiles)
    cols = min(cols, n)
    rows = int(np.ceil(n / cols))
    h, w = tiles[0][0].shape[:2]
    pad, bar = 6, 24
    canvas = PIL.Image.new("RGB", (cols * (w + pad) + pad,
                                   rows * (h + bar + pad) + pad), (255, 255, 255))
    draw = PIL.ImageDraw.Draw(canvas)
    for i, (t, label) in enumerate(tiles):
        r, c = divmod(i, cols)
        x0 = c * (w + pad) + pad // 2
        y0 = r * (h + bar + pad) + bar + pad // 2
        rgb = cv2.cvtColor(t.astype(np.uint8), cv2.COLOR_BGR2RGB)
        canvas.paste(PIL.Image.fromarray(rgb), (x0, y0))
        draw.text((x0, y0 - bar + 3), label, fill=(0, 0, 0), font=font)
    # 存 JPEG 而不是 PNG：这类网格图 PNG 无损要 1.5 MB，JPEG q=88 只要 0.23 MB，
    # 肉眼看不出差别，进 git 仓库也不会把体积撑爆。
    canvas.save(path.replace(".png", ".jpg"), quality=88, optimize=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="results")
    ap.add_argument("--split", default="test")
    ap.add_argument("--no-vis", action="store_true")
    a = ap.parse_args()
    run(a.data, a.out, a.split, not a.no_vis)
