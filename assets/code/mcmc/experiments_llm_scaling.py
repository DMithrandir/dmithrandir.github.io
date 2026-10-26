"""E-L5 / E-L6: the 2020 noise-benefit skeleton inside test-time scaling.

Thesis under test
-----------------
The 2020 thesis proved *noise benefit = selection benefit*: injected randomness
helps only through an inequality that compares a property of the **selector**
against a property of the **generator**.  Test-time scaling (Best-of-N with a
verifier) is structurally the same object: the injected randomness is the N
independent samples, the selector is the verifier.  This script tests whether the
2020 result predicts the 2025-2026 empirical picture.

Three experiments
-----------------
E-L5.1  **Blind selection is exactly useless.**  With the same N samples but a
        random pick instead of a verifier, accuracy is exactly the single-sample
        rate for every N.  This is Proposition 1 (blind noise == variance
        tuning) in LLM language: sampling alone carries no benefit; only the
        selection operator does.

E-L5.2  **The benefit is governed by a tail-index inequality.**  Correct samples
        score with upper tail index ``alpha_C``, wrong ones with ``alpha_W``.
        Then, asymptotically,

            more sampling helps   <=>   1/alpha_C > 1/alpha_W

        with a critical line at ``alpha_C = alpha_W``.  Below it, accuracy
        *decreases* with N -- the 2020 "negative condition" (Theorem 3) as the
        modern "incorrect-tail-dominant" regime.

E-L5.3  **Gumbel scores make N irrelevant.**  If both populations are Gumbel with
        the same scale, ``P(correct)`` is exactly independent of N.  So "just
        sample more" is a no-op unless the tails separate -- the sharpest form of
        "randomness is not the ingredient".

Run:
    python experiments_llm_scaling.py            # all, writes figures/llm_*.png
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MPL = True
except Exception:  # pragma: no cover
    HAS_MPL = False

RESULTS: dict = {}


# ---------------------------------------------------------------------------
# populations
# ---------------------------------------------------------------------------


def pareto_scores(n: int, alpha: float, rng: np.random.Generator) -> np.ndarray:
    """Upper-tail Pareto: P(S > s) = s^{-alpha}, s >= 1.  Smaller alpha = heavier."""
    return (1.0 - rng.random(n)) ** (-1.0 / alpha)


def gumbel_scores(n: int, mu: float, beta: float, rng: np.random.Generator) -> np.ndarray:
    """Gumbel(mu, beta): P(S > s) = 1 - exp(-exp(-(s-mu)/beta))."""
    return mu - beta * np.log(-np.log(rng.random(n)))


def bon_accuracy(
    N: int,
    p_correct: float,
    sampler_C,
    sampler_W,
    rng: np.random.Generator,
    trials: int = 4000,
    selector: str = "verifier",
) -> dict:
    """Best-of-N with a verifier, split into coverage and selection components.

    Returns ``{"overall", "coverage", "selection"}`` where

    * ``overall``   = P(the selected sample is correct)
    * ``coverage``  = P(at least one correct sample was drawn)  = the pass@N rate
    * ``selection`` = P(selected correct | both populations non-empty), i.e. the
      pure "who wins the maximum" probability with the coverage effect removed.

    The decomposition matters: ``overall = coverage * selection`` (up to the
    all-correct corner case), and the two are governed by different mathematics.
    Conflating them is the modern image of the 2020 thesis's methodological
    criticism -- reporting "noise speeds convergence" without a variance-matched
    control, versus reporting "BoN helps" without a pass@N control.
    """
    hits = covered = sel_hits = sel_trials = 0
    for _ in range(trials):
        if selector == "random":
            hits += int(rng.random() < p_correct)
            continue
        n_c = rng.binomial(N, p_correct)
        if n_c >= 1:
            covered += 1
        if n_c == 0:
            continue
        if n_c == N:
            hits += 1
            continue
        s_c = sampler_C(n_c, rng)
        s_w = sampler_W(N - n_c, rng)
        win = int(s_c.max() > s_w.max())
        hits += win
        sel_hits += win
        sel_trials += 1
    return {
        "overall": hits / trials,
        "coverage": covered / trials,
        "selection": (sel_hits / sel_trials) if sel_trials else float("nan"),
    }


def bon_accuracy_theory(
    N: int, p: float, alpha_C: float, alpha_W: float, grid: int = 4000
) -> float:
    """Exact P(max correct > max wrong) for Pareto scores, integrated numerically.

    Averaging over ``n_c ~ Binomial(N, p)`` and integrating the density of the
    wrong-population maximum against the CDF of the correct-population maximum.
    """
    from math import comb

    s = np.concatenate([np.array([1.0]), np.logspace(0, 6, grid)])
    trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    total = 0.0
    for n_c in range(N + 1):
        prob = comb(N, n_c) * p**n_c * (1.0 - p) ** (N - n_c)
        if prob < 1e-12:
            continue
        if n_c == 0:
            continue
        if n_c == N:
            total += prob
            continue
        n_w = N - n_c
        F_c = np.clip(1.0 - s ** (-alpha_C), 0.0, 1.0) ** n_c
        F_w = np.clip(1.0 - s ** (-alpha_W), 0.0, 1.0)
        f_w = n_w * alpha_W * s ** (-alpha_W - 1.0) * np.maximum(F_w, 1e-300) ** (n_w - 1)
        total += prob * float(trapz(f_w * F_c, s))
    return float(total)


# ---------------------------------------------------------------------------
# E-L5.1  blind selection is exactly useless
# ---------------------------------------------------------------------------


def e_l51(p: float = 0.05, Ns=(1, 2, 4, 8, 16, 32, 64), trials: int = 20000,
          seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    row = {}
    for N in Ns:
        blind = bon_accuracy(N, p, None, None, rng, trials=trials,
                             selector="random")["overall"]
        row[N] = blind
    worst = max(abs(v - p) for v in row.values())
    _log(f"E-L5.1  blind selection vs single-sample rate p={p}: "
         + "  ".join(f"N={k}:{v:.4f}" for k, v in row.items())
         + f"   max |dev|={worst:.4f}")
    return {"p": p, "by_N": {str(k): v for k, v in row.items()},
            "max_dev": worst, "pass": bool(worst < 0.02)}


# ---------------------------------------------------------------------------
# E-L5.2  the tail-index inequality
# ---------------------------------------------------------------------------


def gumbel_selection_theory(N: int, p: float, mu_C: float, mu_W: float,
                            beta: float) -> float:
    """Exact E[P(correct wins) | both populations non-empty] for Gumbel scores.

    With equal-scale Gumbel the max over ``n`` draws is Gumbel(mu + beta ln n,
    beta), so

        P(max_C > max_W | n_C, n_W) = n_C A / (n_C A + n_W B),
        A = exp(mu_C/beta), B = exp(mu_W/beta),

    i.e. a multinomial-logit comparison.  Averaging over ``n_C ~ Bin(N, p)``
    conditioned on ``1 <= n_C <= N-1`` gives the curve.  **The N does not cancel
    at finite N**: it cancels only in the typical-proportion limit
    ``n_C ~ Np``, so the conditional selection probability drifts *down* with N
    towards ``pA/(pA + (1-p)B)`` as the conditioning stops forcing a lucky draw.
    """
    from math import comb, exp

    A = exp(mu_C / beta)
    B = exp(mu_W / beta)
    num = den = 0.0
    for n_c in range(1, N):
        prob = comb(N, n_c) * p**n_c * (1 - p) ** (N - n_c)
        n_w = N - n_c
        num += prob * (n_c * A) / (n_c * A + n_w * B)
        den += prob
    return float(num / den) if den > 0 else float("nan")


def bon_selection_fast(
    N: int, p: float, alpha_C: float, alpha_W: float, rng: np.random.Generator,
    trials: int = 200_000,
) -> float:
    """P(selected correct) for Pareto scores, O(1) per trial, valid for huge N.

    The maximum of ``n`` i.i.d. Pareto(alpha) variables has the inverse-CDF form
    ``(1 - U^{1/n})^{-1/alpha}``, so neither the population size nor N needs to be
    materialised.  ``n_C ~ Poisson(N p)`` replaces the binomial in the small-``p``
    regime (exact in the limit used here).
    """
    nc = rng.poisson(N * p, size=trials)
    win = np.zeros(trials, dtype=bool)
    ok = nc > 0
    if not np.any(ok):
        return 0.0
    n_c = nc[ok]
    max_c = (1.0 - rng.random(n_c.size) ** (1.0 / n_c)) ** (-1.0 / alpha_C)
    n_w = N - n_c
    has_w = n_w > 0
    max_w = np.full(n_c.size, -np.inf)
    max_w[has_w] = (1.0 - rng.random(int(has_w.sum())) ** (1.0 / n_w[has_w])) ** (
        -1.0 / alpha_W
    )
    win[ok] = max_c > max_w
    return float(win.mean())


def tail_crossover_N(p: float, alpha_C: float, alpha_W: float) -> float:
    """Sample count at which the tail competition flips, for Pareto scores.

    ``max of n`` grows like ``n^{1/alpha}``, so the correct population's maximum
    overtakes the wrong one when ``(N p)^{1/aC} > (N(1-p))^{1/aW}``, i.e. when

        ln N > [ (1/aW) ln(1-p) - (1/aC) ln p ] / (1/aC - 1/aW).

    Returns ``inf`` when the inequality cannot hold (``1/aC <= 1/aW``).
    """
    from math import inf, log

    slope = 1.0 / alpha_C - 1.0 / alpha_W
    if slope <= 0:
        return inf
    rhs = (1.0 / alpha_W) * log(max(1.0 - p, 1e-12)) - (1.0 / alpha_C) * log(p)
    return float(np.exp(rhs / slope))


def e_l52(p: float = 0.05, Ns=(1, 4, 16, 64, 256, 1024, 4096, 16384),
          trials: int = 200_000, seed: int = 1) -> dict:
    """Sweep the tail-index ratio over N spanning the crossover.

    Chart convention (the one that caused a mislabelling on the first run):
    ``P(S > s) = s^{-alpha}``, so **smaller alpha = heavier upper tail** and the
    asymptotic verdict is

        more sampling helps  <=>  1/alpha_C > 1/alpha_W  <=>  alpha_C < alpha_W.

    A second condition is easy to miss: the crossover only happens past

        ``N* = exp{ [(1/aW) ln(1-p) - (1/aC) ln p] / (1/aC - 1/aW) }``,

    because the wrong population starts with ``(1-p)/p`` times more draws.  For a
    small base rate this is exponentially large -- ``N* ~ 600`` at ``p = 0.05`` --
    so over the N anyone actually uses, the size imbalance dominates and the tail
    effect is invisible.  That is the honest statement, and it is why empirical
    BoN studies disagree about whether scaling helps.
    """
    rng = np.random.default_rng(seed)
    cases = [
        ("correct heavier (aC=0.8 < aW=1.5)", 0.8, 1.5),
        ("matched tails   (aC=aW=1.2)", 1.2, 1.2),
        ("wrong heavier   (aC=1.5 > aW=0.8)", 1.5, 0.8),
    ]
    out = {}
    for label, aC, aW in cases:
        meas = {N: bon_selection_fast(N, p, aC, aW, rng, trials=trials) for N in Ns}
        nstar = tail_crossover_N(p, aC, aW)
        base = meas[Ns[0]]
        far = meas[Ns[-1]]
        if 1.0 / aC > 1.0 / aW:
            # past N* the correct answer must win; require the measured rise
            pred = "gain"
            agrees = (far > base + 0.05)
        elif 1.0 / aC < 1.0 / aW:
            pred = "harm"
            agrees = (far < base + 0.02)
        else:
            pred = "flat"
            agrees = abs(far - base) < 0.15
        out[label] = {
            "alpha_C": aC, "alpha_W": aW, "N_star": float(nstar),
            "measured": {str(k): v for k, v in meas.items()},
            "start": float(base), "end": float(far),
            "predicted": pred, "agrees": bool(agrees),
        }
        nstar_txt = "inf" if not np.isfinite(nstar) else f"{nstar:.0f}"
        _log(f"E-L5.2  {label}: N*={nstar_txt:>6}  "
             f"{Ns[0]}->{Ns[-1]}: {base:.4f} -> {far:.4f}  "
             f"(predicted {pred}, agrees={agrees})")
    ok = all(v["agrees"] for v in out.values())
    return {"p": p, "cases": out, "pass": bool(ok)}


# ---------------------------------------------------------------------------
# E-L5.3  two mechanisms: coverage and tail competition
# ---------------------------------------------------------------------------


def e_l53(p: float = 0.05, Ns=(1, 2, 4, 8, 16, 32, 64, 128, 256),
          trials: int = 6000, seed: int = 2) -> dict:
    """Separate the two things that make Best-of-N look like it works.

    ``overall = coverage * selection``, and the two move in **opposite**
    directions as N grows:

    * ``coverage = 1 - (1-p)^N`` rises and saturates at 1 -- "did we draw a
      correct answer at all";
    * ``selection = P(win | both populations non-empty)`` *falls*, converging to
      the multinomial-logit limit ``pA/(pA+(1-p)B)``: at small N the conditioning
      ``n_C >= 1`` forces a lucky draw, and as N grows the verifier has to
      discriminate against a much larger wrong population.

    So the reported "BoN improves accuracy with N" is a **coverage** effect, and
    it is bounded by the selection limit.  That is the 2026 image of the 2020
    thesis's central claim: the randomness contributes nothing; what contributes
    is how many correct candidates you happened to draw and how well the selector
    ranks them.  Reporting the rise without the pass@N control is exactly the
    missing variance-matched control of the N-MCMC literature.
    """
    rng = np.random.default_rng(seed)
    mu_C, mu_W, beta = 1.0, 0.6, 0.5
    row_overall, row_cov, row_sel, row_theory = {}, {}, {}, {}
    for N in Ns:
        r = bon_accuracy(
            N, p,
            lambda n, rr: gumbel_scores(n, mu_C, beta, rr),
            lambda n, rr: gumbel_scores(n, mu_W, beta, rr),
            rng, trials=trials,
        )
        row_overall[N] = r["overall"]
        row_cov[N] = r["coverage"]
        row_sel[N] = r["selection"]
        row_theory[N] = gumbel_selection_theory(N, p, mu_C, mu_W, beta)
    # the selection limit that no amount of sampling can exceed
    from math import exp

    limit = (p * exp(mu_C / beta)) / (p * exp(mu_C / beta) + (1 - p) * exp(mu_W / beta))
    finite = [n for n in Ns if np.isfinite(row_sel[n])]
    sel_drop = row_sel[finite[0]] - row_sel[finite[-1]] if len(finite) >= 2 else float("nan")
    cov_rise = row_cov[Ns[-1]] - row_cov[Ns[0]]
    sel_err = float(np.nanmax([abs(row_sel[n] - row_theory[n]) for n in finite]))
    _log(f"E-L5.3  Gumbel equal-scale: overall {row_overall[Ns[0]]:.4f} -> "
         f"{row_overall[Ns[-1]]:.4f} (+{row_overall[Ns[-1]] - row_overall[Ns[0]]:.4f})")
    _log(f"        coverage  {row_cov[Ns[0]]:.4f} -> {row_cov[Ns[-1]]:.4f} "
         f"(+{cov_rise:.4f})   selection {row_sel[finite[0]]:.4f} -> "
         f"{row_sel[finite[-1]]:.4f} ({-sel_drop:+.4f})")
    _log(f"        selection limit (no N can exceed) = {limit:.4f}; "
         f"theory-vs-measured max err = {sel_err:.4f}")
    ok = bool(np.isfinite(sel_drop) and sel_drop > 0.05 and cov_rise > 0.8
              and sel_err < 0.03)
    return {"p": p, "overall": {str(k): v for k, v in row_overall.items()},
            "coverage": {str(k): v for k, v in row_cov.items()},
            "selection": {str(k): v for k, v in row_sel.items()},
            "selection_theory": {str(k): v for k, v in row_theory.items()},
            "selection_limit": float(limit), "selection_drop": float(sel_drop),
            "coverage_rise": float(cov_rise), "selection_err": sel_err,
            "pass": ok}


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------


def figure_tails(res52: dict) -> None:
    if not HAS_MPL:
        return
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.4))
    for label, d in res52["cases"].items():
        Ns = sorted(int(k) for k in d["measured"])
        axes[0].semilogx(Ns, [d["measured"][str(n)] for n in Ns], "o-", label=label, ms=4)
        if np.isfinite(d["N_star"]):
            axes[0].axvline(d["N_star"], ls="--", lw=0.8, alpha=0.6)
    axes[0].axhline(0.0, color="k", lw=0.5)
    axes[0].set_xlabel("N  (samples per problem)")
    axes[0].set_ylabel("P(selected correct)")
    axes[0].set_title("selection probability vs N (dashed = predicted crossover N*)",
                      fontsize=9)
    axes[0].legend(fontsize=6.5)

    # the crossover location as a function of the base rate
    ps = np.logspace(-3, -0.05, 60)
    for label, aC, aW, style in (("correct heavier", 0.8, 1.5, "-"),
                                 ("wrong heavier", 1.5, 0.8, "--")):
        ns = [tail_crossover_N(float(pp), aC, aW) for pp in ps]
        axes[1].semilogx(ps, ns, style, label=label)
    axes[1].set_xlabel("base rate p  (P(a single sample is correct))")
    axes[1].set_ylabel(r"crossover $N^*$")
    axes[1].set_title(r"$N^*$ grows like $p^{-1/\alpha}$: tiny base rates hide the tail effect",
                      fontsize=9)
    axes[1].legend(fontsize=8)
    fig.suptitle("E-L5.2  Two conditions for 'more sampling helps': heavier correct tail AND N > N*",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "llm_tail_regimes.png"), dpi=150)
    plt.close(fig)


def figure_blind(res51: dict, res53: dict) -> None:
    if not HAS_MPL:
        return
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.3))
    Ns = sorted(int(k) for k in res51["by_N"])
    axes[0].semilogx(Ns, [res51["by_N"][str(n)] for n in Ns], "o-",
                     label="random pick (blind control)")
    axes[0].axhline(res51["p"], color="k", ls=":", lw=1.0,
                    label=f"single-sample p={res51['p']}")
    axes[0].set_title("E-L5.1  sampling without selection buys nothing", fontsize=10)
    axes[0].set_xlabel("N")
    axes[0].set_ylabel("accuracy")
    axes[0].legend(fontsize=8)

    Ns2 = sorted(int(k) for k in res53["overall"])
    axes[1].semilogx(Ns2, [res53["overall"][str(n)] for n in Ns2], "o-",
                     label="overall accuracy", ms=4)
    axes[1].semilogx(Ns2, [res53["coverage"][str(n)] for n in Ns2], "^--",
                     label="coverage  P(>=1 correct)", ms=4)
    axes[1].semilogx(Ns2, [res53["selection"][str(n)] for n in Ns2], "s-",
                     label="selection  (coverage removed)", ms=4)
    axes[1].set_title("E-L5.3  the apparent gain is coverage, not verification", fontsize=10)
    axes[1].set_xlabel("N")
    axes[1].set_ylabel("probability")
    axes[1].legend(fontsize=7.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "llm_blind_and_coverage.png"), dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    _log("=== E-L5: the noise-benefit skeleton in test-time scaling ===\n")
    RESULTS["l51"] = e_l51()
    RESULTS["l52"] = e_l52()
    RESULTS["l53"] = e_l53()
    figure_tails(RESULTS["l52"])
    figure_blind(RESULTS["l51"], RESULTS["l53"])
    with open(os.path.join(OUT, "llm_scaling_results.json"), "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, indent=1, default=float)
    failed = [k for k, v in RESULTS.items() if isinstance(v, dict) and not v.get("pass", True)]
    _log("\nPASS" if not failed else f"\nFAILED: {failed}")
    _log(f"wrote {os.path.join(OUT, 'llm_scaling_results.json')}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
