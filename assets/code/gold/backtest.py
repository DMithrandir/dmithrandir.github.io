#!/usr/bin/env python3
"""黄金隐含实际利率模型回测（研究用途，只读数据，不进任何闸门）。

回答三个问题：
  Q1 复现：用户模型「隐含 10Y 实际利率 4.12 vs TIPS 2.79」能否用公开数据复现？
  Q2 R1：残差 z-score 对 σ 估计窗口有多敏感？（2006-2021 静态 vs 滚动 vs 分制度）
  Q3 R2：2022 后制度溢价是常数哑变量，还是随央行购金流量时变？

设计（防未来函数）：
  - 静态模型 A：2006-01..2021-12 拟合，之后纯外推（= 用户图中的「静态回归外推」）
  - 滚动模型 B：365d 滚动窗口拟合，只用 t-1 及之前数据 → 每日样本外
  - 制度模型 C：A + 2022 后哑变量（常数溢价）
  - 时变模型 D：log(gold) ~ a + b*real + c*post2022 + d*post2022*real（斜率也变）
  信号 = 隐含实际利率 − 实际 TIPS；正 = 黄金便宜（定价了更高的实际利率）
回测：按信号分位分组，看前向 20/60/120/250 日收益（金、以及相对 TIPS 变化）。

数据：state/_cache/gold_model/{GLD.json, DFII10.csv, DGS10.csv, T10YIE.csv}
"""
from __future__ import annotations
import json, csv, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "state" / "_cache" / "gold_model"
OUT = ROOT / "reports" / "策略分析" / "2026-11"


def load() -> pd.DataFrame:
    # GLD
    g = json.load(open(D / "GLD.json"))["chart"]["result"][0]
    idx = pd.to_datetime(g["timestamp"], unit="s", utc=True).tz_convert("America/New_York").normalize().tz_localize(None)
    # Yahoo: indicators.adjclose = [{"adjclose": [...]}]（dict 而非 list）
    vals = g["indicators"]["adjclose"][0]["adjclose"]
    raw = pd.to_numeric(pd.Series(vals, index=idx, name="gold"), errors="coerce")
    gold = raw.dropna().astype(float)
    gold = gold[~gold.index.duplicated(keep="last")]
    # FRED series
    def fred(name, col):
        rows = list(csv.reader(open(D / name)))[1:]
        s = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in rows if r[1] not in (".", "", "NA")}, name=col)
        return s[~s.index.duplicated(keep="last")]
    real = fred("DFII10.csv", "real")      # 10Y TIPS
    nom = fred("DGS10.csv", "nom")
    be = fred("T10YIE.csv", "be")
    df = pd.concat([gold, real, nom, be], axis=1, sort=True).sort_index()
    for c in ("real", "nom", "be"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # 利率缺失：前向填充最多 5 个交易日（假期），金价不填充
    df[["real", "nom", "be"]] = df[["real", "nom", "be"]].ffill(limit=5)
    df["lg"] = np.log(df["gold"])
    return df.dropna(subset=["gold", "real"])


def ols(x: pd.DataFrame, cols: list[str], y: pd.Series):
    X = np.column_stack([np.ones(len(x))] + [x[c].values for c in cols])
    b, *_ = np.linalg.lstsq(X, y.values, rcond=None)
    return b


def implied(df: pd.DataFrame, b: np.ndarray, cols: list[str]) -> pd.Series:
    # 反解：lg = b0 + b1*real (+...) → 以单变量模型为准反解 real
    assert len(cols) == 1
    return (df["lg"] - b[0]) / b[1]


def z(s: pd.Series, win: int | None) -> pd.Series:
    if win is None:
        return (s - s.expanding(min_periods=252).mean()) / s.expanding(min_periods=252).std()
    r = s.rolling(win, min_periods=win // 2)
    return (s - r.mean()) / r.std()


def fwd(df: pd.DataFrame, col: str, horizons=(20, 60, 120, 250)) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for h in horizons:
        out[f"f{h}"] = df[col].shift(-h) / df[col] - 1
    return out


def main():
    df = load()
    print(f"样本 {df.index[0].date()} → {df.index[-1].date()}  n={len(df)}")
    last = df.iloc[-1]
    print(f"最新 {df.index[-1].date()}  GLD={last.gold:.2f}  TIPS={last.real:.2f}  10Y名义={last['nom']:.2f}  BE={last.be:.2f}")

    results = {}

    # ---------- 模型 A：2006–2021 静态 ----------
    tr = df.loc["2006-01-01":"2021-12-31"]
    cols = ["real"]
    bA = ols(tr, cols, tr["lg"])
    df["impA"] = implied(df, bA, cols)      # 模型隐含实际利率
    df["gapA"] = df["impA"] - df["real"]    # >0 黄金便宜
    r2 = 1 - np.var(tr["lg"] - (bA[0] + bA[1] * tr["real"])) / np.var(tr["lg"])
    print(f"\n[A 静态 2006-2021] lg = {bA[0]:.3f} + {bA[1]:.3f}*real   R²={r2:.3f}  n={len(tr)}")
    print(f"  最新：隐含={df.impA.iloc[-1]:.2f}  TIPS={df.real.iloc[-1]:.2f}  gap={df.gapA.iloc[-1]:+.2f}")

    # R1：不同 σ 口径下的 z
    sig_tr = (tr["lg"] - (bA[0] + bA[1] * tr["real"])).std() / abs(bA[1])   # 训练期隐含利率残差σ
    zA_static = df.gapA.iloc[-1] / sig_tr
    df["zA_roll"] = z(df.gapA, 252)
    df["zA_3y"] = z(df.gapA, 756)
    print(f"  R1 敏感性：σ(2006-21训练)={sig_tr:.2f} → z={zA_static:+.2f} | σ(滚动252) → z={df.zA_roll.iloc[-1]:+.2f} | σ(滚动756) → z={df.zA_3y.iloc[-1]:+.2f}")
    tr_gap = (tr["lg"] - bA[0]) / bA[1] - tr["real"]
    print(f"  训练期 gap 均值={tr_gap.mean():+.2f}  std={tr_gap.std():.2f}")
    # 2022 后 gap 分布（看外推是否系统性偏移 = 制度溢价）
    post = df.loc["2022-01-01":]
    print(f"  外推段 2022+ gap 均值={post.gapA.mean():+.2f} std={post.gapA.std():.2f}  → 均值显著≠0 = 制度断裂")
    results["A"] = dict(b0=bA[0], b1=bA[1], r2=r2, imp=df.impA.iloc[-1], gap=df.gapA.iloc[-1],
                        z_static=zA_static, z_roll=df.zA_roll.iloc[-1], sigma_tr=sig_tr)

    # ---------- 模型 D：制度哑变量（斜率+截距） ----------
    df["post"] = (df.index >= "2022-01-01").astype(float)
    df["post_real"] = df["post"] * df["real"]
    trD = df.loc["2006-01-01":"2026-11-30"]
    bD = ols(trD, ["real", "post", "post_real"], trD["lg"])
    # 隐含实际利率（2022 后用 post 方程反解）
    lg_hat0 = bD[0] + bD[1] * df["real"] + bD[2] + bD[3] * df["real"]
    df["impD"] = (df["lg"] - bD[0] - bD[2]) / (bD[1] + bD[3])
    df["gapD"] = df["impD"] - df["real"]
    print(f"\n[D 制度哑变量 2006-2026] pre: {bD[0]:.3f}+{bD[1]:.3f}*r | post: 截距+{bD[2]:.3f} 斜率+{bD[3]:.3f}")
    print(f"  最新：隐含={df.impD.iloc[-1]:.2f}  gap={df.gapD.iloc[-1]:+.2f}  z(滚动252)={z(df.gapD,252).iloc[-1]:+.2f}")

    # ---------- 模型 B：滚动 365d，样本外 ----------
    impB = pd.Series(np.nan, index=df.index)
    win = 365
    v = df[["lg", "real"]].values
    for i in range(win, len(v)):
        x = v[i - win:i]
        X = np.column_stack([np.ones(win), x[:, 1]])
        bb, *_ = np.linalg.lstsq(X, x[:, 0], rcond=None)
        impB.iloc[i] = (v[i, 0] - bb[0]) / bb[1]
    df["impB"] = impB
    df["gapB"] = df["impB"] - df["real"]
    df["zB"] = z(df.gapB, 252)
    print(f"\n[B 滚动365d 样本外] 最新：隐含={df.impB.iloc[-1]:.2f}  gap={df.gapB.iloc[-1]:+.2f}  z(252)={df.zB.iloc[-1]:+.2f}")

    # ---------- 回测：gap 信号 → 前向收益 ----------
    f = fwd(df, "gold", (20, 60, 120, 250))
    # 「差值收敛」收益：gold 涨 vs TIPS 上行两种收敛路径
    tips_fwd = pd.DataFrame({f"r{h}": df["real"].shift(-h) - df["real"] for h in (20, 60, 120, 250)})
    bt = pd.concat([df[["gapB", "zB", "gapA", "gapD"]], f, tips_fwd], axis=1)

    print("\n========== 回测 1：滚动模型 gapB 分位（样本外，2007+） → 前向收益 ==========")
    b1 = bt.loc["2007-01-01":]
    q = pd.qcut(b1["gapB"], 5, labels=["Q1最贵", "Q2", "Q3", "Q4", "Q5最便宜"])
    tab = b1.groupby(q, observed=True)[["f20", "f60", "f120", "f250", "r20", "r60", "r250"]].mean() * 100
    tab["n"] = b1.groupby(q, observed=True).size()
    print(tab.round(2).to_string())
    # IC
    ics = {h: b1["gapB"].corr(b1[f"f{h}"]) for h in (20, 60, 120, 250)}
    print("IC(gapB, fwd):", {k: round(v, 3) for k, v in ics.items()})

    print("\n========== 回测 2：静态模型 A 外推 gapA（=用户图的做法）分位 → 前向收益，2022+ ==========")
    b2 = bt.loc["2022-01-01":]
    q2 = pd.qcut(b2["gapA"], 5, labels=["Q1最贵", "Q2", "Q3", "Q4", "Q5最便宜"])
    tab2 = b2.groupby(q2, observed=True)[["f20", "f60", "f120", "f250", "r60", "r250"]].mean() * 100
    tab2["n"] = b2.groupby(q2, observed=True).size()
    print(tab2.round(2).to_string())
    print("IC(gapA, fwd) 2022+:", {h: round(b2["gapA"].corr(b2[f"f{h}"]), 3) for h in (20, 60, 120, 250)})

    print("\n========== 回测 3：极端信号（zB ≥ 1.5 / ≥ 2.0）事件研究 ==========")
    for thr in (1.0, 1.5, 2.0):
        ev = b1[b1["zB"] >= thr]
        # 去重：事件间隔 ≥ 60 日
        keep, lastt = [], None
        for t in ev.index:
            if lastt is None or (t - lastt).days >= 60:
                keep.append(t); lastt = t
        e = b1.loc[keep]
        print(f"  zB≥{thr}: 事件 {len(keep)} 次 | 前向60日均 {e.f60.mean()*100:+.1f}% 胜率 {(e.f60>0).mean()*100:.0f}% | 120日 {e.f120.mean()*100:+.1f}% 胜率 {(e.f120>0).mean()*100:.0f}% | 250日 {e.f250.mean()*100:+.1f}% 胜率 {(e.f250>0).mean()*100:.0f}%")
        print(f"           同期 TIPS 60日变化均 {e.r60.mean():+.2f}pp  250日 {e.r250.mean():+.2f}pp")
        if thr == 1.5:
            print("           事件日期:", [str(t.date()) for t in keep])

    print("\n========== R2：制度溢价是否时变（滚动模型隐含实际利率 vs TIPS 的 2022 后年度均值） ==========")
    yr = df.loc["2006":].groupby(df.loc["2006":].index.year).agg(gapA=("gapA", "mean"), gapB=("gapB", "mean"),
                                                                  real=("real", "mean"), gold=("gold", "last"))
    print(yr.round(2).to_string())

    # 落盘
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gold_real_yield_model_backtest_2026-11-25.csv").write_text(
        bt.loc["2006":].round(4).to_csv(encoding="utf-8"))
    json.dump(results, open(D / "results_A.json", "w"), indent=2, default=float)
    print(f"\n[csv] {OUT}/gold_real_yield_model_backtest_2026-11-25.csv")


if __name__ == "__main__":
    sys.exit(main())
