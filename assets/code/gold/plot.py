#!/usr/bin/env python3
"""黄金隐含实际利率模型回测 — 可视化（研究用途，只读）。

四联图：
  (1) 制度断裂散点：金价 vs 10Y TIPS，2006–21 vs 2022–26 两个制度，各自拟合线
  (2) 中枢抬升：同一实际利率区间下，两个制度的金价均值对比
  (3) 隐含实际利率 vs TIPS 时序（复现用户图）+ 2022 后 gap
  (4) 信号回测：静态 gapA 分位前向收益（2022+）+ 滚动 zB 事件研究
依赖 scripts/strategy_lab/gold_real_yield_backtest.py 的 load()/ols()。
"""
from __future__ import annotations
import importlib.util, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("bt", ROOT / "scripts/strategy_lab/gold_real_yield_backtest.py")
bt = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bt)

# 中文字体
for name in ("Hiragino Sans GB", "Heiti SC", "Arial Unicode MS", "PingFang SC"):
    if any(f.name == name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name; break
plt.rcParams["axes.unicode_minus"] = False
ASCII_MINUS = True  # 中文字体缺 U+2212，所有文本用 ASCII "-"
plt.rcParams.update({"figure.dpi": 130, "savefig.dpi": 150, "axes.grid": True,
                     "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9, "axes.titlesize": 11, "axes.titleweight": "bold"})

C_PRE, C_POST, C_ACC, C_NEG = "#1f77b4", "#d62728", "#2ca02c", "#7f7f7f"
OUT = ROOT / "reports/策略分析/2026-11"


def main():
    df = bt.load()
    pre = df.loc["2006-01-01":"2021-12-31"]; post = df.loc["2022-01-01":]
    bA = bt.ols(pre, ["real"], pre["lg"])
    bP = bt.ols(post, ["real"], post["lg"])
    r2A = 1 - np.var(pre.lg - (bA[0] + bA[1] * pre.real)) / np.var(pre.lg)
    r2P = 1 - np.var(post.lg - (bP[0] + bP[1] * post.real)) / np.var(post.lg)

    df["impA"] = (df.lg - bA[0]) / bA[1]
    df["impP"] = (df.lg - bP[0]) / bP[1]
    df["gapP"] = df.impP - df.real
    df["gapA"] = df.impA - df.real

    fig, ax = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle("黄金隐含实际利率模型：实际数据回测（2006–2026，数据截至 2026-11-24）",
                 fontsize=14, fontweight="bold", y=0.995)

    # ---------- (1) 制度断裂散点 ----------
    a = ax[0, 0]
    a.scatter(pre.real, pre.gold, s=4, c=C_PRE, alpha=0.25, lw=0, label=f"2006–2021 (n={len(pre)})")
    a.scatter(post.real, post.gold, s=6, c=C_POST, alpha=0.45, lw=0, label=f"2022–2026 (n={len(post)})")
    xr = np.linspace(df.real.min(), df.real.max(), 50)
    a.plot(xr, np.exp(bA[0] + bA[1] * xr), c=C_PRE, lw=2.2,
           label=f"2006–21 拟合：斜率 {bA[1]:+.3f}，R^2={r2A:.2f}")
    a.plot(xr, np.exp(bP[0] + bP[1] * xr), c=C_POST, lw=2.2,
           label=f"2022–26 拟合：斜率 {bP[1]:+.3f}，R^2={r2P:.2f}")
    a.axvline(2.77, c="k", ls=":", lw=1)
    a.scatter([df.real.iloc[-1]], [df.gold.iloc[-1]], s=90, marker="*", c="gold", edgecolor="k", zorder=5)
    a.annotate(f"当前：TIPS {df.real.iloc[-1]:.2f}% / GLD {df.gold.iloc[-1]:.0f}",
               (df.real.iloc[-1], df.gold.iloc[-1]), xytext=(0.42, 0.08), textcoords="axes fraction",
               fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.7))
    a.set_yscale("log")
    a.set_xlabel("10Y TIPS 实际利率 (%)"); a.set_ylabel("GLD 价格（对数轴，美元）")
    a.set_title("① 制度断裂：2022 后金价对实际利率的斜率由负转正")
    a.legend(fontsize=7.5, loc="upper right")

    # ---------- (2) 中枢抬升 ----------
    a = ax[0, 1]
    bins = [(-1, 0), (0, 1), (1, 2), (2, 3)]
    labs, m1, m2, ns = [], [], [], []
    for lo, hi in bins:
        p1 = pre[(pre.real >= lo) & (pre.real < hi)].gold; p2 = post[(post.real >= lo) & (post.real < hi)].gold
        if len(p1) > 20 and len(p2) > 20:
            labs.append(f"[{lo}, {hi})"); m1.append(p1.mean()); m2.append(p2.mean()); ns.append((len(p1), len(p2)))
    x = np.arange(len(labs)); w = 0.38
    a.bar(x - w / 2, m1, w, color=C_PRE, label="2006–2021 均价")
    a.bar(x + w / 2, m2, w, color=C_POST, label="2022–2026 均价")
    for i, (v1, v2) in enumerate(zip(m1, m2)):
        a.text(i, max(v1, v2) + 8, f"{v2 / v1:.2f}×", ha="center", fontweight="bold", fontsize=10)
    a.axhline(df.gold.iloc[-1], c="gold", ls="--", lw=1.3)
    a.text(len(labs) - 0.5, df.gold.iloc[-1] + 5, f"现价 {df.gold.iloc[-1]:.0f}", color="#8a6d00", fontsize=8)
    a.set_xticks(x); a.set_xticklabels([f"实际利率 {l}\nn={n[0]}/{n[1]}" for l, n in zip(labs, ns)])
    a.set_ylabel("GLD 均价（美元）"); a.set_title("② 中枢抬升：同一实际利率区间，2022 后金价均值")
    a.legend(fontsize=8)

    # ---------- (3) 隐含 vs TIPS 时序 ----------
    a = ax[1, 0]
    seg = df.loc["2006":]
    a.plot(seg.index, seg.impA, c=C_NEG, lw=0.9, label="隐含 r｜2006–21 静态模型外推（用户图）")
    a.plot(seg.index, seg.impP, c=C_POST, lw=0.9, label="隐含 r｜2022–26 校准")
    a.plot(seg.index, seg.real, c="k", lw=1.4, label="10Y TIPS 实际交易")
    a.axvspan(pd.Timestamp("2022-01-01"), seg.index[-1], color=C_POST, alpha=0.05)
    a.axvline(pd.Timestamp("2022-01-01"), c=C_POST, ls=":", lw=1)
    a.text(pd.Timestamp("2022-03-01"), a.get_ylim()[1] * 0.9, "央行购金潮\n制度断裂", color=C_POST, fontsize=8)
    a.scatter([seg.index[-1]] * 2, [seg.impA.iloc[-1], seg.impP.iloc[-1]], s=50, zorder=5, c=[C_NEG, C_POST], edgecolor="k")
    a.annotate(f"静态外推 → {seg.impA.iloc[-1]:.2f}\n（央行溢价把模型打出解释范围）",
               (seg.index[-1], max(seg.impA.iloc[-1], -7.8)), xytext=(0.28, 0.13), textcoords="axes fraction",
               fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.7))
    a.annotate(f"2022 校准 → {seg.impP.iloc[-1]:.2f}\nTIPS {seg.real.iloc[-1]:.2f} → gap +{seg.gapP.iloc[-1]:.2f}",
               (seg.index[-1], seg.impP.iloc[-1]), xytext=(0.06, 0.93), textcoords="axes fraction",
               fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.7))
    a.set_ylim(-8, 8); a.set_ylabel("实际利率 (%)")
    a.set_title("③ 隐含实际利率 vs TIPS：两种校准给出相反符号")
    a.legend(fontsize=7.5, loc="lower right", bbox_to_anchor=(1.0, 0.02))

    # ---------- (4) 信号回测 ----------
    a = ax[1, 1]
    b2 = df.loc["2022-01-01":].copy()
    h = 250
    b2["f"] = b2.gold.shift(-h) / b2.gold - 1
    b2["rt"] = b2.real.shift(-h) - b2.real
    q = pd.qcut(b2.gapA, 5, labels=["Q1\n最贵", "Q2", "Q3", "Q4", "Q5\n最便宜"])
    g = b2.groupby(q, observed=True)[["f", "rt"]].mean() * 100
    x = np.arange(len(g)); w = 0.38
    a.bar(x - w / 2, g.f, w, color=C_ACC, label="黄金前向 250 日收益 (%)")
    a.bar(x + w / 2, g.rt / 10, w, color=C_NEG, label="TIPS 同期变化 (pp，÷10 缩放)")
    for i, (fv, rv) in enumerate(zip(g.f, g.rt)):
        a.text(i - w / 2, fv + (1.5 if fv >= 0 else -5), f"{fv:+.0f}%", ha="center", fontsize=8, va="top" if fv < 0 else "baseline")
        a.text(i + w / 2, rv / 10 + (1.5 if rv >= 0 else -5), f"{rv:+.0f}", ha="center", fontsize=8, color="#444", va="top" if rv < 0 else "baseline")
    a.axhline(0, c="k", lw=0.8)
    lo = min(g.f.min(), (g.rt / 10).min()); hi = max(g.f.max(), (g.rt / 10).max())
    a.set_ylim(lo - 8, hi + 6)
    a.set_xticks(x); a.set_xticklabels([str(t).replace("−", "-") for t in g.index])
    a.set_ylabel("%"); a.set_title("④ 静态 gap 信号（2022+）：「最便宜」后黄金涨最少、TIPS 涨最多")
    a.text(0.02, 0.04, "IC(gapA, 黄金250日) = -0.56 → 差值经债腿收敛，非金腿\n趋势项而非均值回归信号",
           transform=a.transAxes, fontsize=8, bbox=dict(boxstyle="round", fc="#fff3cd", ec="#d4a017"))
    a.legend(fontsize=8, loc="upper left")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = OUT / "黄金隐含实际利率_回测四联图_2026-11-25.png"
    fig.savefig(out, bbox_inches="tight")
    print(f"[saved] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
