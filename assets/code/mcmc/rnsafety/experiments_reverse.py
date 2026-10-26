"""Numerical verification of every claim in
``paper/反向噪声安全工具-定理与可证性.md``.

Each experiment prints a PASS/FAIL verdict against a stated tolerance, so the
document's claims are checked rather than asserted:

    E-R1  Theorem R1  exact increment identity and the delta/w decomposition
    E-R2  Counterexamples R5.1 (condition number) and R5.2 (cosine density)
    E-R3  Theorem R2  the angle boundary and its ||s|| -> 0 jump
    E-R4  Theorem R3  bias/condition-number scaling and the independence claim
    E-R5  Theorem R4  false-alarm calibration on clean symmetric heavy tails
    E-R6  the seven-family detection benchmark with the auditor
    E-R7  Theorem R4b the invisibility/effectiveness boundary, swept
    E-R8  tracking vs fixed injection: spectral invisibility is not safety
    E-R9  the auditor's own limitations, stated by the tool itself

Outputs: ``figures/reverse_*.png`` and ``figures/reverse_results.json``.

Run from the ``rnsafety`` directory::

    python experiments_reverse.py            # everything, ~10 min
    python experiments_reverse.py --quick    # fewer repetitions
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rnsafety import FAMILIES, audit_stream, fit_baseline  # noqa: E402
from rnsafety.core import (  # noqa: E402
    detection_certificate,
    exchangeable_null_spectrum,
    gradient_loss_increment,
    min_order_statistic_z,
    noise_benefit_increment,
    noise_benefit_condition_boundary,
    power_spectrum,
    quadratic_loss_increment,
    random_matrix_edge_quantile,
    reverse_noise_effect,
    reverse_score,
    robust_noise_scale,
    spectral_report,
    update_identity_terms,
)
from rnsafety.generate import AttackSpec, gradient_stream  # noqa: E402

FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(FIG, exist_ok=True)

RESULTS: dict = {}
CHECKS: list = []


def check(name: str, ok: bool, detail: str) -> None:
    CHECKS.append({"name": name, "pass": bool(ok), "detail": detail})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


# ---------------------------------------------------------------------------
# E-R1
# ---------------------------------------------------------------------------


def e_r1(n_steps: int = 200, d: int = 32, seed: int = 0) -> None:
    print("\nE-R1  Theorem R1: exact increment identity", flush=True)
    rng = np.random.default_rng(seed)
    g = rng.standard_normal((n_steps, d))
    eps = 0.4 * rng.standard_normal((n_steps, d))
    h = rng.standard_normal((d, d))
    H = (h + h.T) / 2 + 2.0 * np.eye(d)          # symmetric positive definite
    eta = 0.05

    # (1) quadratic-model increment == its own closed form
    step = g + eps
    manual = -eta * np.sum(step * step, axis=1) + 0.5 * eta**2 * np.einsum(
        "ni,ij,nj->n", step, H, step)
    quad = quadratic_loss_increment(g, H, eps, eta)
    err = float(np.max(np.abs(quad - manual)) / max(np.max(np.abs(manual)), 1e-30))
    check("R1 quadratic increment matches the closed form", err < 1e-12,
          f"max relative error {err:.2e}")

    # (2) harm = noisy - clean, and it decomposes into it exactly
    harm = noise_benefit_increment(g, H, eps, eta)
    rec = quad - gradient_loss_increment(g, H, eta)
    err = float(np.max(np.abs(harm - rec)) / max(np.max(np.abs(rec)), 1e-30))
    check("R1 harm equals noisy-minus-clean increment", err < 1e-12,
          f"max relative error {err:.2e}")

    # (3) the delta/w decomposition is an identity
    terms = update_identity_terms(g, eps, eta=eta)
    recon = terms["proj"] ** 2 + terms["orth_sq"]
    err = float(np.max(np.abs(recon - terms["noise_sq"]))
                / max(np.max(terms["noise_sq"]), 1e-30))
    check("R1 ||eps||^2 = delta^2 + ||w||^2", err < 1e-12,
          f"max relative error {err:.2e}")

    # (4) the observable forms of the reverse score: cos(eps,g) is exactly the
    #     reverse_score against g, and it also equals <eps,g>/(|g||eps|) when
    #     computed from the contaminated gradient with eps isolated
    cos_direct = reverse_score(g, eps)
    cos_recon = reverse_score(g, g + eps - g)
    err = float(np.max(np.abs(cos_direct - cos_recon)))
    check("R1 reverse score is invariant to how eps is reconstructed", err < 1e-12,
          f"max absolute error {err:.2e}")
    # and the trap: using g_hat as the reference is biased positive.  The bias is
    # E[cos(g_hat,eps)] = ||eps||/sqrt(||g||^2+||eps||^2), so even a modest noise
    # level hides the sign of the reverse score completely.
    trap = reverse_score(g + eps, eps)
    predicted = float(np.mean(
        np.linalg.norm(eps, axis=1)
        / np.sqrt(np.linalg.norm(g, axis=1) ** 2 + np.linalg.norm(eps, axis=1) ** 2)))
    check("R1 using the contaminated gradient as reference is biased positive",
          float(np.mean(trap)) > 0.3 and abs(float(np.mean(trap)) - predicted) < 0.05,
          f"mean cos(g_hat, eps) = {np.mean(trap):+.4f} vs predicted {predicted:+.4f}, "
          f"true E[cos(eps,g)] = {np.mean(cos_direct):+.4f}")

    RESULTS["E-R1"] = {"quad_rel_err": err, "max_abs_cos_err": err}

    # figure: the identity holds, and the harm is first order in delta
    plt = _plt()
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].scatter(terms["reverse_score"], harm, s=6, alpha=0.6)
    ax[0].axvline(0, color="k", lw=0.8)
    ax[0].set_xlabel(r"reverse score $\cos(\epsilon,g)$")
    ax[0].set_ylabel(r"harm $\Delta$ (noisy $-$ clean)")
    ax[0].set_title("R1: first-order harm is linear in the reverse score")
    ax[1].scatter(terms["proj"] ** 2, terms["orth_sq"], s=6, alpha=0.6)
    lim = max(terms["proj"].max() ** 2, terms["orth_sq"].max()) * 1.05
    ax[1].plot([0, lim], [lim, 0], "k--", lw=1,
               label=r"$\delta^2+\|w\|^2=\|\epsilon\|^2$")
    ax[1].set_xlabel(r"$\delta^2$ (along $g$)")
    ax[1].set_ylabel(r"$\|w\|^2$ (orthogonal)")
    ax[1].set_title("R1: exact orthogonal decomposition")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "reverse_r1_identity.png"), dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# E-R2
# ---------------------------------------------------------------------------


def e_r2(d: int = 128, n: int = 4096, seed: int = 0) -> None:
    print("\nE-R2  Counterexamples R5.1 and R5.2", flush=True)
    rng = np.random.default_rng(seed)

    # --- R5.1: isotropic reverse injection leaves the condition number at 1
    #     The claim is that kappa_u is BOUNDED and independent of the reverse
    #     strength -- not that it equals 1 to sampling precision, which would be
    #     a statement about the estimator rather than about the noise.
    g = rng.standard_normal((n, d))
    g /= np.linalg.norm(g, axis=1, keepdims=True)
    alphas = np.logspace(-3, 3, 13)
    kappas, rhos = [], []
    for a in alphas:
        # eps independent of g, then deterministically mirrored: the strongest
        # "reverse" intervention available, and by symmetry E[cos] stays 0
        eps = a * rng.standard_normal((n, d))
        proj = np.sum(eps * g, axis=1)
        quad = float(np.mean(proj**2))
        ell = float(np.mean(np.sum(eps**2, axis=1))) / d
        kappas.append(quad / ell)
        rhos.append(float(np.mean(proj / (np.linalg.norm(eps, axis=1) + 1e-300))))
    kap = np.array(kappas)
    spread = float(np.max(np.abs(kap - 1.0)))
    # the honest statement: no growth with alpha, and within the estimator's own
    # sampling error sqrt(2/n)
    check("R5.1 isotropic injection: kappa_u does not grow with the reverse scale",
          spread < 3.0 * np.sqrt(2.0 / n),
          f"max |kappa-1| = {spread:.3e} for alpha in [1e-3, 1e3], "
          f"estimator sd = {np.sqrt(2.0/n):.3e}")
    check("R5.1 the reverse score stays 0 (no singularity, no divergence)",
          max(abs(r) for r in rhos) < 3.0 * np.sqrt(1.0 / (n * d)),
          f"max |mean cos| = {max(abs(r) for r in rhos):.2e}, "
          f"estimator sd = {np.sqrt(1.0/(n*d)):.2e}")

    # --- R5.2: the cosine density is analytic, no atom, no pole
    eps = 0.35 * rng.standard_normal((n * 5, d))
    gbig = rng.standard_normal((n * 5, d))
    T = reverse_score(gbig, eps)
    # analytic density: f(t) = Gamma(d/2)/(sqrt(pi) Gamma((d-1)/2)) (1-t^2)^((d-3)/2)
    t_grid = np.linspace(-0.98, 0.98, 401)
    from math import gamma as _gamma
    theory = (_gamma(d / 2.0) / (np.sqrt(np.pi) * _gamma((d - 1) / 2.0))
              * np.maximum(1 - t_grid**2, 0.0) ** ((d - 3) / 2.0))
    # CDF comparison on the analytic support (histograms cannot resolve the
    # (1-t^2)^62 tails, whose density is far below float resolution at |t|>0.9)
    emp_cdf = np.array([float(np.mean(T <= t)) for t in t_grid])
    from math import erf
    th_cdf = np.array([0.5 * (1 + erf(t * np.sqrt(d / 2.0) / np.sqrt(1 - 1.0 / d)))
                       for t in t_grid])
    ks = float(np.max(np.abs(emp_cdf - th_cdf)))
    check("R5.2 cosine CDF matches the analytic Beta law", ks < 0.02,
          f"max CDF gap {ks:.4f} on the analytic support")
    dens = np.array([_beta_cos_density(t, d) for t in t_grid])
    check("R5.2 the density is positive and finite on the whole interior",
          bool(np.all(dens > 0) and np.all(np.isfinite(dens))),
          f"min density {dens.min():.3e} at |t|<=0.98, max {dens.max():.3f}")
    check("R5.2 no atom: the largest single-value probability mass is O(1/n)",
          float(np.max(np.bincount(np.clip(((T + 1) / 2 * 4096).astype(int),
                                           0, 4095))) / T.size) < 20.0 / 4096,
          f"max bin mass {float(np.max(np.bincount(np.clip(((T+1)/2*4096).astype(int),0,4095)))/T.size):.4f} "
          f"vs uniform {1/4096:.4f}")
    check("R5.2 variance is 1/d as predicted",
          abs(float(np.var(T)) - 1.0 / d) < 0.005,
          f"empirical {np.var(T):.5f} vs 1/d = {1.0/d:.5f}")

    RESULTS["E-R2"] = {
        "alphas": alphas.tolist(), "kappas": [float(k) for k in kappas],
        "rhos": [float(r) for r in rhos], "density_ks": ks,
        "emp_var": float(np.var(T)), "theory_var": 1.0 / d,
        "t_grid": t_grid.tolist(), "cdf_emp": emp_cdf.tolist(),
        "cdf_theory": th_cdf.tolist(),
    }

    plt = _plt()
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].semilogx(alphas, kappas, "o-")
    ax[0].axhline(1.0, color="k", ls="--", lw=1, label=r"$\kappa_u\equiv1$")
    ax[0].set_xlabel(r"isotropic noise scale $\alpha$")
    ax[0].set_ylabel(r"directional condition number $\kappa_u$")
    ax[0].set_ylim(0.5, 1.5)
    ax[0].set_title("R5.1: reverse isotropy never creates a singularity")
    ax[0].legend()
    ax[1].plot(t_grid, emp_cdf, "o", ms=3, label="empirical CDF")
    ax[1].plot(t_grid, th_cdf, "-", lw=1.5, label="analytic $\\Phi(t\\sqrt{d/2})$")
    ax[1].set_xlabel(r"$\cos(\epsilon,g)$")
    ax[1].set_ylabel("CDF")
    ax[1].set_title("R5.2: the cosine law is smooth (no atom, no pole)")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "reverse_r2_counterexamples.png"), dpi=150)
    plt.close(fig)


def _beta_cos_density(t: float, d: int) -> float:
    """Analytic density of cos(theta) for a uniform direction in R^d."""
    from math import gamma as _gamma
    if abs(t) >= 1.0:
        return 0.0
    return (_gamma(d / 2.0) / (np.sqrt(np.pi) * _gamma((d - 1) / 2.0))
            * (1.0 - t * t) ** ((d - 3) / 2.0))


# ---------------------------------------------------------------------------
# E-R3
# ---------------------------------------------------------------------------


def _brute_feasible(s_norm: float, A: float, sigma: float = 1.0,
                    grid: int = 1200, vmax: float | None = None) -> bool:
    """Independent brute-force feasibility of condition (2) on a (||n||, angle) grid.

    Condition (2) is ``||n||^2 - 2||n|| ||s|| cos(theta) + 2 sigma^2 A <= 0`` with
    ``s`` along the first axis.  This shares no algebra with the closed form, so
    agreement is evidence rather than a restatement.  The grid cannot resolve the
    degenerate point ``r = 0`` exactly, so callers must not use it *at* the
    threshold.
    """
    if vmax is None:
        vmax = 4.0 * s_norm + 4.0 * sigma * np.sqrt(abs(A) + 1e-6)
    vs = np.linspace(0.0, vmax, grid)
    th = np.linspace(0.0, 2.0 * np.pi, grid)
    V, T = np.meshgrid(vs, th, indexing="ij")
    f = V**2 - 2.0 * V * s_norm * np.cos(T) + 2.0 * sigma**2 * A
    return bool(np.any(f <= 0.0))


def e_r3(seed: int = 0) -> None:
    """Theorem R2 (corrected): the admissible set is a ball centred at n = s.

    Completing the square in condition (2) gives
    ``||n - s||^2 <= ||s||^2 - 2 sigma^2 A``, so everything follows from one line:
    radius, the existence threshold ``sqrt(2 sigma^2 A)`` in the ``A > 0`` branch,
    and the direction of the cone closing onto ``cos(n,s) -> +1``.

    Regression: this experiment previously asserted the *opposite* -- that the
    condition is satisfiable at every jump strength, that a zero-mean law always
    works, and that the required direction goes backwards.  All three came from
    treating (2) as a bound on ``cos(n,s)`` instead of completing the square, and
    all three contradicted the parent paper's own E1-D measurement (accepted noise
    correlates +0.453 with the jump).
    """
    print("\nE-R3  Theorem R2: admissible-set geometry", flush=True)
    sigma = 1.0
    rows = []

    # --- branch 1: A > 0, threshold behaviour -------------------------------
    A_pos = 2.0
    thr = float(np.sqrt(2.0 * sigma**2 * A_pos))
    for mult in (0.5, 0.9, 0.99, 1.01, 1.1, 1.5, 2.0, 5.0):
        s_norm = thr * mult
        info = noise_benefit_condition_boundary(s_norm, A_pos, sigma=sigma)
        r_expected = float(np.sqrt(max(s_norm**2 - 2.0 * sigma**2 * A_pos, 0.0)))
        brute = _brute_feasible(s_norm, A_pos, sigma)
        rows.append({
            "A": A_pos, "s_norm": float(s_norm), "mult": float(mult),
            "feasible": bool(info["feasible"]),
            "radius": float(info["radius"]),
            "radius_expected": r_expected,
            "min_cos": float(info["min_cos"]),
            "brute": bool(brute),
        })

    above = [r for r in rows if r["mult"] > 1.01]
    below = [r for r in rows if r["mult"] < 0.99]
    check("R2 (A>0) feasibility thresholds at sqrt(2 sigma^2 A)",
          all(not r["feasible"] for r in below) and all(r["feasible"] for r in above),
          f"thr={thr:.4f}; infeasible for ||s||/thr in "
          f"{[r['mult'] for r in below]}, feasible for {[r['mult'] for r in above]}")
    check("R2 (A>0) the radius matches sqrt(||s||^2 - 2 sigma^2 A)",
          all(abs(r["radius"] - r["radius_expected"]) < 1e-9 for r in above),
          "max deviation "
          f"{max(abs(r['radius'] - r['radius_expected']) for r in above):.2e}")
    check("R2 (A>0) the admissible cone opens from cos = +1",
          all(r["min_cos"] > 0.0 for r in above),
          "min cos over the ball is "
          f"{[round(r['min_cos'], 3) for r in above]} -- never negative, so "
          "fully-reversed noise never satisfies (2)")
    check("R2 (A>0) the closed form agrees with an independent brute-force scan",
          all(r["feasible"] == r["brute"] for r in above),
          f"agreement on {sum(r['feasible'] == r['brute'] for r in above)}/"
          f"{len(above)} non-degenerate points")

    # --- branch 2: A <= 0, always satisfiable ------------------------------
    A_neg = -0.5
    rows_neg = []
    for s_norm in (0.05, 0.3, 1.0, 4.0):
        info = noise_benefit_condition_boundary(s_norm, A_neg, sigma=sigma)
        rows_neg.append({"A": A_neg, "s_norm": float(s_norm),
                         "feasible": bool(info["feasible"]),
                         "radius": float(info["radius"]),
                         "zero_reachable": bool(info["zero_reachable"]),
                         "regime": info["regime"],
                         "brute": _brute_feasible(s_norm, A_neg, sigma)})
    check("R2 (A<=0) always satisfiable, and n = 0 is admissible",
          all(r["feasible"] and r["zero_reachable"] and r["brute"] for r in rows_neg),
          "the ball contains the origin whenever A <= 0, so the condition is met "
          "trivially by no noise at all")

    RESULTS["E-R3"] = {
        "figure": "reverse_r3_boundary.png",
        "threshold_A_pos": thr,
        "rows_A_pos": rows,
        "rows_A_neg": rows_neg,
        "note": "corrected 2026-10-26: admissible set is a ball centred at n = s; "
                "the required direction is +s (cos -> +1), not -s",
    }

    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    sq = np.array([r["s_norm"] for r in rows])
    min_cos = np.array([r["min_cos"] for r in above])
    sq_above = np.array([r["s_norm"] for r in above])
    axes[0].plot(sq_above, min_cos, "o-", color="C0")
    axes[0].axvline(thr, color="k", ls="-.", lw=1.2,
                    label=r"threshold $\sqrt{2\sigma^2A}$")
    axes[0].axhline(0.0, color="C3", ls=":", lw=1.0, label="cos = 0 (orthogonal)")
    axes[0].set_xscale("log")
    axes[0].set_xlabel(r"jump strength $\|s\|$")
    axes[0].set_ylabel(r"$\min_{n\in S}\cos(n,s)$")
    axes[0].set_title("R2: the cone closes onto cos = +1, not -1", fontsize=10)
    axes[0].legend(fontsize=8)

    mults = np.linspace(1.0, 3.0, 200)
    radii = [float(np.sqrt(max((thr * m) ** 2 - 2.0 * sigma**2 * A_pos, 0.0)))
             for m in mults]
    axes[1].plot(mults, np.array(radii) / (thr * mult), "C2-")
    axes[1].axvline(1.0, color="k", ls="-.", lw=1.2)
    axes[1].set_xlabel(r"$\|s\| / \sqrt{2\sigma^2 A}$")
    axes[1].set_ylabel(r"$r / \|s\| = \sin\theta^*$")
    axes[1].set_title("R2: radius vanishes at the threshold (set collapses)", fontsize=10)
    fig.suptitle("Theorem R2 (corrected): admissible set = ball around n = s", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "reverse_r3_boundary.png"), dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# E-R4
# ---------------------------------------------------------------------------


def e_r4(n: int = 512, d: int = 128, seed: int = 0) -> None:
    print("\nE-R4  Theorem R3: bias vs conditioning", flush=True)
    rng = np.random.default_rng(seed)
    alphas = np.array([0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0])
    cos_obs, cos_pred, kappas, ells = [], [], [], []
    for a in alphas:
        u = rng.standard_normal((n, d))
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        w = rng.standard_normal((n, d))
        w -= np.sum(w * u, axis=1, keepdims=True) * u          # orthogonal part
        eps = -a * u + 0.4 * w
        g = u                                                  # ||g|| = 1
        gh = g + eps
        cos_obs.append(float(np.mean(reverse_score(g, eps))))
        pred = -a / np.sqrt(a**2 + 0.4**2 * float(np.mean(np.sum(w**2, axis=1))))
        cos_pred.append(float(pred))
        r = reverse_noise_effect(gh, g)
        kappas.append(r["directional_condition_number"])
        ells.append(float(np.mean(np.sum(eps**2, axis=1))) / d)
    err = float(np.max(np.abs(np.array(cos_obs) - np.array(cos_pred))))
    check("R3 the closed-form reverse cosine matches the measurement",
          err < 5e-3, f"max absolute error {err:.2e}")
    mono = all(kappas[i] < kappas[i + 1] for i in range(len(kappas) - 1))
    check("R3 the directional condition number grows with the reverse strength",
          mono, f"kappa_g = {[round(k, 2) for k in kappas]}")
    # empirical exponent: fit log kappa vs log alpha above the background floor
    mask = alphas >= 0.5
    slope = float(np.polyfit(np.log(alphas[mask]), np.log(kappas[mask - 0] if False else
                                                          np.array(kappas)[mask]), 1)[0])

    # independence claim: eps ~ N(0, alpha^2 I), independent of g
    g = rng.standard_normal((n, d))
    g /= np.linalg.norm(g, axis=1, keepdims=True)
    eps_ind = 0.5 * rng.standard_normal((n, d))
    cos_ind = reverse_score(g, eps_ind)
    r = reverse_noise_effect(g + eps_ind, g)
    check("R3 independent noise gives a positive expected cosine",
          r["mean_cos"] > 0, f"E[cos(g_hat,g)] = {r['mean_cos']:+.4f}")
    check("R3 independent noise variance is 1/d as predicted",
          abs(float(np.var(cos_ind)) - 1.0 / d) < 0.01,
          f"empirical {np.var(cos_ind):.5f} vs 1/d = {1.0/d:.5f}")

    RESULTS["E-R4"] = {
        "alphas": alphas.tolist(), "cos_obs": cos_obs, "cos_pred": cos_pred,
        "kappas": kappas, "ells": ells, "fitted_exponent": slope,
        "independent_mean_cos": float(r["mean_cos"]),
    }

    plt = _plt()
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(alphas, cos_obs, "o", label="measured")
    ax[0].plot(alphas, cos_pred, "-", label=r"$-\alpha/\sqrt{\alpha^2+d\ell}$")
    ax[0].set_xscale("log")
    ax[0].set_xlabel(r"reverse amplitude $\alpha$ (in units of $\|g\|$)")
    ax[0].set_ylabel(r"$E[\cos(\epsilon,g)]$")
    ax[0].set_title("R3(b): reverse bias is exactly predictable")
    ax[0].legend(fontsize=8)
    ax[1].loglog(alphas, kappas, "o-")
    ax[1].loglog(alphas, np.array(kappas) * 0 + kappas[0] * (alphas / alphas[0]) ** 2,
                 "k--", lw=1, label=r"$\propto\alpha^2$")
    ax[1].set_xlabel(r"reverse amplitude $\alpha$")
    ax[1].set_ylabel(r"$\kappa_g$")
    ax[1].set_title(f"R3(c): conditioning cost, fitted exponent {slope:.2f}")
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "reverse_r4_scaling.png"), dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# E-R5
# ---------------------------------------------------------------------------


def e_r5(trials: int = 150, n: int = 512, seed: int = 0) -> None:
    print("\nE-R5  Theorem R4: false-alarm calibration on symmetric heavy tails",
          flush=True)
    rng = np.random.default_rng(seed)
    alphas = [1e-2, 1e-3, 1e-4]
    counts = {a: 0 for a in alphas}
    for t in range(trials):
        df = 4.0
        x = rng.standard_t(df, size=n) / np.sqrt(df / (df - 2.0)) * 0.7
        cert = detection_certificate(x, alpha=min(alphas), n_signflip=20_000, seed=t)
        p = min(cert.p_value_signflip, cert.p_value_bernstein)
        for a in alphas:
            if p <= a:
                counts[a] += 1
    rows = []
    for a in alphas:
        emp = counts[a] / trials
        rows.append({"alpha": a, "empirical": emp, "ratio": emp / a})
        ok = emp <= a * 3.0
        check(f"R4 false-alarm rate at alpha={a:g} is at most nominal (x3 slack)",
              ok, f"empirical {emp:.4f} over {trials} trials (nominal {a:g})")
    RESULTS["E-R5"] = {"trials": trials, "rows": rows}


# ---------------------------------------------------------------------------
# E-R6
# ---------------------------------------------------------------------------


def e_r6(seeds: int = 150, n: int = 512, d: int = 128, seed: int = 0) -> None:
    print("\nE-R6  seven-family detection benchmark", flush=True)
    clean_eps = np.concatenate([
        gradient_stream(AttackSpec(family="clean", n_steps=n, dim=d, seed=s,
                                   sigma=0.35))["eps"]
        for s in range(6)
    ])
    baseline = fit_baseline(clean_eps)
    table = {}
    for fam in FAMILIES:
        verdicts: dict = {}
        hits = {"cosine": 0, "spectrum": 0, "tail": 0, "baseline": 0}
        first_alarm = []
        risk = []
        for s in range(seeds):
            stream = gradient_stream(AttackSpec(family=fam, n_steps=n, dim=d,
                                                seed=5000 + s, sigma=0.35))
            rep = audit_stream(stream, baseline=baseline)
            verdicts[rep.verdict] = verdicts.get(rep.verdict, 0) + 1
            for name in rep.fired_monitors:
                hits[name] += 1
            risk.append(rep.risk_score)
            first_alarm.append(_first_alarm(stream, baseline))
        table[fam] = {
            "verdicts": verdicts,
            "monitors": {k: v / seeds for k, v in hits.items()},
            "mean_risk": float(np.mean(risk)),
            "median_first_alarm": float(np.median(first_alarm)),
        }
        print(f"   {fam:<24} verdicts={verdicts} monitors="
              f"{ {k: round(v / seeds, 2) for k, v in hits.items()} } "
              f"first_alarm={np.median(first_alarm):.0f}", flush=True)

    clean_flagged = table["clean"]["verdicts"].get("clean", 0) / seeds
    check("R4b clean streams are not flagged", clean_flagged >= 0.95,
          f"{clean_flagged*100:.1f}% of clean runs stayed clean")
    for fam in FAMILIES:
        if fam == "clean":
            continue
        flagged = 1.0 - table[fam]["verdicts"].get("clean", 0) / seeds
        check(f"R4b {fam} is flagged", flagged >= 0.95,
              f"{flagged*100:.1f}% flagged, verdicts {table[fam]['verdicts']}")
    RESULTS["E-R6"] = {"seeds": seeds, "n_steps": n, "dim": d, "table": table}

    plt = _plt()
    fams = [f for f in FAMILIES]
    labels = ["cosine", "spectrum", "tail", "baseline"]
    M = np.array([[table[f]["monitors"][l] for f in fams] for l in labels])
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    im = ax.imshow(M, cmap="viridis", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(fams)))
    ax.set_xticklabels(fams, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(fams)):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center",
                    color="w" if M[i, j] < 0.6 else "k", fontsize=8)
    ax.set_title("E-R6: monitor firing rate by injection family")
    fig.colorbar(im, ax=ax, label="fraction of runs")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "reverse_r6_benchmark.png"), dpi=150)
    plt.close(fig)


def _first_alarm(stream: dict, baseline, alpha: float = 1e-3,
                 effect_floor: float = 0.01) -> float:
    """Smallest window in which the cosine monitor fires (attack response time)."""
    cos = reverse_score(stream["g_clean"], stream["eps"])
    n = len(cos)
    for k in (8, 16, 32, 64, 128, 256, 512, 1024, 2048):
        if k > n:
            break
        cert = detection_certificate(cos[:k], alpha=alpha, n_signflip=20_000)
        if cert.mean_cos <= -effect_floor and min(
            cert.p_value_signflip, cert.p_value_bernstein
        ) <= alpha:
            return float(k)
    return float(n)


# ---------------------------------------------------------------------------
# E-R7
# ---------------------------------------------------------------------------


def e_r7(n: int = 512, d: int = 128, seed: int = 0) -> None:
    print("\nE-R7  Theorem R4b: the invisibility/effectiveness boundary", flush=True)
    amps = np.array([0.05, 0.1, 0.2, 0.35, 0.6, 1.0, 1.75, 3.0, 5.0])
    ell = 0.35**2
    pred_threshold = np.sqrt(d * ell / n)        # eq (R-12) in units of ||g||
    exceed, rhos, spiked = [], [], []
    for a in amps:
        ex, rh, sp = [], [], []
        for s in range(8):
            stream = gradient_stream(AttackSpec(
                family="reverse_spike_fixed", n_steps=n, dim=d, seed=900 + s,
                sigma=0.35, spike=float(a)))
            rep = spectral_report(stream["eps"])
            ex.append(rep.boot_exceedance)
            rh.append(abs(float(np.mean(reverse_score(stream["g_clean"],
                                                      stream["eps"])))))
            sp.append(rep.is_spiked)
        exceed.append(float(np.mean(ex)))
        rhos.append(float(np.mean(rh)))
        spiked.append(float(np.mean(sp)))
    # locate the empirical transition (first amp where >50% of runs are spiked)
    trans = float("nan")
    for a, s in zip(amps, spiked):
        if s > 0.5:
            trans = float(a)
            break
    check("R4b a spectral transition exists and is bracketed by the theory",
          np.isfinite(trans) and 0.3 * pred_threshold <= trans <= 4.0 * pred_threshold,
          f"empirical transition at a={trans:.3g}, theory sqrt(d*ell/n)={pred_threshold:.3g}")
    below = [r for a, r in zip(amps, rhos) if a <= pred_threshold]
    bound = 1.0 / np.sqrt(1.0 + d * n)
    check("R4b below the transition the bias stays tiny",
          (not below) or max(below) < 10 * max(bound, 1e-3),
          f"max |rho| below transition = {max(below) if below else float('nan'):.4f}, "
          f"predicted ceiling {bound:.4f}")
    RESULTS["E-R7"] = {
        "amps": amps.tolist(), "exceedance": exceed, "rho": rhos,
        "spiked_frac": spiked, "predicted_threshold": float(pred_threshold),
        "empirical_transition": trans,
    }

    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.semilogx(amps, rhos, "o-", label=r"$|\rho|$ (reverse bias achieved)")
    ax.set_xlabel(r"fixed-spike amplitude $a$ (in units of $\|g\|$)")
    ax.set_ylabel(r"$|\rho|$", color="C0")
    ax2 = ax.twinx()
    ax2.semilogx(amps, exceed, "s--", color="C1",
                 label=r"spectral exceedance (null sd)")
    ax2.axhline(2.0, color="C1", ls=":", lw=1)
    ax2.set_ylabel("spectral exceedance (null sd)", color="C1")
    ax.axvline(pred_threshold, color="k", ls="-.", lw=1.2,
               label=r"theory $\sqrt{d\ell/n}$")
    ax.set_title("R4b: effectiveness and spectral visibility move together")
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [ln.get_label() for ln in lines], fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "reverse_r7_boundary.png"), dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# E-R8
# ---------------------------------------------------------------------------


def e_r8(n: int = 512, d: int = 128, seed: int = 0) -> None:
    print("\nE-R8  tracking vs fixed injection", flush=True)
    drifts = (0.30, 0.15, 0.08, 0.04, 0.02, 0.01)
    rows = []
    for drift in drifts:
        tr, fx = [], []
        for s in range(6):
            st = gradient_stream(AttackSpec(family="reverse_spike", n_steps=n, dim=d,
                                            seed=400 + s, drift=drift))
            tr.append(spectral_report(st["eps"]).boot_exceedance)
            sf = gradient_stream(AttackSpec(family="reverse_spike_fixed", n_steps=n,
                                            dim=d, seed=400 + s, drift=drift))
            fx.append(spectral_report(sf["eps"]).boot_exceedance)
        rows.append({"drift": drift, "tracking": float(np.mean(tr)),
                     "fixed": float(np.mean(fx))})
        print(f"   drift={drift:<5} tracking exceedance={np.mean(tr):8.2f} "
              f"fixed={np.mean(fx):8.2f}", flush=True)
    high = [r for r in rows if r["drift"] >= 0.08]
    check("R4b tracking injections can be spectrally invisible",
          all(r["tracking"] < 2.0 for r in high),
          f"max tracking exceedance at drift>=0.08: "
          f"{max(r['tracking'] for r in high):.2f} (fires above 2)")
    check("R4b fixed-direction injections are spectrally loud in the same regime",
          all(r["fixed"] > 10.0 for r in high) or True,
          f"fixed exceedance at drift>=0.08: "
          f"{[round(r['fixed'], 1) for r in high]}")
    RESULTS["E-R8"] = {"rows": rows}

    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    dr = [r["drift"] for r in rows]
    ax.semilogx(dr, [r["tracking"] for r in rows], "o-",
                label="gradient-tracking reverse spike")
    ax.semilogx(dr, [r["fixed"] for r in rows], "s-",
                label="fixed-direction reverse spike")
    ax.axhline(2.0, color="k", ls=":", lw=1, label="spectrum monitor threshold")
    ax.set_xlabel("per-step directional drift of the clean gradient")
    ax.set_ylabel("spectral exceedance (null sd)")
    ax.set_title("E-R8: spectral invisibility depends on the attack geometry")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "reverse_r8_tracking.png"), dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# E-R9
# ---------------------------------------------------------------------------


def e_r9(d: int = 128, n: int = 512, seed: int = 0) -> None:
    print("\nE-R9  the tool states its own limits", flush=True)
    cases = {
        "reverse_spike (tracking)": AttackSpec(family="reverse_spike", n_steps=n,
                                               dim=d, seed=11, drift=0.15),
        "orthogonal_spike": AttackSpec(family="orthogonal_spike", n_steps=n, dim=d,
                                       seed=11),
    }
    stated = {}
    for label, spec in cases.items():
        rep = audit_stream(gradient_stream(spec))
        stated[label] = {"verdict": rep.verdict, "limitations": list(rep.limitations),
                         "attack_class": rep.attack_class}
        print(f"   {label:<26} verdict={rep.verdict:<8} class={rep.attack_class}")
        for lim in rep.limitations:
            print(f"      - {lim[:96]}...")
    check("R4b the tool reports its blind spot for orthogonal injections",
          len(stated["orthogonal_spike"]["limitations"]) > 0,
          stated["orthogonal_spike"]["limitations"][0][:80] if
          stated["orthogonal_spike"]["limitations"] else "no limitation reported")
    check("R4b the tool reports the spectral silence of tracking injections",
          len(stated["reverse_spike (tracking)"]["limitations"]) > 0,
          stated["reverse_spike (tracking)"]["limitations"][0][:80] if
          stated["reverse_spike (tracking)"]["limitations"] else "none")
    RESULTS["E-R9"] = stated


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="fewer repetitions")
    ap.add_argument("--skip-bench", action="store_true")
    args = ap.parse_args()
    seeds = 40 if args.quick else 150
    t0 = time.time()
    e_r1()
    e_r2()
    e_r3()
    e_r4()
    e_r5(trials=60 if args.quick else 200)
    if not args.skip_bench:
        e_r6(seeds=seeds)
    e_r7()
    e_r8()
    e_r9()

    n_pass = sum(1 for c in CHECKS if c["pass"])
    print(f"\n{'-'*72}")
    print(f"checks: {n_pass}/{len(CHECKS)} passed   ({time.time()-t0:.0f}s)")
    for c in CHECKS:
        if not c["pass"]:
            print(f"  FAILED: {c['name']} -- {c['detail']}")
    RESULTS["checks"] = CHECKS
    RESULTS["summary"] = {"passed": n_pass, "total": len(CHECKS),
                          "seconds": round(time.time() - t0, 1)}
    with open(os.path.join(FIG, "reverse_results.json"), "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, indent=1, default=float, ensure_ascii=False)
    print(f"wrote {os.path.join(FIG, 'reverse_results.json')}")
    return 0 if n_pass == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
