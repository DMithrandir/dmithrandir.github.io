#!/usr/bin/env python3
"""黄金隐含实际利率模型回测 v2（研究用途，只读数据，不进任何闸门）。

v2 相对 v1 的方法论变更（审稿后）：
  信号由「利率反解」gap = (ln P - α)/β - TIPS 改为「对数价格残差」
      eps_t = ln(GLD_t) - (α + β·TIPS_t)   （单位 %）
  原因：v1 的 gap 在 β 过零时除零爆炸（滚动 365d 的 β 过零 17 次、|β|<0.03 共 842 天，
  gap 极值 ±1000+）；且 β 由负转正后 gap>0 的经济含义从「便宜」反转为「偏贵」，是隐蔽 bug。
  eps 恒有「正 = 价格高于模型 = 偏贵；负 = 低于模型 = 便宜」，与 β 符号无关。

三个模型（按编号 A/B/C）：
  A 静态外推：2006–2021 拟合，之后不更新。天然样本外。
  B 滚动 365d：每天只用 t−1 前数据重拟合。每日样本外。
  C 制度哑变量：全样本拟合，2022 后允许截距与斜率变化（诊断用，非样本外）。

回测：按 eps 分位（Q1 最便宜 … Q5 最贵）看前向 20/60/120/250 日黄金收益与同期 TIPS 变化。
  附：20 年无条件前向收益基准（剔除长牛 beta），以及非重叠期数（自由度）。
  附：滚动模型 z = eps / 滚动σ 的事件研究。

数据：state/_cache/gold_model/{GLD.json, DFII10.csv, DGS10.csv, T10YIE.csv}
      GLD 与 FRED 利率按日历 outer join 后 dropna；利率缺失 ffill ≤10 个交易日（覆盖 FRED 发布滞后；金价不填充）。
"""
from __future__ import annotations
import json, csv, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "state" / "_cache" / "gold_model"
OUT = ROOT / "reports" / "策略分析" / "2026-11"
HORIZONS = (20, 60, 120, 250)


def load() -> pd.DataFrame:
    g = json.load(open(D / "GLD.json"))["chart"]["result"][0]
    idx = pd.to_datetime(g["timestamp"], unit="s", utc=True).tz_convert("America/New_York").normalize().tz_localize(None)
    vals = g["indicators"]["adjclose"][0]["adjclose"]          # Yahoo: [{"adjclose":[...]}]
    gold = pd.to_numeric(pd.Series(vals, index=idx, name="gold"), errors="coerce").dropna().astype(float)
    gold = gold[~gold.index.duplicated(keep="last")]

    def fred(name, col):
        rows = list(csv.reader(open(D / name)))[1:]
        s = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in rows if r[1] not in (".", "", "NA")}, name=col)
        return s[~s.index.duplicated(keep="last")]
    real, nom, be = fred("DFII10.csv", "real"), fred("DGS10.csv", "nom"), fred("T10YIE.csv", "be")

    df = pd.concat([gold, real, nom, be], axis=1, join="outer", sort=True).sort_index()
    df[["real", "nom", "be"]] = df[["real", "nom", "be"]].ffill(limit=10)   # FRED 滞后 ≤10 交易日
    df["lg"] = np.log(df["gold"])
    n_raw = len(df)
    df = df.dropna(subset=["gold", "real"])
    print(f"[load] inner-join {n_raw} 行 → dropna 后 {len(df)} 行（{df.index[0].date()} → {df.index[-1].date()}）")
    return df


def ols(x: pd.DataFrame, col: str, y: pd.Series) -> np.ndarray:
    X = np.column_stack([np.ones(len(x)), x[col].values])
    b, *_ = np.linalg.lstsq(X, y.values, rcond=None)
    return b


def r2(seg: pd.DataFrame, b: np.ndarray, col: str = "real") -> float:
    return 1 - np.var(seg.lg - (b[0] + b[1] * seg[col])) / np.var(seg.lg)


def eps(df: pd.DataFrame, b: np.ndarray) -> pd.Series:
    """对数价格残差（%）：正=价格高于模型=偏贵；负=便宜。"""
    return (df["lg"] - (b[0] + b[1] * df["real"])) * 100


def zroll(s: pd.Series, win: int = 252) -> pd.Series:
    r = s.rolling(win, min_periods=win // 2)
    return (s - r.mean()) / r.std()


def fwd(df: pd.DataFrame, col: str, scale: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame({f"f{h}": (df[col].shift(-h) / df[col] - 1) * scale for h in HORIZONS}, index=df.index)


def quintile_table(bt: pd.DataFrame, sig: str, label: str = "") -> pd.DataFrame:
    q = pd.qcut(bt[sig], 5, labels=["Q1 最便宜", "Q2", "Q3", "Q4", "Q5 最贵"])
    cols = [f"f{h}" for h in HORIZONS] + [f"r{h}" for h in HORIZONS]
    t = bt.groupby(q, observed=True)[cols].mean()
    for c in cols:
        t[c] = t[c] * (100 if c.startswith("f") else 1)
    t["n"] = bt.groupby(q, observed=True).size()
    t["win120"] = bt.groupby(q, observed=True)["f120"].apply(lambda s: (s > 0).mean() * 100)
    if label:
        print(f"\n===== {label} =====")
        print(t[[f"f{h}" for h in HORIZONS] + ["win120", "n"]].round(2).to_string())
        ics = {h: round(bt[sig].corr(bt[f"f{h}"]), 3) for h in HORIZONS}
        print("IC(信号, 黄金前向):", ics)
    return t


def nonoverlap_count(n_days: int, h: int) -> int:
    return n_days // h


def main():
    df = load()
    last = df.iloc[-1]
    print(f"最新 {df.index[-1].date()}  GLD={last.gold:.2f}  TIPS={last.real:.2f}  10Y名义={last['nom']:.2f}  BE={last.be:.2f}")

    # ---------- 窗口拟合（供 02 的窗口表）----------
    print("\n========== 窗口拟合（lg = a + b·TIPS）==========")
    wins = {"2006–2021": ("2006-01-01", "2021-12-31"), "2022–2025": ("2022-01-01", "2025-12-31"), "2022–2026": ("2022-01-01", None)}
    fitrows = []
    for lab, (a, z) in wins.items():
        seg = df.loc[a:z] if z else df.loc[a:]
        b = ols(seg, "real", seg["lg"])
        e_now = (df.lg.iloc[-1] - (b[0] + b[1] * last.real)) * 100
        imp_now = (df.lg.iloc[-1] - b[0]) / b[1]
        fitrows.append(dict(window=lab, n=len(seg), a=round(b[0], 3), b=round(b[1], 3), R2=round(r2(seg, b), 4),
                            implied_now=round(imp_now, 2), eps_now_pct=round(e_now, 1)))
        print(f"  {lab:10s} n={len(seg):5d}  a={b[0]:.3f}  b={b[1]:+.3f}  R2={r2(seg,b):.4f}  | 当前隐含 r={imp_now:+.2f}  eps={e_now:+.1f}%")
    pd.DataFrame(fitrows).to_csv(OUT / "gold_model_window_fits.csv", index=False, encoding="utf-8")

    # ---------- 模型 A：静态外推 ----------
    tr = df.loc["2006-01-01":"2021-12-31"]
    bA = ols(tr, "real", tr["lg"])
    df["epsA"] = eps(df, bA)
    df["zA"] = zroll(df["epsA"])
    print(f"\n[A 静态 2006–21] a={bA[0]:.3f} b={bA[1]:+.3f} R2={r2(tr,bA):.3f} | 当前 eps={df.epsA.iloc[-1]:+.1f}%  z={df.zA.iloc[-1]:+.2f}")

    # ---------- 模型 C：制度哑变量（截距+斜率变化）----------
    df["post"] = (df.index >= "2022-01-01").astype(float)
    df["post_real"] = df["post"] * df["real"]
    trD = df.loc["2006-01-01":]
    X = np.column_stack([np.ones(len(trD)), trD.real, trD.post, trD.post_real])
    bC, *_ = np.linalg.lstsq(X, trD.lg.values, rcond=None)
    df["epsC"] = (df.lg - (bC[0] + bC[1] * df.real + bC[2] * df.post + bC[3] * df.post_real)) * 100
    print(f"[C 制度哑变量] pre: {bC[0]:.3f}{bC[1]:+.3f}r | post: 截距{bC[2]:+.3f} 斜率{bC[3]:+.3f} | 当前 eps={df.epsC.iloc[-1]:+.1f}%")

    # ---------- 模型 B：滚动 365d（只用 t−1 前数据）----------
    epsB = pd.Series(np.nan, index=df.index)
    betaB = pd.Series(np.nan, index=df.index)
    v = df[["lg", "real"]].values
    win = 365
    for i in range(win, len(v)):
        x = v[i - win:i]
        bb, *_ = np.linalg.lstsq(np.column_stack([np.ones(win), x[:, 1]]), x[:, 0], rcond=None)
        epsB.iloc[i] = (v[i, 0] - (bb[0] + bb[1] * v[i, 1])) * 100
        betaB.iloc[i] = bb[1]
    df["epsB"] = epsB
    df["zB"] = zroll(df["epsB"])
    print(f"[B 滚动365d] 当前 eps={df.epsB.iloc[-1]:+.1f}%  z={df.zB.iloc[-1]:+.2f}  (β 范围 [{betaB.min():.3f},{betaB.max():.3f}]，过零 {(np.sign(betaB).diff().fillna(0)!=0).sum()} 次)")

    # ---------- 前向收益 ----------
    f = fwd(df, "gold")                                        # 小数，表内 ×100
    r = pd.DataFrame({f"r{h}": df["real"].shift(-h) - df["real"] for h in HORIZONS})  # pp
    bt = pd.concat([df[["epsA", "zA", "epsB", "zB", "epsC"]], f, r], axis=1)

    # 无条件基准（剔除长牛 beta）
    base = {h: bt.loc["2007":][f"f{h}"].mean() * 100 for h in HORIZONS}   # f 列是小数
    basewin = {h: (bt.loc["2007":][f"f{h}"] > 0).mean() * 100 for h in HORIZONS}
    print("\n20 年无条件基准（2007+）: " + "  ".join(f"{h}日 {base[h]:+.1f}%/胜率{basewin[h]:.0f}%" for h in HORIZONS))
    print("  基准 n(非重叠): " + "  ".join(f"{h}日≈{nonoverlap_count(len(bt.loc[chr(39)+chr(50)+chr(48)+chr(48)+chr(55)+chr(39):]),h)}" for h in HORIZONS))

    # ---------- 回测 1：静态 A，2022+ ----------
    a22 = bt.loc["2022-01-01":]
    quintile_table(a22, "epsA", "回测 1 · 静态模型 A 的 eps 分位 → 前向收益（2022+，样本外）")
    print("  TIPS 同期变化(pp):", quintile_table(a22, "epsA")[[f"r{h}" for h in HORIZONS]].round(1).to_string())
    print(f"  自由度：2022-01→2026-11 ≈ {len(a22)} 交易日；非重叠期数 20日≈{nonoverlap_count(len(a22),20)} 60日≈{nonoverlap_count(len(a22),60)} 120日≈{nonoverlap_count(len(a22),120)} 250日≈{nonoverlap_count(len(a22),250)} → 250 日仅作方向证伪")

    # ---------- 回测 2：滚动 B，2007+ ----------
    b07 = bt.loc["2007-01-01":]
    quintile_table(b07, "epsB", "回测 2 · 滚动模型 B 的 eps 分位 → 前向收益（2007+，样本外）")

    # ---------- 回测 3：极端信号事件研究（zB ≤ −1.5 = 显著便宜）----------
    print("\n===== 回测 3 · 滚动 z 事件研究（去重间隔 ≥60 日）=====")
    for thr in (-1.0, -1.5, -2.0):
        ev = b07[b07["zB"] <= thr]
        keep, lastt = [], None
        for t in ev.index:
            if lastt is None or (t - lastt).days >= 60:
                keep.append(t); lastt = t
        e = b07.loc[keep]
        def stat(h):
            ee = e.dropna(subset=[f"f{h}"])
            return ee[f"f{h}"].mean()*100, (ee[f"f{h}"]>0).mean()*100, len(ee)
        m60,w60,n60 = stat(60); m120,w120,n120 = stat(120); m250,w250,n250 = stat(250)
        print(f"  z≤{thr:+.1f}: {len(keep):2d} 次 | 60日 {m60:+.1f}%/胜{w60:.0f}%(n={n60}) | "
              f"120日 {m120:+.1f}%/胜{w120:.0f}%(n={n120},基准{basewin[120]:.0f}%) | 250日 {m250:+.1f}%/胜{w250:.0f}%(n={n250},基准{basewin[250]:.0f}%) | TIPS120 {e.r120.mean():+.2f}pp")
        if thr == -1.5:
            print("           日期:", [str(t.date()) for t in keep][-8:], "… 共", len(keep))

    # ---------- 年度均值（制度溢价时变）----------
    yr = df.loc["2006":].groupby(df.loc["2006":].index.year).agg(epsA=("epsA", "mean"), epsB=("epsB", "mean"), real=("real", "mean"), gold=("gold", "last"))
    print("\n===== 年度 eps 均值（%）=====")
    print(yr.round(1).to_string())

    # ---------- 落盘 ----------
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["epsA", "zA", "epsB", "zB", "epsC"] + list(f.columns) + list(r.columns)
    bt.loc["2006":][cols].round(4).to_csv(OUT / "gold_real_yield_model_backtest_2026-11-25.csv", encoding="utf-8")
    print(f"\n[csv] {OUT}/gold_real_yield_model_backtest_2026-11-25.csv  rows={len(bt.loc['2006':])}")
    print(f"[csv] {OUT}/gold_model_window_fits.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
