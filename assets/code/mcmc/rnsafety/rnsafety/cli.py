"""Command-line interface for the reverse-noise safety audit.

Examples
--------
Run the built-in synthetic benchmark (all six injection families, 20 seeds)::

    python -m rnsafety.cli synthetic --seeds 20

Audit a real gradient stream recorded as JSONL, one JSON object per step::

    python -m rnsafety.cli audit run.jsonl --baseline baseline.json

where each line is one of

    {"grad_hat": [...], "grad_clean": [...]}      # both available (best)
    {"grad_hat": [...], "eps": [...]}             # noise isolated
    {"grad_hat": [...], "noise_sigma": 0.35}      # noiseless reference is eps = 0

Characterise the honest noise law once, then reuse it::

    python -m rnsafety.cli fit-baseline clean.jsonl -o baseline.json

Measure the *actual* false-alarm rate of the certificate against its bound::

    python -m rnsafety.cli calibrate --trials 300 --steps 256 --dim 64
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable, Iterator, List, Optional

import numpy as np

from .audit import AuditReport, Baseline, audit_stream, fit_baseline
from .generate import FAMILIES, AttackSpec, gradient_stream


# ---------------------------------------------------------------------------
# JSONL loading
# ---------------------------------------------------------------------------


def iter_records(path: str) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover
                raise SystemExit(f"{path}:{line_no}: bad JSON ({exc})") from exc


def records_to_stream(records: Iterable[dict]) -> dict:
    """Convert JSONL records into the dict ``audit_stream`` expects."""
    g_hat: list = []
    g_clean: list = []
    eps: list = []
    have_clean = True
    have_eps = True
    for i, rec in enumerate(records):
        if "grad_hat" not in rec:
            raise SystemExit(f"record {i}: missing 'grad_hat'")
        gh = np.asarray(rec["grad_hat"], dtype=float)
        g_hat.append(gh)
        if "grad_clean" in rec:
            g_clean.append(np.asarray(rec["grad_clean"], dtype=float))
        else:
            have_clean = False
        if "eps" in rec:
            eps.append(np.asarray(rec["eps"], dtype=float))
        elif "noise_sigma" in rec:
            eps.append(float(rec["noise_sigma"]) * np.zeros_like(gh))
        else:
            have_eps = False
    if not g_hat:
        raise SystemExit("empty stream")
    dims = {v.shape for v in g_hat}
    if len(dims) != 1:
        raise SystemExit(f"inconsistent gradient dimensions in stream: {dims}")
    out = {"g_hat": np.stack(g_hat)}
    if have_clean:
        out["g_clean"] = np.stack(g_clean)
    if have_eps:
        out["eps"] = np.stack(eps)
    if "g_clean" not in out and "eps" not in out:
        raise SystemExit("each record needs 'grad_clean' or 'eps' (or 'noise_sigma')")
    out["meta"] = {"source": "jsonl"}
    return out


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def cmd_synthetic(args: argparse.Namespace) -> int:
    """Built-in benchmark: does the tool catch every family, and how fast?"""
    rows = []
    families = args.families or list(FAMILIES)
    clean_eps = np.concatenate(
        [
            gradient_stream(AttackSpec(family="clean", n_steps=args.steps,
                                       dim=args.dim, seed=s, sigma=args.sigma))["eps"]
            for s in range(max(3, args.seeds // 4))
        ]
    )
    baseline = fit_baseline(clean_eps)

    for fam in families:
        verdicts: dict = {}
        risks: List[float] = []
        n_fire: dict = {}
        first_fire: List[int] = []
        for seed in range(args.seeds):
            spec = AttackSpec(family=fam, n_steps=args.steps, dim=args.dim,
                              seed=1000 + seed, sigma=args.sigma,
                              spike=args.spike, p_micro=args.p_micro)
            stream = gradient_stream(spec)
            rep = audit_stream(stream, baseline=baseline, alpha=args.alpha,
                               effect_floor=args.effect_floor)
            verdicts[rep.verdict] = verdicts.get(rep.verdict, 0) + 1
            risks.append(rep.risk_score)
            for name in rep.fired_monitors:
                n_fire[name] = n_fire.get(name, 0) + 1
            first_fire.append(_first_alarm_step(stream, baseline, args))
        rows.append(
            {
                "family": fam,
                "verdicts": verdicts,
                "mean_risk": float(np.mean(risks)),
                "mean_first_alarm_step": float(np.mean(first_fire)),
                "detectors": n_fire,
            }
        )
        print(f"  {fam:<24} " + " ".join(f"{k}={v}" for k, v in verdicts.items())
              + f"   mean_risk={np.mean(risks):5.1f}"
              + f"   mean_first_alarm@{np.mean(first_fire):6.1f}", flush=True)

    print("\nSummary table")
    print(f"{'family':<26}{'harmful':>8}{'suspect':>8}{'watch':>7}{'clean':>7}"
          f"{'risk':>7}{'alarm@':>9}  detectors")
    for r in rows:
        v = r["verdicts"]
        print(f"{r['family']:<26}{v.get('harmful',0):>8}{v.get('suspect',0):>8}"
              f"{v.get('watch',0):>7}{v.get('clean',0):>7}"
              f"{r['mean_risk']:>7.1f}{r['mean_first_alarm_step']:>9.1f}"
              f"  {r['detectors']}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, ensure_ascii=False)
        print(f"\nwrote {args.json}")
    return 0


def _first_alarm_step(stream: dict, baseline: Baseline, args: argparse.Namespace) -> float:
    """Smallest window in which the cosine monitor first fires (attack response time)."""
    eps = stream["eps"]
    g_hat = stream["g_hat"]
    ref = stream.get("g_clean", g_hat)
    n = g_hat.shape[0]
    from .core import detection_certificate, reverse_score

    cos = reverse_score(ref, eps)
    for k in (8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096):
        if k > n:
            break
        cert = detection_certificate(cos[:k], alpha=args.alpha, n_signflip=20_000)
        if cert.mean_cos <= -args.effect_floor and min(
            cert.p_value_signflip, cert.p_value_bernstein
        ) <= args.alpha:
            return float(k)
    return float(n)


def cmd_calibrate(args: argparse.Namespace) -> int:
    """Measure the empirical false-alarm rate of the certificate under H0."""
    from .core import detection_certificate

    rng = np.random.default_rng(args.seed)
    alarms = {a: 0 for a in args.alphas}
    per_alpha_rows = []
    for t in range(args.trials):
        # H0: a sign-symmetric, zero-mean reverse score.  Use a t-like law so
        # the test is not handed a Gaussian for free.
        df = 4.0
        cos = rng.standard_t(df, size=args.steps) / np.sqrt(df / (df - 2.0)) * 0.7
        cert = detection_certificate(cos, alpha=min(args.alphas), n_signflip=20_000,
                                    seed=t)
        for a in args.alphas:
            if min(cert.p_value_signflip, cert.p_value_bernstein) <= a:
                alarms[a] += 1
    print(f"H0 calibration over {args.trials} trials, {args.steps} steps each")
    print(f"{'alpha':>10}{'empirical':>12}{'ratio':>10}")
    for a in args.alphas:
        emp = alarms[a] / args.trials
        ratio = emp / a if a > 0 else float("nan")
        per_alpha_rows.append({"alpha": a, "empirical": emp, "ratio": ratio})
        print(f"{a:>10.1e}{emp:>12.4f}{ratio:>10.2f}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(per_alpha_rows, fh, indent=2)
        print(f"wrote {args.json}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    stream = records_to_stream(iter_records(args.path))
    baseline = None
    if args.baseline:
        with open(args.baseline, "r", encoding="utf-8") as fh:
            baseline = Baseline(**json.load(fh))
    rep = audit_stream(stream, baseline=baseline, alpha=args.alpha,
                       effect_floor=args.effect_floor)
    print(rep.summary())
    if rep.limitations:
        print("\nlimits of this verdict:")
        for l in rep.limitations:
            print(f"  - {l}")
    if rep.recommendations:
        print("\nrecommended actions:")
        for r in rep.recommendations:
            print(f"  - {r}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(rep.to_json())
        print(f"\nwrote {args.json}")
    return 0 if rep.verdict in ("clean", "watch") else 2


def cmd_fit_baseline(args: argparse.Namespace) -> int:
    stream = records_to_stream(iter_records(args.path))
    if "eps" not in stream:
        raise SystemExit("baseline fitting needs 'eps' (or 'noise_sigma') per record")
    b = fit_baseline(stream["eps"])
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(b.as_dict(), fh, indent=2)
    print(f"baseline written to {args.output}")
    print(f"  per-coordinate rms : {b.per_coord_scale:.6g}")
    print(f"  mean noise norm    : {b.mean_noise_norm:.6g}")
    print(f"  top spectrum share : {b.spectrum_top_fraction:.6g}")
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rnsafety",
        description="Reverse-noise safety audit: is the noise in your training "
                    "pipeline pointing against your gradient?",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synthetic", help="run the built-in six-family benchmark")
    s.add_argument("--seeds", type=int, default=12)
    s.add_argument("--steps", type=int, default=512)
    s.add_argument("--dim", type=int, default=256)
    s.add_argument("--sigma", type=float, default=0.35)
    s.add_argument("--spike", type=float, default=2.0)
    s.add_argument("--p-micro", type=float, default=1e-3)
    s.add_argument("--alpha", type=float, default=1e-3)
    s.add_argument("--effect-floor", type=float, default=0.01)
    s.add_argument("--families", nargs="*", default=None)
    s.add_argument("--json", default=None)
    s.set_defaults(func=cmd_synthetic)

    c = sub.add_parser("calibrate", help="false-alarm calibration under H0")
    c.add_argument("--trials", type=int, default=200)
    c.add_argument("--steps", type=int, default=256)
    c.add_argument("--dim", type=int, default=64)
    c.add_argument("--alphas", type=float, nargs="*", default=[1e-2, 1e-3, 1e-4])
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--json", default=None)
    c.set_defaults(func=cmd_calibrate)

    a = sub.add_parser("audit", help="audit a JSONL gradient stream")
    a.add_argument("path")
    a.add_argument("--baseline", default=None)
    a.add_argument("--alpha", type=float, default=1e-3)
    a.add_argument("--effect-floor", type=float, default=0.01)
    a.add_argument("--json", default=None)
    a.set_defaults(func=cmd_audit)

    b = sub.add_parser("fit-baseline", help="characterise a clean noise law")
    b.add_argument("path")
    b.add_argument("-o", "--output", default="baseline.json")
    b.set_defaults(func=cmd_fit_baseline)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
