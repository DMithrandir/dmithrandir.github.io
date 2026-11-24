#!/usr/bin/env python3
"""黄金隐含实际利率模型回测 — 可视化 v2（审稿后改版，研究用途只读）。

四联图改版：
  ① 制度断裂散点：2022–2026 红点按年份浅→深渐变，显示沿时间轴右上漂移
  ② 区间中枢柱状：柱顶叠加 IQR(25–75%) 误差棒；现价仅在 [2,3) 柱上打点，不再贯通全图
  ③ 改画「2006–21 静态模型的对数价格残差 epsA(%)」时序，避免隐含利率 -3.07 拉扁纵轴
  ④ 静态 eps 分位回测：上下双子图共享 Q1–Q5 横轴（上：黄金 250 日收益%；下：TIPS 250 日变化 bp），取消 ÷10 同轴缩放
依赖 gold_real_yield_backtest.py 的 load()/ols()/r2()。
"""
from __future__ import annotations
import importlib.util, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, cm, colors

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("bt", ROOT / "scripts/strategy_lab/gold_real_yield_backtest.py")
bt = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bt)

_cjk = next((n for n in ("Hiragino Sans GB", "Heiti SC", "Arial Unicode MS", "PingFang SC")
             if any(f.name == n for f in font_manager.fontManager.ttflist)), "DejaVu Sans")
plt.rcParams["font.family"] = [_cjk, "DejaVu Sans"]   # 中文用 CJK，减号/符号回退 DejaVu
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"figure.dpi": 130, "savefig.dpi": 150, "axes.grid": True, "grid.alpha": 0.25,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 9,
                     "axes.titlesize": 11, "axes.titleweight": "bold"})
C_PRE, C_POST, C_ACC, C_NEG = "#1f77b4", "#d62728", "#2ca02c", "#7f7f7f"
OUT = ROOT / "reports/策略分析" / "2026-11"


def quintile(sig: pd.Series, fwd: pd.Series, tips: pd.Series):
    d = pd.concat([sig.rename("s"), fwd.rename("f"), tips.rename("r")], axis=1).dropna()
    q = pd.qcut(d.s, 5, labels=False)
    g = d.groupby(q)
    return (g.f.mean() * 100).values, (g.r.mean() * 100).values, g.size().values   # f%, r bp, n


def main():
    df = bt.load()
    pre = df.loc["2006-01-01":"2021-12-31"]; post = df.loc["2022-01-01":]
    bA = bt.ols(pre, "real", pre["lg"]); bP = bt.ols(post, "real", post["lg"])
    r2A, r2P = bt.r2(pre, bA), bt.r2(post, bP)
    df["epsA"] = bt.eps(df, bA)
    f250 = df.gold.shift(-250) / df.gold - 1
    r250 = df.real.shift(-250) - df.real

    fig = plt.figure(figsize=(15, 11))
    gs = fig.add_gridspec(2, 2, hspace=0.34, wspace=0.24, left=0.06, right=0.97, top=0.93, bottom=0.06)
    fig.suptitle("黄金隐含实际利率模型：实际数据回测 v2（残差口径，数据截至 2026-11-24）", fontsize=14, fontweight="bold")

    # ---------- ① 制度断裂散点（年份渐变）----------
    a = fig.add_subplot(gs[0, 0])
    a.scatter(pre.real, pre.gold, s=4, c=C_PRE, alpha=0.22, lw=0, label=f"2006–2021 (n={len(pre)})")
    norm = colors.Normalize(vmin=2021.5, vmax=2026.5)
    sc = a.scatter(post.real, post.gold, s=7, c=post.index.year, cmap="Reds", norm=norm, alpha=0.85, lw=0)
    cb = fig.colorbar(sc, ax=a, pad=0.02, fraction=0.04); cb.set_label("年份（浅→深）", fontsize=8); cb.ax.tick_params(labelsize=7)
    xr = np.linspace(df.real.min(), df.real.max(), 50)
    a.plot(xr, np.exp(bA[0] + bA[1] * xr), c=C_PRE, lw=2.2, label=f"2006–21 拟合 b={bA[1]:+.3f}, R^2={r2A:.2f}")
    a.plot(xr, np.exp(bP[0] + bP[1] * xr), c="#8b0000", lw=2.2, label=f"2022–26 拟合 b={bP[1]:+.3f}, R^2={r2P:.2f}")
    a.scatter([df.real.iloc[-1]], [df.gold.iloc[-1]], s=110, marker="*", c="gold", edgecolor="k", zorder=6)
    a.annotate(f"当前 TIPS {df.real.iloc[-1]:.2f}% / GLD {df.gold.iloc[-1]:.0f}", (df.real.iloc[-1], df.gold.iloc[-1]),
               xytext=(0.30, 0.06), textcoords="axes fraction", fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.7))
    a.set_yscale("log"); a.set_xlabel("10Y TIPS 实际利率 (%)"); a.set_ylabel("GLD 价格（对数轴，美元）")
    a.set_title("① 制度断裂：红点按年份渐变，沿时间轴右上漂移")
    a.legend(fontsize=7, loc="upper left")

    # ---------- ② 中枢抬升 + IQR ----------
    a = fig.add_subplot(gs[0, 1])
    bins = [(-1, 0), (0, 1), (1, 2), (2, 3)]; labs, m1, m2, e1, e2, ns = [], [], [], [], [], []
    for lo, hi in bins:
        p1 = pre[(pre.real >= lo) & (pre.real < hi)].gold; p2 = post[(post.real >= lo) & (post.real < hi)].gold
        if len(p1) > 20 and len(p2) > 20:
            labs.append(f"[{lo}, {hi})"); m1.append(p1.mean()); m2.append(p2.mean())
            e1.append([p1.mean() - p1.quantile(.25), p1.quantile(.75) - p1.mean()])
            e2.append([p2.mean() - p2.quantile(.25), p2.quantile(.75) - p2.mean()]); ns.append((len(p1), len(p2)))
    x = np.arange(len(labs)); w = 0.38
    a.bar(x - w/2, m1, w, color=C_PRE, label="2006–2021 均价")
    a.bar(x + w/2, m2, w, color=C_POST, label="2022–2026 均价")
    a.errorbar(x - w/2, m1, yerr=np.array(e1).T, fmt="none", ecolor="#0d3d5c", capsize=3, lw=1)
    a.errorbar(x + w/2, m2, yerr=np.array(e2).T, fmt="none", ecolor="#5c0d0d", capsize=3, lw=1)
    for i, (v1, v2) in enumerate(zip(m1, m2)):
        a.text(i, max(v1 + np.array(e1)[i, 1], v2 + np.array(e2)[i, 1]) + 12, f"{v2/v1:.2f}×", ha="center", fontweight="bold", fontsize=10)
    # 现价仅在 [2,3) 柱上打点
    j = labs.index("[2, 3)")
    a.scatter([j + w/2], [df.gold.iloc[-1]], s=70, marker="D", c="gold", edgecolor="k", zorder=6)
    a.annotate(f"现价 {df.gold.iloc[-1]:.0f}", (j + w/2, df.gold.iloc[-1]), xytext=(j + w/2 - 0.55, df.gold.iloc[-1] + 40),
               fontsize=8, color="#8a6d00", arrowprops=dict(arrowstyle="->", lw=0.7, color="#8a6d00"))
    a.set_xticks(x); a.set_xticklabels([f"实际利率 {l}\nn={n[0]}/{n[1]}" for l, n in zip(labs, ns)])
    a.set_ylabel("GLD 均价（美元）"); a.set_title("② 中枢抬升（柱顶 IQR 25–75%）：1.09→4.44×")
    a.legend(fontsize=8, loc="upper left")

    # ---------- ③ 静态模型对数价格残差时序 ----------
    a = fig.add_subplot(gs[1, 0])
    seg = df.loc["2006":]
    a.plot(seg.index, seg.epsA, c=C_NEG, lw=1.0, label="epsA = ln(GLD) − (α+β·TIPS)，2006–21 静态模型")
    a.axhline(0, c="k", lw=0.9)
    a.axvspan(pd.Timestamp("2022-01-01"), seg.index[-1], color=C_POST, alpha=0.06)
    a.axvline(pd.Timestamp("2022-01-01"), c=C_POST, ls=":", lw=1)
    a.text(pd.Timestamp("2022-02-01"), 12, "央行购金潮\n制度断裂", color=C_POST, fontsize=8)
    a.scatter([seg.index[-1]], [seg.epsA.iloc[-1]], s=55, c=C_POST, edgecolor="k", zorder=6)
    a.annotate(f"当前 epsA = +{seg.epsA.iloc[-1]:.0f}%\n（价格高于旧模型 {np.exp(seg.epsA.iloc[-1]/100):.1f} 倍＝央行溢价）",
               (seg.index[-1], seg.epsA.iloc[-1]), xytext=(0.30, 0.55), textcoords="axes fraction", fontsize=8,
               arrowprops=dict(arrowstyle="->", lw=0.7))
    a.set_ylabel("对数价格残差 (%)"); a.set_title("③ 静态模型残差：央行溢价从 0 累积到 +162%")
    a.legend(fontsize=7.5, loc="upper left")

    # ---------- ④ 双子图：黄金收益 / TIPS 变化 ----------
    gs4 = gs[1, 1].subgridspec(2, 1, hspace=0.10, height_ratios=[1, 1])
    aT = fig.add_subplot(gs4[0]); aB = fig.add_subplot(gs4[1], sharex=aT)
    a22 = df.loc["2022-01-01":]
    fm, rb, nn = quintile(a22.epsA, f250.loc[a22.index], r250.loc[a22.index])
    xq = np.arange(5); qlab = ["Q1\n最便宜", "Q2", "Q3", "Q4", "Q5\n最贵"]
    aT.bar(xq, fm, 0.6, color=[C_ACC if v >= 0 else C_POST for v in fm])
    for i, v in enumerate(fm):
        aT.text(i, v + (1.5 if v >= 0 else -3), f"{v:+.1f}%", ha="center", fontsize=8, va="bottom" if v >= 0 else "top")
    aT.axhline(0, c="k", lw=0.8); aT.set_ylabel("黄金 250 日收益 (%)")
    aT.set_title("④ 静态 eps 分位（2022+）：倒 U 型，两端跑输中间", fontsize=10)
    aT.text(0.02, 0.90, f"IC(eps,250日)=+0.56（动量代理，非均值回归）\n250 日仅 ≈4 个非重叠期 → 仅作方向证伪",
            transform=aT.transAxes, fontsize=7.5, va="top", bbox=dict(boxstyle="round", fc="#fff3cd", ec="#d4a017"))
    aB.bar(xq, rb, 0.6, color=C_NEG)
    for i, v in enumerate(rb):
        aB.text(i, v + (4 if v >= 0 else -8), f"{v:+.0f}", ha="center", fontsize=8, va="bottom" if v >= 0 else "top")
    aB.axhline(0, c="k", lw=0.8); aB.set_ylabel("TIPS 250 日变化 (bp)")
    aB.set_xticks(xq); aB.set_xticklabels(qlab); aB.set_xlabel("eps 分位（残差越低＝越便宜）")
    plt.setp(aT.get_xticklabels(), visible=False)

    out = OUT / "黄金隐含实际利率_回测四联图_2026-11-25.png"
    fig.savefig(out, bbox_inches="tight")
    print(f"[saved] {out}")
    print("\n=== ④ 精确数值（供正文转录，dropna 后）===")
    print("黄金 250 日收益%:", [round(v, 1) for v in fm])
    print("TIPS 250 日变化 bp:", [round(v, 0) for v in rb])
    print("各分位 n:", list(nn))
    print(f"窗口 R²: 2006–21={r2A:.4f}  2022–26={r2P:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
