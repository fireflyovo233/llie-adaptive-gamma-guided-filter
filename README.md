# 低照度图像增强：自适应 Gamma 与引导滤波的联合方案

《图像处理与分析》课程报告配套代码。

一句话概括：**低照度图不能只想着"提亮"，提亮的同时必须把被一起放大的噪声压下去。**
本项目比较了 7 种经典做法，并提出了一条"自适应 Gamma 提亮 + 引导滤波压噪"的两步管线，
在自建合成数据集上把 SSIM 从 0.54（固定 Gamma）提到 0.74，NIQE 从 241 降到 9.9。

---

## 快速开始

```bash
# 1. 装依赖（Python 3.9+）
pip install -r requirements.txt

# 2. 生成数据集（约 5 秒，不联网）
python make_dataset.py --out data --n-train 24 --n-test 8

# 3. 跑全部方法并出指标表
python run_bench.py --data data --out results

# 4. 生成报告用图（样例图、直方图、消融、SSIM-耗时、分档曲线）
python make_figures.py --data data --out results/figures

# 5. 对自己的照片做增强（可选）
python run_photo.py --input 你的照片.jpg --out results/photo

# 6. 生成课程报告（需要 python-docx）
python build_report.py
```

跑完 `results/summary.md` 里就是那张总表，`results/compare_*.png` 是逐图对比网格。

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `make_dataset.py` | 合成低照度数据集：真值图 × 退化成因（暗角 + 阴影 + Gamma + 泊松-高斯噪声） |
| `enhance.py` | 7 种增强方法，**核心方法在 `proposed()`** |
| `metrics.py` | 评价指标：PSNR / SSIM（有参考）、LOE / NIQE / 熵 / 对比度 / 平均梯度（无参考） |
| `run_bench.py` | 批量跑全部方法，输出 CSV / Markdown 指标表和对比图 |
| `tune.py` | 参数网格搜索（**只在 train 划分上跑**） |
| `make_figures.py` | 生成通用插图与消融实验 |
| `make_report_figs.py` | 生成报告专用的高清插图（`r_*.jpg`），字号按 A4 缩放比调过 |
| `build_report.py` | 用 python-docx 生成课程报告 `1.报告.docx` |
| `run_photo.py` | 对真实照片做定性对比（无真值，因此只算无参考指标） |

目录约定：

```
data/clean/   真值图（程序合成）
data/low/     对应的低照度观测图
data/meta.json  每张图的退化参数（gamma、kappa、阴影位置、均值）
```

---

## 方法一览

| 方法 | 核心思想 | 主要问题 |
|---|---|---|
| HE | 累积分布函数把直方图铺平 | 低照度图像素全堆在 0~30，CDF 那里近乎垂直，噪声被指数放大 |
| CLAHE | 分块均衡 + 裁剪峰值 | 治对比度不治亮度，输出仍偏暗 |
| Gamma | `out = 255·(y/255)^g` | 全局常数 g，一张图合适另一张就过曝 |
| Gamma+CLAHE | 先提亮再补局部对比 | 比单独用 CLAHE 好，但仍是"提亮"，噪声原样放大 |
| SSR / MSR | 对数域去掉低频照明 | 噪声在中高频，去低频等于把噪声留下，画面变雪花 |
| **本文方法** | 自适应 Gamma 提亮 → 引导滤波压噪 | 见下 |

### 本文方法的两处关键设计

**① 目标亮度随"有多暗"浮动，不固定。**

取亮度 10% 分位数 `p`（代表这张图有多暗），解 `p^g = target` 得 gamma。
但 `target` 不是常数：

```
p < 0.04  → target = 0.35   （极暗，使劲提）
p > 0.20  → target = 0.60   （已经不太暗，克制点）
中间线性插值
```

如果 target 固定成 0.5，本来亮度正常的图会被强行推到 0.5，等于凭空过曝。
实测中不加上这个约束，几张本身不暗的图 PSNR 从 19.7 直接掉到 14.4。

**② 压噪必须放在提亮之后。**

Gamma 的导数是 `g·(y/255)^(g-1)`，在 y 接近 0 时趋于无穷。
暗部噪声经过提亮会被放大十几倍，所以：

- 先压噪再提亮 → 压的是"放大前"的噪声，提亮后又原样放大回来，白忙
- **先提亮再压噪** → 压的才是已经放大到肉眼可见的那份噪声

去噪用引导滤波（He et al., 2010），引导图取提亮后 Y 的轻度平滑版：
拿平滑版做引导可以避免噪声把滤波系数 `a` 带偏；而引导滤波在边缘处 `a≈1`、`b≈0`，
不会跨越边缘平滑，所以不像纯高斯模糊那样把画面整体摸软。

---

## 主要结果（test 划分，8 张）

| 方法 | PSNR↑ | SSIM↑ | LOE↓ | NIQE↓ | 耗时(ms) |
|---|---|---|---|---|---|
| HE | 10.95 | 0.170 | 0.2 | 313.9 | 1.3 |
| CLAHE | 8.72 | 0.280 | 7.5 | 249.8 | 1.7 |
| Gamma (g=0.32) | 15.80 | 0.537 | 0.0 | 241.1 | 2.6 |
| Gamma+CLAHE | 15.13 | 0.409 | 5.0 | 279.0 | 2.9 |
| SSR | 11.44 | 0.197 | 6.2 | 311.2 | 20.3 |
| MSR | 11.33 | 0.170 | 5.8 | 317.6 | 83.6 |
| **本文方法** | **17.24** | **0.738** | 8.8 | **9.9** | 10.0 |

三点值得说：

1. **SSIM 是第二名的 1.38 倍**，而且 8 张图**逐张**都比所有基线高（8/8），不是平均被拉起来的。
   PSNR 只在 8 张里的 5 张上赢过单 Gamma——另外 3 张是输入本来就不太暗的，
   自适应把目标亮度放宽后与固定 Gamma 基本持平，这也是"不强推亮度"的代价。
2. **NIQE 从 240 级降到 9.9**，量级差异说明其它方法输出在统计上根本不像自然图像。
3. **LOE 偏高（8.8）是主动的取舍**：LOE 衡量"原来谁比谁亮"的顺序有没有被打乱。
   低照度图里大量像素挤在同一个灰度附近，本来就没有清晰亮度序。
   提亮必然把它们拉开，LOE 就上去了。对低照度增强来说，**看得见**比**保持亮度序**更重要。

### 消融

| 配置 | PSNR | SSIM |
|---|---|---|
| ① 固定 Gamma g=0.32 | 15.80 | 0.537 |
| ② 换成自适应 Gamma | 16.86 | 0.538 |
| ③ + 引导滤波压噪（默认） | **17.24** | **0.738** |
| ④ + 细节回加 0.15 | 17.23 | 0.726 |

前两步提亮，第三步压噪才是 SSIM 涨 0.21 的主力。
第四步在合成数据上是**负收益**（噪声与细节同频段，加回来会一起加），所以默认关掉 `detail=0`；
真实照片可以试 0.1~0.3。

---

## 已知局限

- **数据是合成的。** 真值由程序生成，退化模型也是我自己写的，
  所以指标只能说明"在这个退化模型下"的相对好坏，不能直接推广到任意真实夜景。
  代码里 `run_photo.py` 用真实照片做了定性验证，趋势一致（NIQE 仍是 4.07 vs 其它 31~70）。
- **SSIM 对亮度偏移极其敏感。** 本实验里所有方法的"曝光准不准"对 SSIM 的影响，
  和"结构恢复得好不好"是一个量级的。所以评价增强算法时，单看 SSIM 容易误判。
- **自适应在极端图上会失准。** 10% 分位数是个统计量，个别图（大块纯黑背景）会偏小，
  导致提亮过头。要彻底解决得做区域级估计（分块算光照图），代码里没展开。
- **没有用深度学习。** 只做了传统方法。如果要和 RetinexNet / Zero-DCE 这类比，
  需要真实配对数据集（LOL），不在本次范围内。

---

## 参考

- Land & McCann, *Lightness and Retinex Theory*, JOSA 1971
- Jobson et al., *Properties and Performance of a Center/Surround Retinex*, TIP 1997
- He et al., *Guided Image Filtering*, ECCV 2010 / TPAMI 2013
- Zuiderveld, *Contrast Limited Adaptive Histogram Equalization*, 1994
- Mittal et al., *Making a "Completely Blind" Image Quality Analyzer*, SPL 2013
- Wang et al., *Brightness Preserving Bi-Histogram Equalization*, 1997（LOE 的原始出处）

## 环境

Python 3.9+，依赖见 `requirements.txt`（numpy / opencv-python / pillow / matplotlib）。
不需要 GPU，纯 CPU 跑完全流程约 30 秒。
