#!/usr/bin/env python3
"""P1 · 结构性断点检验（月频一阶差分 + Chow / HAC-Wald）。

回应「水平回归可能是伪回归」的质疑：对 ln(GLD) 与 TIPS 取月频一阶差分，
检验 2022-01 前后 Δln(GLD) ~ ΔTIPS 的斜率/截距是否发生结构性变化。

  经典 Chow F（同方差假设）
  HAC Wald（Newey-West，对异方差+自相关稳健）—— 主结论以此为准

用法：
  python3 scripts/strategy_lab/p1_structural_break.py \
      --csv reports/策略分析/2026-11/gold_real_yield_model_backtest_2026-11-25.csv \
      --out-dir reports/策略分析/2026-11/p1_out
数据源也可直接用 state/_cache/gold_model（默认）。
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def load_monthly() -> pd.DataFrame:
    """从原始缓存重建月频序列（不依赖回测 CSV 的列）。"""
    import csv
    D = ROOT / "state" / "_cache" / "gold_model"
    g = json.load(open(D / "GLD.json"))["chart"]["result"][0]
    idx = pd.to_datetime(g["timestamp"], unit="s", utc=True).tz_convert("America/New_York").normalize().tz_localize(None)
    vals = g["indicators"]["adjclose"][0]["adjclose"]
    gold = pd.to_numeric(pd.Series(vals, index=idx), errors="coerce").dropna()
    gold = gold[~gold.index.duplicated(keep="last")]
    rows = list(csv.reader(open(D / "DFII10.csv")))[1:]
    real = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in rows if r[1] not in (".", "", "NA")})
    real = real[~real.index.duplicated(keep="last")]
    df = pd.concat([gold.rename("gold"), real.rename("real")], axis=1, join="inner").sort_index()
    df["real"] = df["real"].ffill(limit=10)
    df = df.dropna()
    df["lg"] = np.log(df["gold"])
    m = df.resample("ME").last()                      # 月末
    d = m.diff().dropna()                             # 一阶差分
    d = d.loc["2006-01-01":]
    return d.rename(columns={"lg": "dlnP", "real": "dTIPS"})


def ols_hac(y: np.ndarray, X: np.ndarray, lag: int | None = None):
    """OLS + Newey-West HAC 协方差。返回 beta, cov, resid, n, k。"""
    n, k = X.shape
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    u = y - X @ b
    if lag is None:
        lag = int(np.floor(4 * (n / 100) ** (2 / 9)))   # Newey-West 经验带宽
    XtX_inv = np.linalg.inv(X.T @ X)
    S = (X * u[:, None]).T @ (X * u[:, None])
    for l in range(1, lag + 1):
        w = 1 - l / (lag + 1)
        Xu = X * u[:, None]
        G = Xu[l:].T @ Xu[:-l]
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv * n / (n - k)
    return b, cov, u, n, k


def chow_classic(d: pd.DataFrame, break_date: str) -> dict:
    pre = d.loc[:break_date].iloc[:-1]                 # 断点前
    post = d.loc[break_date:]
    y, x = d.dlnP.values, d.dTIPS.values
    X = np.column_stack([np.ones(len(d)), x])
    def ssr(seg):
        yy, xx = seg.dlnP.values, seg.dTIPS.values
        XX = np.column_stack([np.ones(len(seg)), xx])
        bb, *_ = np.linalg.lstsq(XX, yy, rcond=None)
        return float(np.sum((yy - XX @ bb) ** 2)), bb
    s_pooled, _ = ssr(d); s_pre, b_pre = ssr(pre); s_post, b_post = ssr(post)
    k = 2; n = len(d)
    F = ((s_pooled - s_pre - s_post) / k) / ((s_pre + s_post) / (n - 2 * k))
    from scipy import stats
    p = 1 - stats.f.cdf(F, k, n - 2 * k)
    return dict(F=round(F, 3), p=float(f"{p:.3g}"), df=(k, n - 2 * k),
                b_pre=[round(v, 4) for v in b_pre], b_post=[round(v, 4) for v in b_post],
                n_pre=len(pre), n_post=len(post), n=n)


def hac_wald(d: pd.DataFrame, break_date: str) -> dict:
    """交互模型 y = a + b·x + c·D + d·D·x，HAC 协方差下 Wald 检验 c=d=0。"""
    D = (d.index >= break_date).astype(float)
    x = d.dTIPS.values; y = d.dlnP.values
    X = np.column_stack([np.ones(len(d)), x, D, D * x])
    b, cov, u, n, k = ols_hac(y, X)
    R = np.zeros((2, k)); R[0, 2] = 1; R[1, 3] = 1     # 检验 c, d
    Rb = R @ b
    W = float(Rb @ np.linalg.inv(R @ cov @ R.T) @ Rb)
    from scipy import stats
    p = 1 - stats.chi2.cdf(W, 2)
    # 分段斜率与 HAC t
    se = np.sqrt(np.diag(cov))
    return dict(Wald_chi2=round(W, 3), p=float(f"{p:.3g}"), df=2,
                a=round(b[0], 4), b_pre=round(b[1], 4), c=round(b[2], 4), d_slope_shift=round(b[3], 4),
                b_post=round(b[1] + b[3], 4),
                t_b_pre=round(b[1] / se[1], 2), t_d=round(b[3] / se[3], 2),
                nw_lag=int(np.floor(4 * (n / 100) ** (2 / 9))), n=n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="")
    ap.add_argument("--out-dir", default="reports/策略分析/2026-11/p1_out")
    ap.add_argument("--break", default="2022-01-01")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    d = load_monthly()
    print(f"月频一阶差分样本：{d.index[0].date()} → {d.index[-1].date()}  n={len(d)}")
    print(f"断点：{getattr(args, "break")}\n")

    chow = chow_classic(d, getattr(args, "break"))
    hac = hac_wald(d, getattr(args, "break"))
    print("=== 经典 Chow F（同方差）===")
    print(f"  F={chow['F']}  p={chow['p']}  df={chow['df']}  n_pre={chow['n_pre']} n_post={chow['n_post']}")
    print(f"  斜率 pre={chow['b_pre'][1]:+.4f}  post={chow['b_post'][1]:+.4f}")
    print("\n=== HAC Wald（Newey-West，主结论）===")
    print(f"  Wald χ²={hac['Wald_chi2']}  p={hac['p']}  df={hac['df']}  NW lag={hac['nw_lag']}  n={hac['n']}")
    print(f"  斜率 pre={hac['b_pre']:+.4f} (t={hac['t_b_pre']})  斜率变化 d={hac['d_slope_shift']:+.4f} (t={hac['t_d']})  post={hac['b_post']:+.4f}")
    print(f"  截距变化 c={hac['c']:+.4f}")

    verdict = "拒绝无断点（结构变化显著）" if hac["p"] < 0.05 else "不能拒绝无断点"
    print(f"\n裁决：HAC p={hac['p']} → {verdict}")

    out = ROOT / args.out_dir; out.mkdir(parents=True, exist_ok=True)
    res = dict(break_date=getattr(args, "break"), n_monthly=len(d), chow_classic=chow, hac_wald=hac, verdict=verdict)
    (out / "structural_break.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    d.to_csv(out / "monthly_first_diff.csv", encoding="utf-8")
    print(f"[out] {out}/structural_break.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
