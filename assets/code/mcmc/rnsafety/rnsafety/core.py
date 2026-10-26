"""Reverse-noise safety: the mathematics, as computable primitives.

This module is the engine of `rnsafety`.  Every function below is either

  (a) an **exact algebraic identity** from the reverse-noise theory (so the test
      suite can assert it to machine precision), or
  (b) a **non-asymptotic bound** whose constants are stated in the paper

      ``_mcmc/paper/反向噪声安全工具-定理与可证性.md``

      Theorem R1  gradient-loss identity / reverse score
      Theorem R2  geometric form of the noise-benefit condition
      Theorem R3  collapse theorem (bias-variance of the reverse estimator)
      Theorem R4  detection certificate and the invisibility-vs-depth tradeoff
      Theorem R5  non-existence of a universal singularity (counterexamples)

Nothing here is heuristic: where a threshold is used it is derived from a stated
inequality, and the empirical false-alarm rate is calibrated against it.

--------------------------------------------------------------------------
Notation (identical to the parent paper `论文-2020增补版.md`)
--------------------------------------------------------------------------

Loss      ``L(theta)``, twice differentiable, beta-smooth.
Gradient  ``g = grad L(theta)``                          (the clean direction)
Noise     ``eps``, ``E[eps] = 0``, ``Cov(eps) = Sigma``  (the injected noise)
Observed  ``g_hat = g + eps``                            (what the optimiser uses)

**Reverse noise** (the definition fixed with the user, matching Theorem 3 of the
parent paper -- the reversed noise-inequality / "negative condition"):

    ``rho := E[<eps, g>] / (||g|| E||eps||) < 0``   i.e.   ``E[cos(eps, g)] < 0``

A single step of the contaminated update is ``theta' = theta - eta * g_hat``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

__all__ = [
    "EPS",
    "ReverseNoiseStats",
    "UpdateStats",
    "DetectionCertificate",
    "SpectralReport",
    "cosine",
    "norm",
    "safe_div",
    "reverse_score",
    "update_identity_terms",
    "quadratic_loss_increment",
    "gradient_loss_increment",
    "noise_benefit_increment",
    "effective_condition_number",
    "noise_covariance",
    "direction_condition_number",
    "power_spectrum",
    "robust_noise_scale",
    "describe_reverse_noise",
    "detection_certificate",
    "spectral_report",
    "bernoulli_kl_nats",
    "required_alignment_for_power",
    "reverse_noise_effect",
    "random_matrix_edge",
    "random_matrix_edge_quantile",
    "exchangeable_null_spectrum",
    "bbp_detectable",
    "min_order_statistic_z",
    "set_n_jobs",
]

EPS = 1e-300


# ---------------------------------------------------------------------------
# basic vector helpers
# ---------------------------------------------------------------------------


def norm(x: np.ndarray, axis: Optional[int] = -1) -> np.ndarray:
    """Euclidean norm that returns a python float for 1-D input."""
    return np.linalg.norm(np.asarray(x, dtype=float), axis=axis)  # type: ignore[return-value]


def safe_div(a, b, fill: float = 0.0):
    """Elementwise ``a / b`` with a fill value where ``|b|`` is below 1e-300."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    out = np.full(np.broadcast(a, b).shape, fill, dtype=float)
    np.divide(a, b, out=out, where=np.abs(b) > EPS)
    return out


def cosine(a: np.ndarray, b: np.ndarray, axis: int = -1) -> np.ndarray:
    """cosine similarity, 0.0 wherever either vector is (numerically) zero."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na = np.linalg.norm(a, axis=axis)
    nb = np.linalg.norm(b, axis=axis)
    num = np.sum(a * b, axis=axis)
    return safe_div(num, na * nb, fill=0.0)


# ---------------------------------------------------------------------------
# Theorem R1: the exactly decomposable step statistics
# ---------------------------------------------------------------------------


def reverse_score(reference: np.ndarray, eps: np.ndarray, axis: int = -1) -> np.ndarray:
    """``rho = <eps, reference> / (||reference|| ||eps||)`` -- the reverse score.

    **The reference must be the clean gradient ``g``.**  This is the single most
    common way to get the diagnostic wrong: computing ``cos(g_hat, eps)`` (using
    the contaminated gradient as the reference) produces a number that is
    *positive by construction* -- because ``<g_hat,eps> = <g,eps> + ||eps||^2`` --
    and thereby hides every reverse attack.

    The observable equivalent of the definition is the cosine between the
    contaminated and the clean gradient, ``cos(eps,g) = cos(eps, g_hat)``: both
    are ``<eps,g>`` normalised, and the normalising factors differ.  So a monitor
    that records both ``g`` and ``g_hat`` can compute the score exactly from
    ``eps = g_hat - g``; a monitor that sees only ``g_hat`` cannot, and must fall
    back on a two-sided bound (reported as such in the audit's limitations).
    """
    a = np.asarray(reference, dtype=float)
    b = np.asarray(eps, dtype=float)
    return safe_div(
        np.sum(a * b, axis=axis),
        np.linalg.norm(a, axis=axis) * np.linalg.norm(b, axis=axis),
        fill=0.0,
    )


def update_identity_terms(
    g: np.ndarray, eps: np.ndarray, eta: float = 1.0, axis: int = -1
) -> dict:
    """Theorem R1: exact terms of one contaminated update step.

    For the update ``theta' = theta - eta (g + eps)`` the *quadratic* (small-eta)
    loss increment is exactly

        L(theta') - L(theta) ~= eta [ <eps,g> - ||g||^2 ]
                               + eta^2/2 [ g'Hg + 2 eps'Hg + eps'Heps ]

    Splitting ``eps = delta * u + w`` with ``u = g/||g||`` and ``<w,g> = 0``,
    ``delta = <eps,g>/||g||``, the three terms that decide everything are

        drift      ``<eps, g>      = delta ||g||``      (sign = the whole story)
        variance   ``||eps||^2     = delta^2 + ||w||^2``
        amplified  ``eps'Heps``    = delta^2 u'Hu + 2 delta u'Hw + w'Hw``

    The last one is where the *condition number* enters: when ``delta`` is
    concentrated on a single Hessian eigendirection, ``eps'Heps`` scales with
    that eigenvalue, so the curvature the noise feels is
    ``kappa = lambda_max / lambda_g`` -- not the ambient condition number.

    Returns a dict with ``drift``, ``noise_sq``, ``proj`` (delta), ``orth_sq``
    (||w||^2), ``reverse_score`` and ``norm_ratio`` (||eps||/||g||).
    """
    g = np.asarray(g, dtype=float)
    eps = np.asarray(eps, dtype=float)
    gn = np.linalg.norm(g, axis=axis)
    en = np.linalg.norm(eps, axis=axis)
    drift = np.sum(g * eps, axis=axis)
    proj = safe_div(drift, gn, fill=0.0)
    noise_sq = en**2
    orth_sq = np.maximum(noise_sq - proj**2, 0.0)
    return {
        "drift": drift,
        "noise_sq": noise_sq,
        "proj": proj,
        "orth_sq": orth_sq,
        "reverse_score": safe_div(drift, gn * en, fill=0.0),
        "norm_ratio": safe_div(en, gn, fill=0.0),
        "eta": float(eta),
        "grad_sq": gn**2,
    }


def quadratic_loss_increment(
    g: np.ndarray,
    hess: np.ndarray,
    eps: np.ndarray,
    eta: float,
    axis: int = -1,
) -> np.ndarray:
    """Exact quadratic-model increment for ``theta' = theta - eta (g + eps)``.

    The step is ``-eta g_hat`` with ``g_hat = g + eps``, and the gradient at the
    current point *is* ``g_hat`` (that is what the optimiser saw), so

        ``dL = -eta <g_hat, g_hat> + eta^2/2 g_hat' H g_hat``.

    Pairing the seen gradient with the clean one in the linear term -- the
    ``lin = <step, g>`` variant -- is wrong and was the source of a three-round
    sign hunt in the Theorem R1 identity.  ``hess`` may be a single ``(d, d)``
    matrix or broadcast to ``(n, d, d)``.
    """
    g = np.asarray(g, dtype=float)
    eps = np.asarray(eps, dtype=float)
    step = g + eps
    H = np.asarray(hess, dtype=float)
    quad = np.einsum("...i,...ij,...j->...", step, H, step)
    lin = np.sum(step * step, axis=axis)
    return -eta * lin + 0.5 * eta**2 * quad


def gradient_loss_increment(
    g: np.ndarray, hess: np.ndarray, eta: float, axis: int = -1
) -> np.ndarray:
    """Exact quadratic-model increment of the *clean* gradient step (eps = 0)."""
    zeros = np.zeros_like(np.asarray(g, dtype=float))
    return quadratic_loss_increment(g, hess, zeros, eta, axis=axis)


def noise_benefit_increment(
    g: np.ndarray, hess: np.ndarray, eps: np.ndarray, eta: float, axis: int = -1
) -> np.ndarray:
    """``L_noisy - L_clean`` under the quadratic model -- the harm made explicit.

    With the steps ``-eta g`` (clean) and ``-eta (g+eps)`` (noisy), the quadratic
    model gives, exactly,

        harm = -eta ( 2<eps,g> + ||eps||^2 ) + eta^2 ( eps'Hg + eps'Heps/2 ).

    **The identity is only correct with all four terms.**  Getting it right took
    three attempts, every one of them caught by the verification script E-R1
    (first a missing factor 2 with flipped quadratic signs, then a flipped
    ``||eps||^2`` term).  Read the identity off the implementation, not the prose:
    a least-squares fit of the exact increment on the basis
    ``{eta<eps,g>, eta||eps||^2, eta^2 eps'Hg, eta^2 eps'Heps}`` returns
    ``(-2, -1, +1, +1/2)`` with residual 5e-16.

    In the small-step regime that matters in practice (``eta lambda_max`` not
    large) the first term dominates, ``-2 eta <eps,g>``: a reverse noise with
    ``delta = <eps,g>/||g|| < 0`` makes ``harm`` *positive*, i.e. the contaminated
    step loses ground relative to the clean step.  That is the parameter-space
    image of the parent paper's Theorem 3 (``E_N[d_t(N)] - d_t >= 0`` under the
    reversed inequality), and it is why ``E[cos(eps,g)] < 0`` is the right scalar
    summary.
    """
    g = np.asarray(g, dtype=float)
    eps = np.asarray(eps, dtype=float)
    H = np.asarray(hess, dtype=float)
    coupling = 2.0 * np.sum(eps * g, axis=axis) + np.sum(eps * eps, axis=axis)
    cross = np.einsum("...i,...ij,...j->...", eps, H, g)
    own = np.einsum("...i,...ij,...j->...", eps, H, eps)
    return -eta * coupling + eta**2 * cross + 0.5 * eta**2 * own


# ---------------------------------------------------------------------------
# Theorem R2: the noise-benefit condition in geometric (cosine) form
# ---------------------------------------------------------------------------


def noise_benefit_condition_boundary(
    sigma_q: float, a_value: float, sigma: float = 1.0
) -> dict:
    """Theorem R2: the exact admissible set of the parent paper's condition (2).

    Condition (2) is ``n (n + 2 (x_t - x)) <= -2 sigma^2 A(x_t)``.  With the jump
    ``s := x - x_t`` (so ``x_t - x = -s``) it reads

        ``f(n) = ||n||^2 - 2 <n, s> + 2 sigma^2 A  <=  0``,

    and completing the square gives the whole answer at once:

        ``f(n) = ||n - s||^2 - ||s||^2 + 2 sigma^2 A``.

    **The admissible set is a ball centred at ``n = s`` with radius**

        ``r = sqrt(||s||^2 - 2 sigma^2 A)``.

    That single line replaces three earlier attempts that all reasoned about a
    *direction bound* ``cos(n,s) >= c*`` and concluded that the admissible cone
    points backwards with ``c* -> -1``.  Both halves of that were wrong, and the
    error is worth recording because the wrong answer looks plausible:

    * the cone does **not** point backwards.  ``f(-s) = 3||s||^2 + 2 sigma^2 A``
      is positive whenever the ball exists, so fully-reversed noise never
      satisfies (2).  The admissible noise points *along* the jump.
    * the limit is ``cos -> +1``, not ``-1``: at the threshold the radius vanishes
      and the ball collapses onto the single point ``n = s``, which has
      ``cos(n,s) = +1``.

    This is consistent with the parent paper's own measurement: the accepted
    noise in group E1-D correlates **positively** with the jump (Pearson
    ``r = 0.453``), and ``+1`` is where the theory says the cone closes.

    Three regimes, all exact:

    * ``A <= 0`` -- ``r^2 = ||s||^2 + 2 sigma^2 |A|``, the ball always contains
      ``n = 0``, so (2) is satisfiable for every jump strength (trivially, by no
      noise at all).
    * ``A > 0`` and ``||s||^2 < 2 sigma^2 A`` -- **infeasible**.  No injection of
      any magnitude or direction satisfies the benefit condition.  This is the
      sharp form of "blind noise cannot help here".
    * ``A > 0`` and ``||s||^2 >= 2 sigma^2 A`` -- a non-trivial ball around
      ``n = s``, whose half-angle as seen from the origin is
      ``asin(r / ||s||)`` and shrinks to zero at the threshold.

    Returns a dict with ``M`` (``sqrt(2 sigma^2 |A|)``, the threshold scale),
    ``s_threshold`` (``sqrt(2 sigma^2 A)`` for ``A > 0``, else 0), ``feasible``,
    ``radius``, ``center_norm`` (``||s||``, the ball centre's distance from the
    origin), ``half_angle`` (radians, ``nan`` when infeasible), ``min_cos``
    (``cos`` of the most-backward admissible direction -- **positive** whenever
    the ball exists and ``A > 0``), and ``regime``.

    ``sigma_q`` is the jump norm ``||s||``; the name is kept for backward
    compatibility with the parent paper's notation.
    """
    A = float(a_value)
    s_norm = float(sigma_q)
    sig = float(sigma)
    if s_norm < 0.0 or sig <= 0.0:
        raise ValueError("jump norm must be non-negative and sigma positive")
    s2 = s_norm * s_norm
    two_sigma_A = 2.0 * sig * sig * A
    r2 = s2 - two_sigma_A
    threshold = float(np.sqrt(2.0 * sig * sig * A)) if A > 0.0 else 0.0

    if A > 0.0 and r2 < 0.0:
        return {
            "M": float(np.sqrt(2.0 * sig * sig * A)),
            "s_threshold": threshold,
            "feasible": False,
            "radius": float("nan"),
            "center_norm": s_norm,
            "half_angle": float("nan"),
            "min_cos": float("nan"),
            "mean_intervals": [],
            "min_feasible_mean": float("nan"),
            "max_feasible_mean": float("nan"),
            "envelope_low": float("nan"),
            "envelope_high": float("nan"),
            "c_min_feasible": float("nan"),
            "zero_reachable": False,
            "psi": 1.0,
            "regime": "unsatisfiable",
        }

    r = float(np.sqrt(max(r2, 0.0)))
    feasible = True
    # the ball may or may not contain the origin
    zero_reachable = bool(r >= s_norm)
    if s_norm > 0.0:
        half_angle = float(np.arcsin(min(r / s_norm, 1.0)))
        min_cos = float(np.cos(half_angle))
    else:
        half_angle = float("nan")
        min_cos = float("nan")
    if A > 0.0:
        regime = "cone" if r < s_norm else "free"
    else:
        regime = "always"
    # signed projections <n,s> reachable by the ball: n = s + r u, u on the sphere
    # -> <n,s> = ||s||^2 + r <u,s>, with <u,s> in [-||s||, ||s||]
    lo = s2 - r * s_norm
    hi = s2 + r * s_norm
    return {
        "M": float(np.sqrt(2.0 * sig * sig * abs(A))) if A != 0.0 else 0.0,
        "s_threshold": threshold,
        "feasible": feasible,
        "radius": r,
        "center_norm": s_norm,
        "half_angle": half_angle,
        "min_cos": min_cos,
        "mean_intervals": [[float(lo), float(hi)]],
        "min_feasible_mean": float(lo),
        "max_feasible_mean": float(hi),
        "envelope_low": float(lo),
        "envelope_high": float(hi),
        "c_min_feasible": float(min_cos),
        "zero_reachable": zero_reachable,
        "psi": float(min(1.0, threshold / s_norm)) if s_norm > 0.0 else 1.0,
        "regime": regime,
    }


def noise_covariance(eps: np.ndarray) -> np.ndarray:
    """Unbiased sample covariance of the noise draws, ``(n, d) -> (d, d)``."""
    e = np.asarray(eps, dtype=float)
    if e.ndim != 2:
        raise ValueError("eps must be 2-D (n_steps, dim)")
    n = e.shape[0]
    if n < 2:
        raise ValueError("need at least two noise draws")
    e = e - e.mean(axis=0, keepdims=True)
    return (e.T @ e) / (n - 1)


def direction_condition_number(
    eps: np.ndarray, direction: np.ndarray, ridge: float = 0.0
) -> float:
    """``u' Sigma u / (tr(Sigma)/d)`` -- condition number *seen along* a direction.

    **``direction`` must be a single fixed vector.**  This is the right object for
    the paper's (R-6) applied to a fixed injection axis, or to a stream whose
    reference direction is essentially constant.  For a *rotating* reference (a
    real training run) use :func:`directional_gain` or
    :func:`reverse_noise_effect` instead: feeding per-step directions into this
    estimator silently returns ~1 no matter how strong the injection, because the
    numerator is averaged over steps while the direction is not.

    An isotropic noise has value 1 regardless of ``d``; a low-rank spike aligned
    with ``u`` grows like the spike strength, and an orthogonal spike leaves it at
    1 -- that last case is the hiding place identified in Theorem R5.
    """
    e = np.asarray(eps, dtype=float)
    u = np.asarray(direction, dtype=float).reshape(-1)
    if e.ndim != 2:
        raise ValueError("eps must be 2-D (n_steps, dim)")
    if u.shape[0] != e.shape[1]:
        raise ValueError(f"direction dim {u.shape[0]} != noise dim {e.shape[1]}")
    nu = np.linalg.norm(u)
    if nu <= EPS:
        return float("nan")
    u = u / nu
    d = e.shape[1]
    proj = e @ u
    quad = float(np.mean(proj**2)) + ridge * float(u @ u)
    trace = float(np.sum(e**2)) / e.shape[0] + ridge
    return quad / max(trace / d, EPS)


def directional_gain(eps: np.ndarray, direction: np.ndarray) -> float:
    """Directional second moment over a *moving* reference, energy-normalised.

        ``gain = mean_t <eps_t, u_t>^2 / mean_t ||eps_t||^2``

    Both numerator and denominator are averaged over the same steps, so the ratio
    has a stable limit even when ``u_t`` rotates.  For an isotropic stream
    ``eps ~ N(0, alpha^2 I_d)`` the numerator is ``alpha^2`` and the denominator
    ``d alpha^2``, giving exactly ``1/d`` *independent of* ``alpha`` -- which is
    the numerical content of counterexample R5.1 (no condition-number singularity
    from isotropy, however large or however reversed).  A reverse injection
    aligned with ``u_t`` raises it by the aligned share of the energy.
    """
    e = np.asarray(eps, dtype=float)
    u = np.asarray(direction, dtype=float)
    if e.ndim != 2 or u.ndim != 2 or e.shape != u.shape:
        raise ValueError("eps and direction must both be (n_steps, dim) and match")
    nu = np.linalg.norm(u, axis=1, keepdims=True)
    if np.any(nu <= EPS):
        raise ValueError("direction contains a zero row")
    proj = np.einsum("nd,nd->n", e, u / nu)
    denom = float(np.mean(np.sum(e**2, axis=1)))
    if denom <= EPS:
        return float("nan")
    return float(np.mean(proj**2) / denom)


def power_spectrum(
    eps: np.ndarray, top_k: int = 20, center: bool = False
) -> tuple[np.ndarray, np.ndarray, float]:
    """Leading eigenvalues/eigenvectors of the noise second-moment matrix.

    Returns ``(eigenvalues_desc (k,), eigenvectors (d, k), trace)`` for

        ``center=False`` (default):  ``S = n^{-1} E' E``      (second moment)
        ``center=True``           :  ``Sigma = (n-1)^{-1} E_c' E_c``  (covariance)

    ``trace`` is ``tr(S)`` (or ``tr(Sigma)``), so the mean eigenvalue used by
    every spectral threshold is ``trace / d``.  Keeping this convention is not
    cosmetic: mixing ``tr`` up with the per-coordinate variance, or forgetting
    the ``/d``, shifts the threshold by a factor of ``d`` and turns the monitor
    into either a rubber stamp or a permanent alarm.

    **Why the default is uncentered.**  A constant injected offset -- the
    ``modify_t5``/corrupt-rank signature, and the only *fixed-direction* attack
    an adversary can mount without knowing the gradient -- lives entirely in the
    mean ``E[E]``.  Mean-centering removes it: in the worked example shipped
    with this toolkit the top eigenvalue of a fixed spike of magnitude
    ``2*||g||`` over 512 steps is 4.19 uncentered and **0.27 centered**, i.e.
    centering deletes the attack.  An auditor must therefore test the second
    moment, not the covariance.  The centered spectrum is still computed on
    request because it is the right object when the mean is irrelevant.

    Regime handling (both use the same eigenvalue identity, so the cost is
    ``O(n^2 d)`` in the ``n < d`` regime rather than ``O(d^3)``):

    * ``n >= d``: eigendecompose the ``d x d`` matrix -- all ``d`` eigenvalues
      are finite, ``lambda_min`` is well defined.
    * ``n < d``: eigendecompose the ``n x n`` Gram matrix.  Only ``n``
      eigenvalues are finite; the remaining ``d-n`` are identically zero and are
      **not** information about the noise.  Any ``lambda_min``-based quantity is
      therefore defined on the top-``k`` modes only.
    """
    e = np.asarray(eps, dtype=float)
    if e.ndim != 2:
        raise ValueError("eps must be 2-D (n_steps, dim)")
    n, d = e.shape
    if center:
        ec = e - e.mean(axis=0, keepdims=True)
        denom = max(n - 1, 1)
    else:
        ec = e
        denom = max(n, 1)
    keep = int(min(max(top_k, 1), d))
    if n >= d:
        mat = (ec.T @ ec) / denom
        ev_all, evec_all = np.linalg.eigh(mat)
        order = np.argsort(ev_all)[::-1]
        ev = ev_all[order]
        vecs = evec_all[:, order][:, :keep]
        return ev[:keep], vecs, float(np.sum(ev_all))
    gram = (ec @ ec.T) / denom
    ev_g, evec_g = np.linalg.eigh(gram)
    order = np.argsort(ev_g)[::-1]
    ev_g = ev_g[order]
    evec_g = evec_g[:, order]
    keep_min = int(min(keep, ev_g.size))
    vecs = np.zeros((d, keep_min), dtype=float)
    for j in range(keep_min):
        if ev_g[j] <= EPS:
            continue
        vecs[:, j] = (ec.T @ evec_g[:, j]) / np.sqrt(max(ev_g[j], EPS) * denom)
    total = float(np.sum(ec**2)) / denom
    return ev_g[:keep_min], vecs, total


def effective_condition_number(
    eps: np.ndarray,
    top_k: Optional[int] = None,
    ridge: float = 0.0,
) -> float:
    """Condition number of the noise second moment over its leading modes.

    The naive ``lambda_max / lambda_min`` is **not** an estimator of anything when
    ``n < d``: ``S`` is then singular by construction and the value would report
    the sample size rather than a property of the noise.  This function reports

        ``kappa_k(S) = lambda_1 / lambda_k``,   ``k = min(top_k, d, n)``,

    which is finite, statistically stable, and is the quantity an auditor cares
    about.  ``top_k=None`` uses the largest well-determined ``k``.  ``ridge`` is an
    absolute floor: eigenvalues at or below it are treated as zero, so an exactly
    rank-deficient stream returns ``inf`` (which is itself the loudest possible
    signature) and any subsequent zero modes are ignored rather than dividing by
    nothing.
    """
    e = np.asarray(eps, dtype=float)
    if e.ndim != 2:
        raise ValueError("eps must be 2-D (n_steps, dim)")
    n, d = e.shape
    k = int(min(d, max(n, 1))) if top_k is None else int(top_k)
    # The full spectrum is needed: lambda_k is a *small* eigenvalue, so a top-k
    # slice is not sufficient to evaluate it.  For wide streams the Gram route
    # supplies the finite eigenvalues (n of them) and the remaining d-n are exactly
    # zero, which is what makes an exactly rank-deficient stream report inf.
    ec = e - e.mean(axis=0, keepdims=True)
    if n >= d:
        ev_all = np.linalg.eigvalsh(ec.T @ ec / max(n - 1, 1))[::-1]
    else:
        ev_all = np.linalg.eigvalsh(ec @ ec.T / max(n - 1, 1))[::-1]
        ev_all = np.concatenate([ev_all, np.zeros(d - ev_all.size)])
    if ev_all.size == 0 or float(ev_all[0]) <= 0.0:
        return 0.0
    kept = ev_all[ev_all > ridge] if ridge > 0.0 else ev_all[ev_all > 0.0]
    if kept.size == 0:
        return 0.0
    if k > kept.size:
        return float("inf")             # zero modes inside the requested range
    lmin = float(kept[k - 1])
    if lmin <= 0.0:
        return float("inf")
    return float(ev_all[0] / lmin)


def random_matrix_edge(
    total_variance: float,
    n: int,
    d: int,
    center: bool = False,
    ols_correction: bool = False,
) -> float:
    """Marchenko-Pastur upper edge of the top eigenvalue under coordinate i.i.d. noise.

    For ``M = rank^{-1} X' X`` with i.i.d. entries and mean eigenvalue
    ``ell = tr(M)/d``, the largest eigenvalue concentrates at

        ``lambda_max ~ ell (1 + sqrt(g))^2``,   ``g = min(d, rank)/max(d, rank)``,

    which covers both regimes (``d <= n`` and ``d > n``) without a special case.
    ``total_variance`` here is ``tr(M)``, i.e. ``rank * d * ell``.

    Two corrections, both standard and both material:

    * ``center=True`` for the centred matrix ``(n-1)^{-1} X_c' X_c``: the formula
      is unchanged but ``rank = n - 1`` must be used.  Ignoring this loses power,
      because at ``n = 512``, ``d = 512`` the uncentred edge is 4/3 of the
      centred one.
    * ``ols_correction=True``: the Marchenko-Pastur law describes a *score*
      matrix (rows of identity covariance).  A residual ``X - PX`` from a
      projection is not a score matrix; its top singular value is inflated by
      roughly ``1 / (1 - sqrt(g))``.  This is Johnstone's correction and ignoring
      it makes the edge up to 82% too low in the interesting regime.  It is *off*
      by default because :func:`spectral_report` tests the raw noise stream, which
      is a score matrix, not a regression residual.
    """
    if n <= 1 or d <= 0 or total_variance <= 0:
        return 0.0
    rank = max(n - 1, 1) if center else n
    gamma = min(d, rank) / max(d, rank)
    ell = total_variance / (rank * d)                 # mean eigenvalue of M
    edge = ell * (1.0 + np.sqrt(gamma)) ** 2          # MP upper edge
    if ols_correction:
        denom = 1.0 - np.sqrt(gamma)
        if denom > 0.05:
            edge = edge / denom
    return float(edge)


def _top_eigenvalue_batch(mats: np.ndarray, n_iter: int = 300) -> np.ndarray:
    """Largest eigenvalue of each symmetric matrix in a batch, by power iteration.

    Only the extremal eigenvalue is needed, and ``eigvalsh`` computes the whole
    spectrum: at ``n = d = 512`` that costs ~50 ms per matrix, which makes a
    128-draw null ensemble take 7.6 s.  Power iteration costs ``n_iter`` matrix
    products instead.

    The iteration count is deliberately generous.  The convergence ratio for a
    Wishart matrix is ``((1+sqrt(gamma))/(1-sqrt(gamma)))^4``, which is 0.545 at
    ``gamma = 1`` and 0.478 at ``gamma = 0.25`` and approaches 1 as ``gamma``
    falls; measured against ``eigvalsh`` on 512x512 draws the error is 6% at 20
    iterations, 3% at 40, 1% at 160 and sub-1% at 300.  The statistic they feed
    is then divided into a threshold that itself only need be accurate to a few
    percent, so this is the right trade -- but the count is reported in the
    report's ``notes`` so a reader can raise it if a finding is marginal.
    """
    mats = np.asarray(mats, dtype=float)
    if mats.ndim == 2:
        mats = mats[None, :, :]
    b, m, _ = mats.shape
    rng = np.random.default_rng(12345)               # deterministic start
    v = rng.standard_normal((b, m, 1))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    for _ in range(max(1, int(n_iter))):
        w = mats @ v
        nw = np.linalg.norm(w, axis=1, keepdims=True)
        nw[nw <= EPS] = 1.0
        v = w / nw
    mv = mats @ v
    lam = np.einsum("bi,bi->b", v[:, :, 0], mv[:, :, 0])
    return lam


def random_matrix_edge_quantile(
    ell: float,
    n: int,
    d: int,
    center: bool = False,
    q: float = 0.99,
    n_boot: int = 0,
    seed: int = 0,
    tw_coefficient: float = 1.2,
) -> tuple[float, float]:
    """``q``-quantile of the null ``lambda_max``, in closed form.

    ``ell`` is the **mean eigenvalue** of the matrix under test (see
    :func:`robust_noise_scale`), i.e. ``tr(M)/d``; in the Gaussian model it equals
    the mean-squared entry of the noise matrix.  For i.i.d. entries the top
    eigenvalue of ``M`` concentrates at the Marchenko-Pastur edge

        ``edge = ell (1 + sqrt(gamma))^2``,   ``gamma = d / rank``

    and fluctuates around it on the Tracy-Widom scale

        ``sigma_TW = ell (sqrt(1/gamma) + sqrt(gamma))^{4/3} rank^{-2/3}``.

    **The aspect ratio is ``d/rank``, never ``min(d, rank)/max(d, rank)``.**  This
    is the trap that produced three consecutive wrong thresholds while this module
    was being written.  ``M`` has rank ``rank`` and dimension ``d``, and the edge
    of a Wishart-type matrix is always ``(1 + sqrt(gamma))^2`` with ``gamma`` the
    *dimension-to-sample ratio*.  When ``rank < d`` the matrix is rank-deficient
    and one switches to the equivalent ``rank x rank`` Gram form, which carries
    the **same** edge -- so the formula is unchanged.  Substituting ``min/max``
    understates the edge by up to ``(1+sqrt(d/rank))^2``, a factor of 9 at
    ``d = 4 rank``, and a monitor with a 9x-too-low threshold fires on everything.

    **Why not bootstrap.**  Drawing the ensemble costs ``O(n_boot n_iter d^2)``.
    At ``d = 4096``, ``n = 1024`` that is 428 seconds per audit, which is not an
    audit.  This closed form is ``O(1)``, so the spectrum monitor runs at any
    model width.  ``n_boot > 0`` instead *measures* the ensemble and returns its
    empirical quantile -- useful once, on a small instance, to confirm the
    formula (available through ``null="gaussian_boot"``).
    """
    if n <= 1 or d <= 0 or ell <= 0:
        return 0.0, 0.0
    rank = max(n - 1, 1) if center else n
    g = d / rank
    edge = ell * (1.0 + np.sqrt(g)) ** 2
    sigma = ell * (np.sqrt(1.0 / g) + np.sqrt(g)) ** (4.0 / 3.0) * rank ** (-2.0 / 3.0)
    if n_boot and int(n_boot) > 0:
        floor = _gaussian_null_quantile(
            rank, d, ell, int(n_boot), seed, float(q), center
        )
    else:
        z = _normal_quantile(float(q))
        floor = edge + tw_coefficient * z * sigma
    return float(floor), float(sigma)

def _normal_quantile(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    p = min(max(float(p), 1e-15), 1.0 - 1e-15)
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    df = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
          3.754408661907416e00)
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        qq = np.sqrt(-2.0 * np.log(p))
        return float(((((c[0] * qq + c[1]) * qq + c[2]) * qq + c[3]) * qq + c[4]) * qq
                     + c[5]) / ((((df[0] * qq + df[1]) * qq + df[2]) * qq + df[3]) * qq + 1.0)
    if p > phigh:
        qq = np.sqrt(-2.0 * np.log(1.0 - p))
        return -float(((((c[0] * qq + c[1]) * qq + c[2]) * qq + c[3]) * qq + c[4]) * qq
                      + c[5]) / ((((df[0] * qq + df[1]) * qq + df[2]) * qq + df[3]) * qq + 1.0)
    qq = p - 0.5
    r = qq * qq
    return float(((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * qq \
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)


def _gaussian_null_quantile(
    rank: int, d: int, ell: float, n_boot: int, seed: int, q: float, center: bool
) -> float:
    """Measured ``q``-quantile of the Gaussian null ensemble (small instances only)."""
    rng = np.random.default_rng(seed)
    use_gram = rank > d
    # Target: the eigenvalues of M = rank^{-1} X'X, whose mean is ell = tr(M)/d.
    #   rank > d : use the d x d form G'G/d, whose eigenvalues are (d/rank) * eig(M)
    #              -> rescale by d/rank, giving the edge ell (1 + sqrt(d/rank))^2
    #   rank <= d: use the rank x rank Gram form GG'/rank, one of whose
    #              eigenvalues is already lambda_max(M) and the rest are 0
    #              -> no rescaling
    # Getting this backwards inflates the threshold by (d/rank)^2 -- a factor of
    # 256 at d = 4n -- and the monitor silently stops seeing anything.
    scale = (d / rank) if use_gram else 1.0
    sd = np.sqrt(max(ell, 0.0))
    batch_cap = max(1, int(2.0e7 // max(rank * d, 1)))
    tops = np.empty(n_boot)
    pos = 0
    while pos < n_boot:
        b = int(min(max(batch_cap, 1), n_boot - pos))
        x = sd * rng.standard_normal((b, rank, d))
        if center:
            x = x - x.mean(axis=2, keepdims=True)
        if use_gram:
            mats = np.einsum("brd,bre->bde", x, x) / d
        else:
            mats = np.einsum("brd,bsd->brs", x, x) / rank
        tops[pos:pos + b] = _top_eigenvalue_batch(mats) * scale
        pos += b
    return float(np.quantile(tops, q))


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class ReverseNoiseStats:
    """Theorem R1 summary over a stream of noisy gradient observations."""

    n_steps: int
    dim: int
    mean_cos: float
    median_cos: float
    std_cos: float
    min_cos: float
    max_cos: float
    frac_negative: float
    mean_norm_ratio: float
    median_norm_ratio: float
    mean_cos_neg_part: float
    has_clean: bool = False
    mean_reverse_score: Optional[float] = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class UpdateStats:
    """Aggregate of the exact per-step harm decomposition."""

    mean_drift: float
    mean_noise_sq: float
    mean_proj_sq: float
    mean_orth_sq: float
    mean_norm_ratio: float
    mean_reverse_score: float
    frac_harmful: float
    mean_harm: Optional[float] = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class DetectionCertificate:
    """Theorem R4: a one-sided test for reverse noise with a valid bound.

    Under the null ``H0: E[cos] >= 0`` (no reverse bias) the reported
    ``p_value_bernstein`` satisfies ``P(p <= alpha) <= alpha`` up to the stated
    data-dependent range proxy; ``p_value_signflip`` is an exact Monte-Carlo
    sign-flip permutation test and needs no range proxy at all.
    """

    n_steps: int
    mean_cos: float
    std_cos: float
    se: float
    ci_low: float
    ci_high: float
    t_statistic: float
    p_value_bernstein: float
    p_value_signflip: float
    alpha: float
    reject_h0: bool
    range_proxy: float
    notes: str = ""

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class SpectralReport:
    """Spiked-covariance report: the detector that Theorem R4 pairs with the
    cosine test, and by Theorem R4b the only one that can see an *orthogonal*
    injection."""

    n_steps: int
    dim: int
    effective_condition_number: float
    top_eigenvalue: float
    tail_eigenvalue: float
    total_variance: float
    spike_fraction: float
    spike_direction_energy: float
    spike_cos_with_gradient: Optional[float]
    random_matrix_upper_edge: float
    is_spiked: bool
    boot_floor: float = float("nan")
    boot_sd: float = float("nan")
    boot_exceedance: float = 0.0
    spike_energy: float = 0.0
    centered: bool = False
    null_kind: str = "rotation"
    statistic: float = float("nan")
    null_mean_eigenvalue: float = float("nan")
    notes: str = ""

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ---------------------------------------------------------------------------
# Theorem R3/R5: attack concentration, visibility budget, KL of a coin
# ---------------------------------------------------------------------------


def robust_noise_scale(eps: np.ndarray, center: bool = False) -> float:
    """Mean eigenvalue ``ell`` of the noise second moment, robustly estimated.

    ``ell`` is the quantity every spectral threshold is stated in, and mixing it
    up with the *per-coordinate variance* is the single easiest way to get a
    spectrum monitor that never fires.  For ``S = n^{-1} E'E``,

        ``ell = tr(S) / d = (1/(n d)) sum E^2``   (uncentred)
        ``ell = tr(Sigma) / d = (1/((n-1) d)) sum E_c^2``   (centred)

    which is the same as the mean-squared entry of ``E``.

    The mean of ``tr`` over coordinates is inflated by *any* structure, including
    the very spike being tested for, so the estimate used for the threshold is
    the **median** coordinate's contribution: immune to a minority of
    contaminated coordinates, which is what makes the resulting test honest
    rather than self-defeating.
    """
    e = np.asarray(eps, dtype=float)
    if e.ndim != 2:
        raise ValueError("eps must be 2-D (n_steps, dim)")
    n, d = e.shape
    if center:
        e = e - e.mean(axis=0, keepdims=True)
        denom = max(n - 1, 1)
    else:
        denom = max(n, 1)
    per_coord = np.sum(e**2, axis=0) / denom          # per-coordinate second moment
    return float(np.median(per_coord))


def exchangeable_null_spectrum(
    eps: np.ndarray,
    n_draw: int = 128,
    center: bool = True,
    seed: int = 0,
    q: float = 0.99,
    n_jobs: Optional[int] = None,
    mode: str = "rotate",
    block: int = 4,
) -> tuple[float, float, float]:
    """Null distribution of ``lambda_max`` under **norm-preserving isotropisation**.

    A spike is a deviation from "coordinates are exchangeable and independent".
    The natural null therefore rotates each row by an independent Haar-random
    orthogonal matrix: a rotation preserves the row norm exactly and maps a fixed
    spiked direction to a uniformly random one, so it removes exactly the
    alignment a spike lives on while keeping every row's scale and any temporal
    dependence between rows.  Nothing is assumed about the marginal law.

    **Why the rotation must be *per row*.**
    Rotating every row by the *same* orthogonal ``Q`` does nothing at all:
    ``(EQ)(EQ)' = EQQ'E' = EE'``, so the spectrum is invariant.  The first
    implementation made exactly this mistake and produced ``q99`` identically
    equal to ``lambda_max`` with zero null spread -- a "test" that could never
    fire.  Independence across rows is what breaks the alignment, and it requires
    one ``d x d`` orthogonal factor **per row** (``n`` QR decompositions per draw,
    ``O(n d^3)``).

    **Cost, and the cheap alternative.**  At ``n = 512``, ``d = 128`` the rotation
    null costs roughly 0.05 s per draw, so the default 128 draws take ~6 s; at
    ``d = 512`` it is ~130x more and stops being practical.  For large ``d`` use
    ``mode="permute"``: permuting coordinates *within disjoint blocks* of size
    ``block`` also destroys long-range alignment at ``O(n d)`` per draw.  It has
    strictly less power against a spike confined to a single block, which is the
    documented price.

    **Why not resample coordinates with replacement.**  Also tried, also wrong:
    drawing ``d`` coordinates *with replacement* makes them dependent on each
    other (they share a pool), manufacturing spurious low-rank structure and
    *raising* the null.  Measured on an exactly isotropic ``512 x 128`` Gaussian
    matrix with per-coordinate variance 0.25, that null gave ``p99 = 0.688``
    against a true ``lambda_max`` of 0.540 and an asymptotic edge of 0.563 -- a
    22% inflated threshold that quietly destroys power against the very attacks
    this toolkit exists to find.

    Returns ``(floor, sd, ell_null)``: the ``q`` quantile of the null
    ``lambda_max``, its standard deviation, and the null's mean eigenvalue.
    """
    e = np.asarray(eps, dtype=float)
    if e.ndim != 2:
        raise ValueError("eps must be 2-D (n_steps, dim)")
    if not center:
        raise ValueError(
            "the isotropisation null requires centered data: it cancels a constant "
            "common offset, which would make the threshold meaningless. Use "
            "null='gaussian' for the uncentered second moment."
        )
    n, d = e.shape
    e = e - e.mean(axis=0, keepdims=True)
    denom = max(n - 1, 1)
    n_draw = max(8, int(n_draw))
    if mode not in ("rotate", "permute"):
        raise ValueError("mode must be 'rotate' or 'permute'")
    ell = float(np.sum(e**2) / denom / max(d, 1))
    n_jobs = _resolve_jobs(n_jobs, n_draw, d)
    if n_jobs <= 1:
        tops = _isotropise_null_batch(e, denom, n_draw, seed, mode, block)
    else:
        import concurrent.futures as cf

        per = max(8, int(np.ceil(n_draw / n_jobs)))
        chunks, left, s = [], n_draw, int(seed)
        while left > 0:
            k = int(min(per, left))
            chunks.append((e, denom, k, s, mode, block))
            left -= k
            s += 1
        with cf.ProcessPoolExecutor(max_workers=n_jobs) as ex:
            parts = list(ex.map(_isotropise_null_chunk, chunks))
        tops = np.concatenate(parts)
    return float(np.quantile(tops, q)), float(np.std(tops, ddof=1)), ell


def _isotropise_null_batch(
    e: np.ndarray,
    denom: int,
    n_draw: int,
    seed: int,
    mode: str = "rotate",
    block: int = 4,
) -> np.ndarray:
    """Independent per-row isotropisation, then the top eigenvalue of each draw."""
    n, d = e.shape
    rng = np.random.default_rng(seed)
    tops = np.empty(int(n_draw))
    if mode == "permute":
        # within-block permutation: O(n d) per draw, destroys any alignment that
        # spans more than `block` coordinates
        nb = max(1, d // max(int(block), 1))
        cols = (np.arange(nb * max(int(block), 1))).reshape(nb, max(int(block), 1))
        pos = 0
        while pos < int(n_draw):
            b = int(min(max(1, int(5.0e7 // max(n * d, 1))), int(n_draw) - pos))
            perm = np.argsort(rng.random((b, nb, cols.shape[1])), axis=2)
            idx = np.take_along_axis(np.broadcast_to(cols, (b, nb, cols.shape[1])),
                                     perm, axis=2).reshape(b, -1)
            draw = np.take_along_axis(e[None, :, :], idx[:, None, :], axis=2)
            if n <= d:
                g = np.einsum("bnd,bmd->bnm", draw, draw) / denom
            else:
                g = np.einsum("bnd,bne->bde", draw, draw) / denom
            tops[pos:pos + b] = np.linalg.eigvalsh(g)[:, -1]
            pos += b
        return tops
    # full per-row rotation: one d x d Haar factor per row, O(n d^3) per draw
    batch_cap = max(1, int(4.0e7 // max(n * d * 8, 1)))
    pos = 0
    while pos < int(n_draw):
        b = int(min(max(batch_cap, 1), int(n_draw) - pos))
        z = rng.standard_normal((b, n, d, d))
        q, r = np.linalg.qr(z)
        sgn = np.sign(np.diagonal(r, axis1=2, axis2=3))
        sgn[sgn == 0] = 1.0
        q = q * sgn[:, :, None, :]
        # rot[b, i] = Q_{b,i} e_i : independent rotation per row, row norms exact
        rot = np.einsum("bnij,nj->bni", q, e)
        if n <= d:
            g = np.einsum("bnd,bmd->bnm", rot, rot) / denom
        else:
            g = np.einsum("bnd,bne->bde", rot, rot) / denom
        tops[pos:pos + b] = np.linalg.eigvalsh(g)[:, -1]
        pos += b
    return tops


def _isotropise_null_chunk(args):
    """Worker for the isotropisation null (module level: picklable)."""
    e, denom, n_draw, seed, mode, block = args
    return _isotropise_null_batch(e, denom, n_draw, seed, mode, block)


_N_JOBS_OVERRIDE: Optional[int] = None


def set_n_jobs(n: Optional[int]) -> None:
    """Globally fix the bootstrap worker count (``None`` restores auto-detection).

    Parallelism is auto-disabled when calls come from inside a worker process,
    which keeps nested parfor from oversubscribing the machine.  On Windows the
    entry point of a script that audits streams must still be guarded with
    ``if __name__ == "__main__":``, exactly like any other multiprocessing code.
    """
    global _N_JOBS_OVERRIDE
    _N_JOBS_OVERRIDE = None if n is None else max(1, int(n))


def _resolve_jobs(n_jobs: Optional[int], n_boot: int, d: int) -> int:
    """Pick a worker count: parallel only pays when the matrix work is large."""
    import multiprocessing as mp
    import os

    if mp.current_process().name != "MainProcess":
        return 1
    if n_jobs is not None:
        return max(1, int(n_jobs))
    if _N_JOBS_OVERRIDE is not None:
        return _N_JOBS_OVERRIDE
    env = os.environ.get("RNSAFETY_JOBS")
    if env is not None:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    cpus = os.cpu_count() or 1
    if n_boot < 40 or d < 32 or cpus < 2:
        return 1
    return max(1, min(max(cpus // 2, 2), 8, n_boot // 8))


def bbp_detectable(lambda_max: float, null_floor: float, safety: float = 1.0) -> bool:
    """Is the observed top eigenvalue beyond what exchangeable noise explains?

    ``null_floor`` is the 99% quantile of the null ``lambda_max``, obtained in
    closed form from :func:`random_matrix_edge_quantile`.  The decision is

        ``lambda_max / null_floor > safety``

    i.e. "the top mode carries more energy than the largest mode pure exchangeable
    noise produces at the 99% quantile".  A threshold *above* the null quantile is
    required rather than a bare "past the Marchenko-Pastur edge" test, because at
    realistic ``n`` the top eigenvalue of *any* matrix sits near its own edge and
    an edge comparison has almost no power.

    The corresponding **effect size** is the spike energy per coordinate,
    ``(lambda_max - null_floor) / d``, directly comparable to the per-coordinate
    noise level; that is the BBP scale, and the audit uses it to decide whether a
    statistically visible spike is *practically* visible.

    Why a fixed injected offset is hard to see in a short window: with ``d``
    coordinates and a spike of magnitude ``a ||g||`` the spiked eigenvalue is
    ``a^2 ||g||^2 / d`` while the null quantile is of order
    ``ell (1 + sqrt(d/n))^2``, so the ratio *decreases* with dimension and grows
    only linearly in the window length.
    """
    if not np.isfinite(null_floor) or null_floor <= EPS:
        return False
    return bool(lambda_max / null_floor > safety)


def min_order_statistic_z(x: np.ndarray) -> tuple[float, float, float]:
    """One-sided test on the *minimum* of a sample -- the rare-event detector.

    A probabilistic attack (fire once in ``1/p`` steps) cannot be seen by a mean
    test inside a realistic window, but it makes the sample minimum anomalously
    extreme.  Under the null that ``x`` is approximately Gaussian at the sample's
    own scale, the minimum of ``n`` draws concentrates at
    ``mu - sigma sqrt(2 ln n)`` with standard deviation ``sigma / sqrt(2 ln n)``,
    so

        z = (min(x) - (mu - sigma sqrt(2 ln n))) / (sigma / sqrt(2 ln n))

    measures how extreme the single most extreme observation is, in standard
    errors.  The construction is deliberately *robust* -- ``mu`` and ``sigma``
    come from median absolute deviation -- because otherwise one outlier could
    inflate them enough to hide itself, which is exactly the failure mode of a
    mean-based test.

    Returns ``(z, observed_min, null_min_location)``.
    """
    v = np.asarray(x, dtype=float)
    v = v[np.isfinite(v)]
    n = v.size
    if n < 8:
        return (float("nan"), float("nan"), float("nan"))
    mu = float(np.median(v))
    sd = float(np.median(np.abs(v - mu)) * 1.4826)
    if sd <= EPS:
        sd = float(np.std(v, ddof=1))
    if sd <= EPS:
        return (float("nan"), float(np.min(v)), mu)
    loc = mu - sd * np.sqrt(2.0 * np.log(n))
    scale = sd / np.sqrt(2.0 * np.log(n))
    return (float((float(np.min(v)) - loc) / scale), float(np.min(v)), float(loc))


def bernoulli_kl_nats(p: float, q: float) -> float:
    """``KL(Bern(p) || Bern(q))`` in nats; inf when ``q`` is a boundary and p is not."""
    p = float(min(max(p, 0.0), 1.0))
    q = float(min(max(q, 0.0), 1.0))
    out = 0.0
    for pi_, qi in ((p, q), (1.0 - p, 1.0 - q)):
        if pi_ <= 0.0:
            continue
        if qi <= 0.0:
            return float("inf")
        out += pi_ * np.log(pi_ / qi)
    return float(out)


def reverse_noise_effect(
    grad_hat: np.ndarray,
    grad_clean: np.ndarray,
    hessian: Optional[np.ndarray] = None,
    eta: float = 1.0,
) -> dict:
    """Theorem R3 in executable form: the reverse-noise bias-variance identity.

    Decompose ``eps = g_hat - g`` into the part along the gradient and the part
    orthogonal to it.  Then, *exactly*, for the quadratic model and the update
    ``theta' = theta - eta (g + eps)``:

        harm = L_noisy - L_clean
             = eta <eps,g> - eta^2/2 (2 eps'Hg + eps'Heps          )

    and with ``delta = <eps,g>/||g||`` (signed, negative under reverse noise):

        ``<eps,g>       = delta ||g||``                (first-order drift; < 0)
        ``||eps||^2     = delta^2 + ||w||^2``          (w orthogonal to g)
        ``eps'Heps``    = delta^2 u'Hu + 2 delta u'Hw + w'Hw``

    The three consequences that make reverse noise detectable:

    1. **Bias not variance.**  A reverse component with ``|delta|`` of order
       ``||g||`` shifts the descent direction by ``O(1)``; an isotropic noise of
       the same norm shifts only its length.
    2. **Conditioning.**  Contracting the noise covariance with ``g`` gives
       ``u'Sigma u = delta^2 + E[w_u^2]``, whose leading term grows like
       ``delta^2``.  That is the exact sense in which reverse noise *creates* a
       condition-number singularity, and the scaling is ``delta^{-2}``: to buy a
       relative bias reduction ``delta`` an attacker must accept a directional
       condition number that grows like ``delta^{-2}``.
    3. **Cheapness of the benign case.**  When ``delta >= 0`` the drift term is
       non-negative, so no first-order harm is possible regardless of how large
       ``||eps||`` becomes -- which is why "energy" alone is not a security
       signal and the cosine is.

    Returns a dict with the aggregate quantities the audit report quotes.
    """
    g = np.asarray(grad_clean, dtype=float)
    eps = np.asarray(grad_hat, dtype=float) - g
    if g.shape != eps.shape:
        raise ValueError("grad_hat and grad_clean must have the same shape")
    gn = np.linalg.norm(g, axis=1)
    proj = np.sum(eps * g, axis=1) / np.maximum(gn, EPS)          # delta
    orth_sq = np.maximum(np.sum(eps**2, axis=1) - proj**2, 0.0)
    u = g / np.maximum(gn, EPS)[:, None]
    sigma_g = np.mean(proj**2) + np.mean(orth_sq) / max(g.shape[1], 1)
    ell = float(np.mean(np.sum(eps**2, axis=1))) / max(g.shape[1], 1)
    out = {
        "mean_delta": float(np.mean(proj)),
        "mean_delta_sq": float(np.mean(proj**2)),
        "mean_orth_sq": float(np.mean(orth_sq)),
        "mean_cos": float(np.mean(proj / np.maximum(np.linalg.norm(eps, axis=1), EPS))),
        "directional_condition_number": float(sigma_g / max(ell, EPS)),
        "mean_grad_norm": float(np.mean(gn)),
        "n_steps": int(g.shape[0]),
        "dim": int(g.shape[1]),
    }
    if hessian is not None:
        harm = noise_benefit_increment(g, hessian, eps, eta=eta)
        out["mean_harm"] = float(np.mean(harm))
        out["frac_harmful"] = float(np.mean(harm > 0))
    return out


def required_alignment_for_power(
    sigma: float, n: int, alpha: float = 1e-3, power: float = 0.9
) -> float:
    """Theorem R4 sensitivity limit: the smallest ``|rho|`` this window can detect.

    From the one-sided test of ``H0: E[cos] >= 0`` at level ``alpha`` and power
    ``1 - beta``, the minimum detectable bias is

        ``rho_min = (z_{1-alpha} + z_{power}) sigma / sqrt(n)``

    with ``sigma`` the standard deviation of the per-step cosine.  Taking the
    independent-noise value ``sigma^2 ~ 1/d`` gives
    ``rho_min ~ (z_a + z_b) / sqrt(n d)``: **the detection floor shrinks like
    ``1/sqrt(n d)``**, which is the same scale that Theorem R4b shows bounds the
    usefulness of an invisible attack.  Reporting this number is what keeps the
    effect-size floor in the audit honest -- a bias below it is neither detectable
    nor worth detecting.

    Returns ``nan`` when ``sigma`` or ``n`` are degenerate.
    """
    if n <= 0 or not np.isfinite(sigma) or sigma <= 0:
        return float("nan")
    from math import sqrt

    try:
        from statistics import NormalDist

        z_a = NormalDist().inv_cdf(1.0 - alpha)
        z_b = NormalDist().inv_cdf(power)
    except Exception:  # pragma: no cover - very old python
        z_a, z_b = 3.0902, 1.2816
    return float((z_a + z_b) * sigma / sqrt(n))


# ---------------------------------------------------------------------------
# Top-level entry points used by the audit tool
# ---------------------------------------------------------------------------


def _block_bootstrap_ci(
    x: np.ndarray, alpha: float = 0.05, n_boot: int = 2000, block: Optional[int] = None,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile CI for the mean of a *dependent* series (stationary bootstrap).

    Reverse-noise attacks can be temporally clustered (a compromised rank fires
    intermittently), so an i.i.d. CI would be anti-conservative.  A moving-block
    bootstrap with block length ``ceil(n^{1/3})`` keeps the CI honest under
    short-range dependence.
    """
    x = np.asarray(x, dtype=float).ravel()
    n = x.size
    if n == 0:
        return (float("nan"), float("nan"))
    if block is None:
        block = max(1, int(round(n ** (1.0 / 3.0))))
    block = max(1, min(block, n))
    n_blocks = int(np.ceil(n / block))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    samples = x[idx.reshape(n_boot, -1)[:, :n]].mean(axis=1)
    lo = float(np.quantile(samples, alpha / 2.0))
    hi = float(np.quantile(samples, 1.0 - alpha / 2.0))
    return lo, hi


def describe_reverse_noise(
    grad_hat: np.ndarray,
    grad_clean: Optional[np.ndarray] = None,
    eps: Optional[np.ndarray] = None,
) -> ReverseNoiseStats:
    """Summarise ``cos(noise, gradient)`` over a stream of steps.

    Provide **either** ``eps`` (noise vectors, if the pipeline can isolate them)
    **or** ``grad_clean`` (in which case ``eps = grad_hat - grad_clean``).
    """
    g_hat = np.asarray(grad_hat, dtype=float)
    if g_hat.ndim != 2:
        raise ValueError("grad_hat must be 2-D (n_steps, dim)")
    if eps is None:
        if grad_clean is None:
            raise ValueError("provide eps or grad_clean")
        eps = g_hat - np.asarray(grad_clean, dtype=float)
    eps = np.asarray(eps, dtype=float)
    if eps.shape != g_hat.shape:
        raise ValueError(f"eps shape {eps.shape} != grad_hat shape {g_hat.shape}")
    rho = reverse_score(g_hat, eps)
    nr = safe_div(np.linalg.norm(eps, axis=1), np.linalg.norm(g_hat, axis=1), fill=np.inf)
    return ReverseNoiseStats(
        n_steps=int(g_hat.shape[0]),
        dim=int(g_hat.shape[1]),
        mean_cos=float(np.mean(rho)),
        median_cos=float(np.median(rho)),
        std_cos=float(np.std(rho, ddof=1)) if rho.size > 1 else 0.0,
        min_cos=float(np.min(rho)),
        max_cos=float(np.max(rho)),
        frac_negative=float(np.mean(rho < 0)),
        mean_norm_ratio=float(np.mean(nr[np.isfinite(nr)])) if np.any(np.isfinite(nr)) else float("inf"),
        median_norm_ratio=float(np.median(nr[np.isfinite(nr)])) if np.any(np.isfinite(nr)) else float("inf"),
        mean_cos_neg_part=float(np.mean(np.minimum(rho, 0.0))),
        has_clean=grad_clean is not None,
        mean_reverse_score=float(np.mean(rho)),
    )


def detection_certificate(
    cos_values: Sequence[float],
    alpha: float = 1e-3,
    n_signflip: int = 20_000,
    seed: int = 0,
    ci_seed: int = 0,
) -> DetectionCertificate:
    """Theorem R4 in executable form: one-sided test of ``H0: E[cos] >= 0``.

    Two p-values are returned deliberately:

    * ``p_value_signflip`` -- exact under the symmetry ``cos -> -cos``, which
      holds for any *sign-symmetric* noise law; assumption-light, preferred.
    * ``p_value_bernstein`` -- non-asymptotic one-sided bound using the
      empirical variance as a proxy and the empirical range as a bound; valid
      regardless of the noise law's shape, but conservative.
    """
    from math import exp, sqrt

    x = np.asarray(cos_values, dtype=float).ravel()
    x = x[np.isfinite(x)]
    n = x.size
    if n == 0:
        return DetectionCertificate(0, float("nan"), float("nan"), float("nan"),
                                   float("nan"), float("nan"), float("nan"),
                                   1.0, 1.0, alpha, False, float("nan"),
                                   "empty sample")
    mean = float(np.mean(x))
    var = float(np.var(x, ddof=1)) if n > 1 else 0.0
    sd = sqrt(max(var, 0.0))
    se = sd / sqrt(n) if n > 0 else float("nan")
    lo, hi = _block_bootstrap_ci(x, alpha=alpha, seed=ci_seed)
    t = mean / se if se and np.isfinite(se) and se > EPS else (np.inf if mean > 0 else -np.inf)
    # Bernstein: for X_i in [a, b],  P(mean - EX >= t) <= exp(-n t^2 / (2(var + t R/3)))
    rng_proxy = float(np.max(x) - np.min(x))
    if sd <= 0.0:
        p_bern = 0.0 if mean < 0 else 1.0
    else:
        t_obs = -mean  # we test the violation mean < 0
        if t_obs <= 0:
            p_bern = 1.0
        else:
            denom = 2.0 * (var + t_obs * rng_proxy / 3.0)
            p_bern = float(min(1.0, exp(-n * t_obs**2 / max(denom, EPS))))
    # exact sign-flip permutation (Monte-Carlo): uniform over the 2^n sign
    # patterns, each giving a null draw of the mean under symmetry of the law
    rng = np.random.default_rng(seed)
    if n_signflip > 0 and n > 0:
        total = int(n_signflip)
        below = 0
        chunk = max(1, int(2.0e6 // max(n, 1)))
        done = 0
        for s in range(0, total, chunk):
            m = min(chunk, total - s)
            signs = rng.integers(0, 2, size=(m, n), dtype=np.int8)
            signs *= 2
            signs -= 1
            means = signs @ x / n
            below += int(np.count_nonzero(means <= mean))
            done += m
        p_perm = (below + 1.0) / (done + 1.0)
    else:
        p_perm = 1.0
    return DetectionCertificate(
        n_steps=int(n),
        mean_cos=mean,
        std_cos=sd,
        se=float(se),
        ci_low=float(lo),
        ci_high=float(hi),
        t_statistic=float(t),
        p_value_bernstein=float(p_bern),
        p_value_signflip=float(p_perm),
        alpha=float(alpha),
        reject_h0=bool(min(p_bern, p_perm) <= alpha),
        range_proxy=rng_proxy,
    )


def spectral_report(
    eps: np.ndarray,
    gradient_direction: Optional[np.ndarray] = None,
    top_k: int = 5,
    calibrate: bool = True,
    n_boot: int = 200,
    boot_seed: int = 0,
    center: bool = False,
    safety: float = 1.0,
    null: str = "auto",
    n_draw: int = 128,
    n_jobs: Optional[int] = None,
) -> SpectralReport:
    """Spiked-structure report against a *principled* null.

    ``center=False`` (default) tests the **second moment** ``n^{-1} E'E``, which
    is the only object that sees a constant injected offset (``modify_t5`` and
    corrupt-rank signatures both live in ``mean(E)``); ``center=True`` tests the
    covariance and is blind to it.  See :func:`power_spectrum`.

    ``null`` selects the reference ensemble:

    * ``"gaussian"`` (default): a Gaussian ensemble at the robust
      median-coordinate noise scale -- the classical spiked-covariance model.
      Closed-form fast, valid for both the centred and the uncentred matrix, and
      exactly the right model when the injected noise is Gaussian.
    * ``"rotate"``: assumption-free per-row Haar rotation
      (:func:`exchangeable_null_spectrum`).  Costs ``O(n d^3)`` per draw, so it is
      practical for ``d`` up to a few hundred only; use it as a robustness check
      on a suspected finding.
    * ``"permute"``: within-block coordinate permutation, ``O(n d)`` per draw.
      Nearly free at any dimension, but blind to a spike confined to one block.

    The decision is ``lambda_max > safety * q_99(null)``; the effect size is
    reported as ``spike_energy = (lambda_max - floor) / d`` -- the spike's energy
    per coordinate, directly comparable to the per-coordinate noise variance.
    Both matter: statistical visibility and practical importance are not the same
    thing in a short window.

    ``random_matrix_upper_edge`` (the asymptotic MP edge) is reported for
    reference but is deliberately **not** the decision rule: at realistic ``n``
    the top eigenvalue of any matrix sits near that edge, so an edge comparison
    has almost no power.
    """
    e = np.asarray(eps, dtype=float)
    if e.ndim != 2:
        raise ValueError("eps must be 2-D (n_steps, dim)")
    n, d = e.shape
    if null == "auto":
        null = "gaussian"
    want = int(min(max(top_k, 2), max(d, 2)))
    ev, vecs, total = power_spectrum(e, top_k=want, center=center)
    lmax = float(ev[0]) if ev.size else 0.0
    tail = float(ev[1]) if ev.size > 1 else 0.0
    # ------------------------------------------------------------------
    # ONE estimate of the mean eigenvalue, used by every threshold below.
    #   ell_obs   = tr(S)/d                     -- the observed scale
    #   ell_robust= median coordinate scale     -- the spike-proof scale
    # Everything spectral is expressed as a multiple of a mean eigenvalue, so
    # there is exactly one place where units can go wrong.
    # ------------------------------------------------------------------
    ell_obs = float(total) / max(d, 1)
    ell_robust = robust_noise_scale(e, center=center)
    edge = ell_obs * (1.0 + np.sqrt(min(d, max(n, 1)) / max(d, max(n, 1)))) ** 2
    spike_frac = lmax / total if total > 0 else 0.0
    k = int(min(d, max(n, 1)))
    cond = effective_condition_number(e, top_k=k)

    boot_floor = float("nan")
    boot_sd = float("nan")
    exceed = 0.0
    energy = 0.0
    ell_null = ell_robust
    if calibrate and d > 1 and n > 2:
        if null == "gaussian":
            boot_floor, boot_sd = random_matrix_edge_quantile(
                ell_robust, n, d, center=center, q=0.99, n_boot=0, seed=boot_seed
            )
        elif null == "gaussian_boot":
            boot_floor, boot_sd = random_matrix_edge_quantile(
                ell_robust, n, d, center=center, q=0.99,
                n_boot=max(32, int(n_draw)), seed=boot_seed,
            )
        else:
            boot_floor, boot_sd, ell_null = exchangeable_null_spectrum(
                e, n_draw=n_draw, center=True, seed=boot_seed, q=0.99,
                n_jobs=n_jobs, mode=null,
            )
        if np.isfinite(boot_sd) and boot_sd > EPS:
            exceed = (lmax - boot_floor) / boot_sd
        energy = (lmax - boot_floor) / max(d, 1)
    statistic = float(lmax / ell_null) if np.isfinite(ell_null) and ell_null > EPS else float("nan")
    spike_cos = None
    dir_energy = float("nan")
    if gradient_direction is not None and vecs.size:
        u = np.asarray(gradient_direction, dtype=float).reshape(-1)
        nu = np.linalg.norm(u)
        if nu > EPS:
            u = u / nu
            v = vecs[:, 0]
            vn = np.linalg.norm(v)
            if vn > EPS:
                spike_cos = float(np.dot(u, v / vn))
                dir_energy = float(ev[0] * spike_cos**2)
    return SpectralReport(
        n_steps=int(n),
        dim=int(d),
        effective_condition_number=float(cond),
        top_eigenvalue=lmax,
        tail_eigenvalue=tail,
        total_variance=float(total),
        spike_fraction=float(spike_frac),
        spike_direction_energy=float(dir_energy),
        spike_cos_with_gradient=spike_cos,
        random_matrix_upper_edge=float(edge),
        is_spiked=bool(bbp_detectable(lmax, boot_floor, safety=safety)),
        boot_floor=float(boot_floor),
        boot_sd=float(boot_sd),
        boot_exceedance=float(exceed),
        spike_energy=float(energy),
        centered=bool(center),
        null_kind=str(null),
        statistic=float(statistic),
        null_mean_eigenvalue=float(ell_null),
        notes=(
            f"null={null}"
            + (" (per-row Haar rotation)" if null != "gaussian"
               else " (Gaussian ensemble at the robust scale)")
            + f"; decision lambda_max > {safety} x null q99; statistic = "
            "lambda_max / null mean eigenvalue; spike_energy is the BBP-scale "
            "energy per coordinate"
        ),
    )
