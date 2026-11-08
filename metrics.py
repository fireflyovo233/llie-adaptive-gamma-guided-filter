# -*- coding: utf-8 -*-
"""
metrics.py
评价增强结果用的几个指标。分两类，报告里也是分开讨论的：

【有参考】需要真值图
  PSNR      峰值信噪比，衡量整体像素误差
  SSIM      结构相似度，衡量结构/对比度/亮度的相似性
【无参考】只有增强图，真实夜景场景就只能用这类
  LOE       亮度阶次误差 (Lightness Order Error)，衡量增强前后
            "谁比谁亮"的相对关系有没有被打乱，越低越好
  NIQE      自然图像质量评价，用自然图像的统计先验打分，越低越自然
  entropy   信息熵，衡量细节丰富程度（但会把噪声也算成信息，要结合着看）
  contrast  标准差 / 平均梯度，衡量整体对比和清晰度
"""
from __future__ import annotations

import math

import cv2
import numpy as np


# ----------------------------------------------------------------------------
# 有参考指标
# ----------------------------------------------------------------------------
def psnr(ref: np.ndarray, test: np.ndarray) -> float:
    ref = ref.astype(np.float64)
    test = test.astype(np.float64)
    mse = np.mean((ref - test) ** 2)
    if mse < 1e-10:
        return 99.0
    return 10 * math.log10(255.0 ** 2 / mse)


def _ssim_gray(ref: np.ndarray, test: np.ndarray) -> float:
    """标准 SSIM，11x11 高斯窗，sigma=1.5，C1/C2 取常用常数。"""
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    ref = ref.astype(np.float64)
    test = test.astype(np.float64)
    k = cv2.getGaussianKernel(11, 1.5)
    win = k @ k.T

    mu1 = cv2.filter2D(ref, -1, win)
    mu2 = cv2.filter2D(test, -1, win)
    mu1_sq, mu2_sq, mu1_mu2 = mu1 ** 2, mu2 ** 2, mu1 * mu2
    s1 = cv2.filter2D(ref ** 2, -1, win) - mu1_sq
    s2 = cv2.filter2D(test ** 2, -1, win) - mu2_sq
    s12 = cv2.filter2D(ref * test, -1, win) - mu1_mu2
    num = (2 * mu1_mu2 + C1) * (2 * s12 + C2)
    den = (mu1_sq + mu2_sq + C1) * (s1 + s2 + C2)
    return float(np.mean(num / den))


def ssim(ref: np.ndarray, test: np.ndarray) -> float:
    """彩色图按分量平均，与人眼对彩色的感知大致一致。"""
    vals = [_ssim_gray(ref[:, :, c], test[:, :, c]) for c in range(3)]
    return float(np.mean(vals))


# ----------------------------------------------------------------------------
# 无参考指标
# ----------------------------------------------------------------------------
def loe(img_low: np.ndarray, img_enh: np.ndarray, step: int = 4) -> float:
    """亮度阶次误差。
    LOE = (1/(m*n)) * sum sum U(L(x), L(y)) XOR U(Le(x), Le(y))
    U(p,q)=1 若 p>=q。为控制计算量，按 step 采样。
    越低说明原本暗的东西增强后还是偏暗，亮度顺序没乱。
    """
    a = cv2.cvtColor(img_low, cv2.COLOR_BGR2GRAY).astype(np.int16)[::step, ::step]
    b = cv2.cvtColor(img_enh, cv2.COLOR_BGR2GRAY).astype(np.int16)[::step, ::step]
    n = a.size
    lo, hi = a.min(), a.max()
    span = max(hi - lo, 1)
    # 在 [0,1] 上比较；对低照度图先做线性拉伸，避免暗部全部并列
    a = (a - lo) / span
    b = b / 255.0
    # 分块计算，避免 n*n 的矩阵爆内存
    total = 0
    flat_a, flat_b = a.ravel(), b.ravel()
    chunk = 256
    for i in range(0, n, chunk):
        pa = flat_a[i:i + chunk, None] >= flat_a[None, :]
        pb = flat_b[i:i + chunk, None] >= flat_b[None, :]
        total += int(np.count_nonzero(pa != pb))
    return 100.0 * total / (n * n)


def entropy(img: np.ndarray) -> float:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([g], [0], None, [256], [0, 256]).ravel()
    p = hist / max(hist.sum(), 1)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def contrast(img: np.ndarray) -> float:
    """灰度标准差，最朴素的全局对比度度量。"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return float(g.std())


def mean_gradient(img: np.ndarray) -> float:
    """平均梯度：衡量清晰度，噪声也会抬高它，所以要和 NIQE 一起看。"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    return float(np.mean(np.sqrt(gx ** 2 + gy ** 2)) / 8.0)


class NIQE:
    """NIQE (Mittal et al., 2013) 的简化实现。

    原理：自然图像的一阶（MSCN 系数）和二阶（相邻乘积）统计量服从
    一种比较稳定的多元高斯分布。先在一批自然图像上估计参考分布的
    均值 mu 和协方差 cov，再对测试图计算同样的统计量，
    用两者的马氏距离作为分数。分数越低越接近自然图像。

    这里用 data/clean 里的真值图作为"自然图像"参考集，所以分数是
    "相对这批参考图"的，横向比较各方法时才有效。
    """

    def __init__(self, refs=None):
        self.mu = None
        self.cov_inv = None
        if refs:
            feats = np.array([self._features(r) for r in refs])
            self.mu = feats.mean(axis=0)
            cov = np.cov(feats.T) + np.eye(feats.shape[1]) * 1e-6
            self.cov_inv = np.linalg.inv(cov)

    @staticmethod
    def _mscn(gray: np.ndarray) -> np.ndarray:
        g = gray.astype(np.float32)
        mu = cv2.GaussianBlur(g, (7, 7), 7 / 6)
        var = cv2.GaussianBlur(g * g, (7, 7), 7 / 6) - mu ** 2
        var = np.maximum(var, 0)
        return (g - mu) / (np.sqrt(var) + 1.0)

    def _features(self, img: np.ndarray) -> np.ndarray:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        m = self._mscn(g)
        # 用 4 个方向上的相邻乘积刻画二阶结构
        pairs = [m[:, :-1] * m[:, 1:], m[:-1, :] * m[1:, :],
                 m[:-1, :-1] * m[1:, 1:], m[:-1, 1:] * m[1:, :-1]]
        f = [m.mean(), m.std()]
        for p in pairs:
            f += list(np.percentile(p, [10, 50, 90]))
        return np.array(f, dtype=np.float64)

    def score(self, img: np.ndarray) -> float:
        if self.mu is None:
            raise RuntimeError("NIQE 需要先用参考图估计分布")
        d = self._features(img) - self.mu
        return float(np.sqrt(d @ self.cov_inv @ d))


def all_metrics(ref, low, enh, niqe: NIQE | None = None) -> dict:
    out = {
        "PSNR": psnr(ref, enh),
        "SSIM": ssim(ref, enh),
        "LOE": loe(low, enh),
        "Entropy": entropy(enh),
        "Contrast": contrast(enh),
        "AvgGrad": mean_gradient(enh),
    }
    if niqe is not None:
        out["NIQE"] = niqe.score(enh)
    return out
