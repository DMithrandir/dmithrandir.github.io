"""Synthetic reverse-noise generators -- the six injection paradigms the audit
tool must handle, each mapped to a real attack surface.

| family | real-world mapping (see `拓展二-工程篇.md` S2) |
|---|---|
| ``clean``                | untampered pipeline                                   |
| ``reverse_spike``        | one rank's updates negated / ``adamw2.py`` partial reversal, concentrated |
| ``norm_matched``         | ``modify_t5`` style: global norm restored in full, direction reversed |
| ``partial_rank_reversal``| ``maximize=True`` on a subset of ranks: mix of +1 and -1 cosines |
| ``micro_spike``          | ``~2^-18..2^-21`` skip of all_gather: rare, huge, invisible in means |
| ``orthogonal_spike``     | sophistication ceiling: spike placed in the gradient's null space |

All generators are *reverse* by construction in the sense fixed with the user:
``E[cos(eps, g)] < 0`` for every family except ``clean`` (where it is 0).  The
``orthogonal_spike`` family additionally has ``E[cos] = 0`` -- it is the family
that Theorem R4 predicts is genuinely harder to catch, and is included so the
tool's honest limits are testable rather than asserted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

__all__ = ["AttackSpec", "FAMILIES", "make_stream", "gradient_stream"]

FAMILIES = (
    "clean",
    "reverse_spike",
    "reverse_spike_fixed",
    "norm_matched",
    "partial_rank_reversal",
    "micro_spike",
    "orthogonal_spike",
)


@dataclass
class AttackSpec:
    """Parameters of a synthetic gradient-noise stream."""

    family: str = "clean"
    n_steps: int = 512
    dim: int = 256
    grad_norm: float = 1.0
    sigma: float = 0.35           # isotropic background noise level (per coordinate)
    spike: float = 2.0            # strength of the reverse component (in units of ||g||)
    rev_frac: float = 0.5         # partial_rank_reversal: fraction of coords flipped
    p_micro: float = 0.02         # micro_spike: firing probability per step
    micro_amp: float = 20.0       # micro_spike: amplitude when it fires
    drift: float = 0.02           # step-size parameter of the directional walk
    persistence: float = 0.995    # AR(1) coefficient of the gradient direction
    spike_coords: Optional[list] = None
    seed: int = 0

    def resolved_coords(self, rng: np.random.Generator) -> np.ndarray:
        if self.spike_coords is not None:
            return np.asarray(self.spike_coords, dtype=int)
        k = max(1, self.dim // 8)
        return rng.choice(self.dim, size=k, replace=False)


def _clean_gradients(spec: AttackSpec, rng: np.random.Generator) -> np.ndarray:
    """A stream of clean gradients whose direction does a persistent random walk.

    ``g_{t+1} ~ N(persistence * g_t, drift^2)`` on the sphere, i.e. an AR(1) in
    direction with correlation time ``1/(1-persistence)``.  The persistence
    parameter is not cosmetic: it is *the* quantity that decides whether a
    fixed-direction attack can also be a reverse-direction attack.

    * High persistence (``~0.995``, the default): the ambient mean direction
      stays close to every per-step direction, so a constant injected offset can
      be simultaneously (a) spectrally loud and (b) strongly anti-aligned with
      the instantaneous gradient.  This is the regime a corrupt rank lives in.
    * Low persistence: the direction decorrelates faster than the mean can track,
      so a constant offset has ``E[cos] ~ 0`` and is only a variance attack --
      the regime where the cosine monitor is blind *by construction*, not by
      failure (Theorem R5.2).
    """
    d, n = spec.dim, spec.n_steps
    rho = float(spec.persistence)
    g = rng.standard_normal(d)
    g = g / np.linalg.norm(g) * spec.grad_norm
    out = np.empty((n, d))
    for t in range(n):
        g = rho * g + spec.drift * rng.standard_normal(d)
        g = g / np.linalg.norm(g) * spec.grad_norm
        out[t] = g
    return out


def gradient_stream(spec: AttackSpec) -> dict:
    """Build ``(g_clean, g_hat, meta)`` for a given attack family.

    ``meta`` carries the ground truth: ``is_reverse``, the theoretical
    ``expected_cos`` and which detector family is expected to fire.
    """
    if spec.family not in FAMILIES:
        raise ValueError(f"unknown family {spec.family!r}; known: {FAMILIES}")
    rng = np.random.default_rng(spec.seed)
    g = _clean_gradients(spec, rng)
    n, d = g.shape
    sigma = spec.sigma
    meta = {"family": spec.family, "sigma": sigma, "spike": spec.spike}

    if spec.family == "clean":
        eps = sigma * rng.standard_normal((n, d))
        meta.update(is_reverse=False, expected_cos=0.0, expected_detector="none")

    elif spec.family == "reverse_spike":
        # Gradient-tracking reverse spike: the attacker knows the current
        # gradient direction (or is the rank that computes it) and pushes
        # exactly backwards.  Spectrally INVISIBLE: the spike direction rotates
        # with g, so the empirical scatter matrix shows no fixed spike.
        u = g / np.linalg.norm(g, axis=1, keepdims=True)
        orth = rng.standard_normal((n, d))
        orth -= np.sum(orth * u, axis=1, keepdims=True) * u
        orth /= np.maximum(np.linalg.norm(orth, axis=1, keepdims=True), 1e-300)
        eps = -spec.spike * spec.grad_norm * u + 0.2 * spec.spike * spec.grad_norm * orth \
            + sigma * rng.standard_normal((n, d))
        meta.update(is_reverse=True,
                    expected_cos=-spec.spike * spec.grad_norm
                    / np.sqrt((spec.spike * spec.grad_norm) ** 2 * 1.04
                              + d * sigma**2),
                    expected_detector="cosine only (no spectral signature)",
                    spectral_signature=False)

    elif spec.family == "reverse_spike_fixed":
        # Same magnitude as reverse_spike but carried by a FIXED ambient
        # direction pair: a constant offset that opposes the walk's average
        # direction (the signature of a corrupt rank holding a constant bias).
        # Contrast case for Theorem R4b: the cosine monitor and the calibrated
        # spectrum monitor both fire here, unlike the tracking variant.
        gbar = g.mean(axis=0)
        w_rev = -gbar / max(np.linalg.norm(gbar), 1e-300)
        # make the fixed offset *maximally* anti-aligned with the mean direction
        # subject to the requested magnitude: any lateral component only dilutes
        # the reverse cosine, so it is added only if the cosine comes out too
        # weak to register (checked below).
        fixed = spec.spike * spec.grad_norm * w_rev
        eps = np.broadcast_to(fixed, (n, d)).copy() + sigma * rng.standard_normal((n, d))
        cos_mean = float(np.mean(
            (g @ fixed) / (np.linalg.norm(g, axis=1) * np.linalg.norm(eps, axis=1))
        ))
        meta.update(is_reverse=bool(cos_mean < 0), expected_cos=cos_mean,
                    expected_detector="cosine + calibrated spectrum",
                    spectral_signature=True)

    elif spec.family == "norm_matched":
        # per-step: draw isotropic noise, then rescale so ||eps|| equals the
        # magnitude the clean pipeline would have produced; direction reversed.
        norm_target = sigma * np.sqrt(d) * (1.0 + 0.05 * rng.standard_normal(n))
        u = g / np.linalg.norm(g, axis=1, keepdims=True)
        raw = rng.standard_normal((n, d))
        raw -= np.sum(raw * u, axis=1, keepdims=True) * u
        raw /= np.maximum(np.linalg.norm(raw, axis=1, keepdims=True), 1e-300)
        eps = norm_target[:, None] * (-u + 0.25 * raw) / np.linalg.norm(
            -u + 0.25 * raw, axis=1, keepdims=True
        )
        meta.update(is_reverse=True,
                    expected_cos=-1.0 / np.sqrt(1.0 + 0.25**2),
                    expected_detector="cosine")

    elif spec.family == "partial_rank_reversal":
        coords = spec.resolved_coords(rng)
        eps = sigma * rng.standard_normal((n, d))
        eps[:, coords] = -2.0 * g[:, coords] + sigma * rng.standard_normal((n, len(coords)))
        share = len(coords) / d
        meta.update(is_reverse=True,
                    expected_cos=-2.0 * share
                    / np.sqrt(4.0 * share * spec.grad_norm**2 + d * sigma**2)
                    * spec.grad_norm,
                    expected_detector="cosine")

    elif spec.family == "micro_spike":
        eps = sigma * rng.standard_normal((n, d))
        fire = rng.random(n) < spec.p_micro
        if np.any(fire):
            u = g[fire] / np.linalg.norm(g[fire], axis=1, keepdims=True)
            eps[fire] -= spec.micro_amp * spec.grad_norm * u
        meta.update(is_reverse=True,
                    expected_cos=-spec.p_micro * spec.micro_amp
                    / np.sqrt((spec.p_micro * spec.micro_amp) ** 2 + d * sigma**2 / spec.grad_norm**2),
                    expected_detector="cosine (heavy-tailed; needs the tail test)",
                    n_fire=int(fire.sum()))

    elif spec.family == "orthogonal_spike":
        # The Theorem-R4 hiding place: reverse energy placed where the gradient
        # has (numerically) zero mass -> ||w||^2 grows, <eps,g> stays zero.
        coords = spec.resolved_coords(rng)
        if len(coords) > d // 2:
            coords = coords[: max(1, d // 8)]
        eps = sigma * rng.standard_normal((n, d))
        eps[:, coords] += spec.spike * spec.grad_norm * rng.standard_normal(
            (n, len(coords))
        ) * np.sign(rng.standard_normal((n, len(coords))))
        meta.update(is_reverse=False, expected_cos=0.0,
                    expected_detector="spectrum (spiked covariance)")

    g_hat = g + eps
    meta["grad_norm"] = spec.grad_norm
    meta["sigma"] = sigma
    meta["spike"] = spec.spike
    meta.setdefault("expected_cos", None)
    return {"g_clean": g, "g_hat": g_hat, "eps": eps, "spec": spec, "meta": meta}


def make_stream(
    family: str = "clean",
    n_steps: int = 512,
    dim: int = 256,
    seed: int = 0,
    **kwargs,
) -> dict:
    """Convenience wrapper around :func:`gradient_stream`."""
    spec = AttackSpec(family=family, n_steps=n_steps, dim=dim, seed=seed, **kwargs)
    return gradient_stream(spec)
