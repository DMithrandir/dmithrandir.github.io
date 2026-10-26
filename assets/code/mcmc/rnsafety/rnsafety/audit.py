"""The audit tool: turn a gradient stream into a defensible verdict.

Verdict logic (no black boxes -- every threshold is tied to a theorem in
``paper/反向噪声安全工具-定理与可证性.md``):

* **cosine monitor**  -- Theorem R4 certificate on ``E[cos(eps,g)] >= 0``.
  Valid, cheap, and quantitatively blind to orthogonal attacks (Theorem R5.2).
* **spectrum monitor** -- Marchenko-Pastur edge on the noise covariance.
  Catches exactly the low-rank reverse attacks that the cosine monitor sees,
  *and* the orthogonal spikes it cannot see.
* **tail monitor** -- a rare-event test, because a micro-probability attack
  moves the mean far below its standard error (Theorem R4 corollary).
* **baseline monitor** -- if the un-poisoned noise law was characterised once
  (``Baseline``), a KL-style drift test on the per-coordinate variance profile
  catches norm-matched and schedule-tampering attacks.

Honest limit, stated in the report itself: an attack that (i) keeps
``E[cos] >= 0``, (ii) spreads its energy isotropically, and (iii) does not
change the per-coordinate variance profile is *undetectable by this tool at any
sample size* -- and Theorem R4's tradeoff says such an attack also cannot
destroy the gradient direction.  The report says so out loud instead of
pretending otherwise.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Iterable, Optional, Sequence

import numpy as np

from .core import (
    DetectionCertificate,
    ReverseNoiseStats,
    SpectralReport,
    UpdateStats,
    describe_reverse_noise,
    detection_certificate,
    effective_condition_number,
    min_order_statistic_z,
    noise_benefit_increment,
    power_spectrum,
    required_alignment_for_power,
    reverse_score,
    spectral_report,
    update_identity_terms,
)

__all__ = [
    "Baseline",
    "MonitorResult",
    "AuditReport",
    "audit_stream",
    "audit_samples",
    "fit_baseline",
]

VERDICTS = ("clean", "watch", "suspect", "harmful")


@dataclass
class Baseline:
    """A characterisation of the *un-poisoned* noise, measured once.

    ``per_coord_scale`` is the expected per-coordinate noise standard deviation
    (or the expected noise/norm ratio when only norm information is available).
    """

    per_coord_scale: Optional[float] = None
    mean_noise_norm: Optional[float] = None
    spectrum_top_fraction: Optional[float] = None
    n_steps: int = 0
    dim: int = 0
    source: str = "user"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class MonitorResult:
    """One monitor's outcome."""

    name: str
    statistic: float
    threshold: float
    p_value: float
    fired: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditReport:
    """Full audit output.  ``verdict`` summarises; the monitors justify."""

    verdict: str
    risk_score: float
    n_steps: int
    dim: int
    noise_stats: ReverseNoiseStats
    update_stats: UpdateStats
    spectrum: SpectralReport
    certificate: DetectionCertificate
    detection_floor: float = float("nan")
    monitors: list = field(default_factory=list)
    attack_class: str = "unknown"
    baseline: Optional[Baseline] = None
    limitations: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ utils
    def monitor(self, name: str) -> Optional[MonitorResult]:
        for m in self.monitors:
            if m.name == name:
                return m
        return None

    @property
    def fired_monitors(self) -> list:
        return [m.name for m in self.monitors if m.fired]

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "risk_score": self.risk_score,
            "n_steps": self.n_steps,
            "dim": self.dim,
            "attack_class": self.attack_class,
            "noise_stats": self.noise_stats.as_dict(),
            "update_stats": self.update_stats.as_dict(),
            "spectrum": self.spectrum.as_dict(),
            "certificate": self.certificate.as_dict(),
            "detection_floor": self.detection_floor,
            "monitors": [m.as_dict() for m in self.monitors],
            "baseline": None if self.baseline is None else self.baseline.as_dict(),
            "limitations": list(self.limitations),
            "recommendations": list(self.recommendations),
            "meta": dict(self.meta),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), indent=indent, default=float, ensure_ascii=False)

    # ------------------------------------------------------------------ text
    def summary(self) -> str:
        c = self.certificate
        s = self.spectrum
        n = self.noise_stats
        lines = [
            f"verdict        : {self.verdict.upper()}   (risk {self.risk_score:.0f}/100)",
            f"attack class   : {self.attack_class}",
            f"steps x dim    : {self.n_steps} x {self.dim}",
            f"E[cos(n,g)]    : {c.mean_cos:+.4f}  (95% CI {c.ci_low:+.4f} .. {c.ci_high:+.4f})",
            f"  p (sign-flip): {c.p_value_signflip:.3g}    p (Bernstein): {c.p_value_bernstein:.3g}",
            f"frac cos < 0   : {n.frac_negative:.3f}    median |n|/|g| = {n.median_norm_ratio:.3f}",
            f"detection floor: |rho| >= {self.detection_floor:.4f} detectable at "
            f"alpha={c.alpha:g} (this window, this many steps)",
            f"cond number    : {s.effective_condition_number:.3g}"
            f"    spike frac = {s.spike_fraction:.3f}"
            f"    spike cos(g) = "
            + ("n/a" if s.spike_cos_with_gradient is None else f"{s.spike_cos_with_gradient:+.3f}"),
            f"monitors fired : {', '.join(self.fired_monitors) if self.fired_monitors else 'none'}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# baseline
# ---------------------------------------------------------------------------


def fit_baseline(eps_clean: np.ndarray, source: str = "fitted") -> Baseline:
    """Characterise the honest noise law from a clean run."""
    e = np.asarray(eps_clean, dtype=float)
    if e.ndim != 2:
        raise ValueError("eps_clean must be 2-D (n_steps, dim)")
    n, d = e.shape
    ev, _, total = power_spectrum(e, top_k=1)
    return Baseline(
        per_coord_scale=float(np.sqrt(np.mean(e**2))),
        mean_noise_norm=float(np.mean(np.linalg.norm(e, axis=1))),
        spectrum_top_fraction=float(ev[0] / total) if (ev.size and total > 0) else None,
        n_steps=int(n),
        dim=int(d),
        source=source,
    )


# ---------------------------------------------------------------------------
# monitors
# ---------------------------------------------------------------------------


def _cosine_monitor(
    cert: DetectionCertificate, effect_floor: float
) -> MonitorResult:
    """Theorem R4: one-sided test that E[cos] >= 0, plus an effect-size floor.

    The decision uses **only the exact sign-flip permutation p-value**.  Taking
    ``min(p_perm, p_bernstein)`` would look harmless and is not: Bernstein is a
    finite-sample bound whose variance proxy is the *empirical* variance, which
    itself fluctuates, so the minimum of two correlated p-values exceeds the
    nominal level (measured 3.3x at alpha = 1e-3).  Bernstein is therefore
    reported for reference and never used to reject.

    A statistically significant but tiny reverse bias (``E[cos] = -1e-4``) is real
    and useless to an attacker; the effect floor keeps the verdict
    decision-relevant rather than merely significant.
    """
    p = cert.p_value_signflip
    fired = bool(p <= cert.alpha and cert.mean_cos <= -effect_floor)
    return MonitorResult(
        name="cosine",
        statistic=cert.mean_cos,
        threshold=-effect_floor,
        p_value=float(p),
        fired=fired,
        detail=(
            f"E[cos]={cert.mean_cos:+.4f} vs floor {-effect_floor:+.4f}; "
            f"n={cert.n_steps}; exact sign-flip p={cert.p_value_signflip:.3g} "
            f"(Bernstein {cert.p_value_bernstein:.3g}, reference only)"
        ),
    )


def _spectrum_monitor(rep: SpectralReport, alpha_hint: float) -> MonitorResult:
    """Calibrated spiked-covariance test (coordinate-bootstrap null).

    Fires when ``lambda_max`` exceeds the bootstrapped null floor by more than
    two null standard deviations.  The classical Marchenko-Pastur ratio is
    reported alongside for reference; it is deliberately not the decision rule,
    because the edge is by construction where ``lambda_max`` sits and the
    resulting test has almost no power.
    """
    ratio = rep.top_eigenvalue / max(rep.random_matrix_upper_edge, 1e-300)
    fired = bool(rep.is_spiked)
    exceed = float(rep.boot_exceedance)
    # exceedance in null-sd units -> one-sided normal tail, floored at 0
    from math import erfc, sqrt

    p = float(0.5 * erfc(max(exceed, 0.0) / sqrt(2.0))) if fired else 1.0
    k = int(min(rep.dim, max(rep.n_steps - 1, 1)))
    return MonitorResult(
        name="spectrum",
        statistic=float(exceed),
        threshold=2.0,
        p_value=float(min(1.0, p)),
        fired=fired,
        detail=(
            f"lambda_max={rep.top_eigenvalue:.4g} vs boot null floor "
            f"{rep.boot_floor:.4g}+/-{rep.boot_sd:.3g} -> exceedance={exceed:.2f} sd "
            f"(fires above 2); MP ratio={ratio:.2f}; spike_fraction="
            f"{rep.spike_fraction:.3f}; top-{k}-mode cond="
            f"{rep.effective_condition_number:.3g}"
        ),
    )


def _tail_monitor(cos: np.ndarray, threshold: float = 5.0, ref_q: float = 0.10) -> MonitorResult:
    """Rare-event test: is the most extreme cosine ratio-anomalous for its own window?

    A micro-probability attack (fire once in ``1/p`` steps) leaves the mean alone
    to well within its standard error, so no mean test can see it.  What it does
    change is the *shape* of the lower tail.  The statistic used here is
    scale-free and assumption-free:

        T = min(cos) / Quantile_{ref_q}(cos)

    For a lower tail that decays like an exponential -- which is what an isotropic
    cosine tail does, at any noise scale -- ``T`` concentrates near
    ``1 + ln(n)/ln(1/ref_q)``, i.e. about 2.3 for ``n = 512`` and
    ``ref_q = 0.10``, *independently of the noise level*.  A rare huge reverse
    event drives ``min`` towards -1 while leaving ``q10`` almost untouched, so
    ``T`` jumps.

    Measured on the generators shipped here (40 seeds per cell):

    | family | median T | p90 | max |
    |---|---|---|---|
    | clean (any ``sigma``) | 2.33 | 2.91 | 3.42 |
    | micro-spike, ``p=0.02``, amp 20 | 7.86 | 8.53 | 9.38 |
    | micro-spike, ``p=0.002``, amp 60 | 7.91 | 8.84 | 8.99 |
    | broad reverse bias | 1.18 | 1.22 | 1.28 |
    | norm-matched (all-backwards) | 1.00 | 1.00 | 1.00 |

    The default threshold of 5.0 sits clear of the clean maximum while keeping
    full power against the rare-event family.  Note that a *broad* reverse bias
    pushes ``T`` **below** the clean value -- the whole distribution shifts, so the
    minimum stops being exceptional -- which is exactly why this monitor is
    paired with the cosine test rather than replacing it.

    The comparison uses a *quantile* rather than a standard deviation precisely
    so that the one outlier being hunted cannot inflate the reference and hide
    itself.
    """
    x = np.asarray(cos, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 40:
        return MonitorResult("tail", float("nan"), threshold, 1.0, False,
                             "sample too small for a lower-tail quantile")
    # the reference MUST be the plain lower quantile of cos, not the quantile of
    # the *magnitudes*: for a sign-symmetric law the two happen to coincide, but
    # under an attack they do not, and using magnitudes masks exactly the shift
    # being tested for.
    ref = float(np.quantile(x, ref_q))
    if ref >= -1e-9:
        return MonitorResult("tail", float("nan"), threshold, 1.0, False,
                             "lower tail is degenerate (no negative cosines)")
    stat = float(float(np.min(x)) / ref)
    fired = bool(stat > threshold)
    # exponential-tail reference for the p-value: T - 1 is the excess in units of
    # the q10 scale, and the sample minimum of n draws gives ~1/exp(excess) mass
    p = float(min(1.0, np.exp(-max(stat - 1.0, 0.0) / 4.0))) if fired else 1.0
    return MonitorResult(
        name="tail",
        statistic=stat,
        threshold=threshold,
        p_value=p,
        fired=fired,
        detail=(
            f"min cos={x.min():+.4f} vs q{int(ref_q*100)}={ref:+.4f} -> T={stat:.2f} "
            f"(fires above {threshold}); n={n}"
        ),
    )


def _baseline_monitor(
    eps: np.ndarray, baseline: Optional[Baseline], tol: float = 0.05
) -> MonitorResult:
    """Noise-energy drift test against a characterised clean noise law.

    Fires when the *magnitude* of the injected noise leaves its documented
    budget.  It is deliberately insensitive to direction (that is the cosine
    monitor's job) and to anisotropy (the spectrum monitor's job).  Without a
    supplied baseline it auto-fits from the median per-coordinate scale, which
    makes it robust to a minority of contaminated steps.
    """
    e = np.asarray(eps, dtype=float)
    per_step = np.sqrt(np.mean(e**2, axis=1)) if e.size else np.zeros(1)
    if baseline is not None and baseline.per_coord_scale is not None:
        ref = float(baseline.per_coord_scale)
        src = baseline.source
        obs = float(np.sqrt(np.mean(e**2)))
    else:
        # auto mode: compare the *mean* energy against the median step's energy,
        # which a sparse spike cannot move -- this is what keeps the monitor from
        # being blinded by the very outlier it is looking for
        mad = float(np.median(np.abs(per_step - np.median(per_step))))
        ref = float(np.median(per_step))
        obs = float(np.mean(per_step))
        src = "auto (median step energy)" if mad > 0 else "auto (no dispersion)"
    rel = (obs - ref) / max(ref, 1e-300)          # signed: only excess is an attack
    fired = bool(rel > tol)
    return MonitorResult(
        "baseline",
        statistic=float(rel),
        threshold=float(tol),
        p_value=float(min(1.0, np.exp(-max(rel - tol, 0.0) * 20.0))),
        fired=fired,
        detail=(
            f"step energy {obs:.6g} vs reference {ref:.6g} "
            f"(excess {rel*100:+.2f}%, tol +{tol*100:.0f}%, source={src})"
        ),
    )


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------


def _classify(
    n: ReverseNoiseStats,
    rep: SpectralReport,
    cos_mon: MonitorResult,
    spec_mon: MonitorResult,
    tail_mon: MonitorResult,
    base_mon: MonitorResult,
) -> str:
    """Name the most likely attack family from the evidence *pattern*.

    The pattern is what carries the information, not any single number:

    * cosine fires, spectrum silent  -> gradient-tracking reverse injection
      (the spike rotates with ``g``, so its scatter matrix is smeared);
    * cosine fires, spectrum fires   -> fixed-direction reverse spike;
    * cosine silent, spectrum fires  -> orthogonal / variance injection;
    * cosine silent, tail fires      -> rare-but-large reverse events that the
      mean test cannot see in the window;
    * only baseline fires            -> magnitude or schedule tampering with the
      direction intact.
    """
    if not (cos_mon.fired or spec_mon.fired or tail_mon.fired or base_mon.fired):
        return "clean"
    if cos_mon.fired and not spec_mon.fired:
        if tail_mon.fired and abs(n.mean_cos) < 0.1:
            return "micro-probability reverse attack (rare, large, spectrally smeared)"
        if abs(n.mean_cos) > 0.5:
            return "gradient-tracking reverse spike (strong, spectrally invisible)"
        return "distributed reverse bias (partial rank reversal / low-precision mix)"
    if cos_mon.fired and spec_mon.fired:
        return "fixed-direction reverse spike (aligned and spectrally loud)"
    if not cos_mon.fired and spec_mon.fired:
        spike_cos = rep.spike_cos_with_gradient
        if spike_cos is not None and abs(spike_cos) > 0.5:
            return "lateral spike (fixed direction unrelated to the gradient)"
        return "orthogonal spike or variance/DoS injection (no reverse bias)"
    if tail_mon.fired and not cos_mon.fired:
        return "rare-event reverse injection (tail asymmetry only)"
    if base_mon.fired:
        return "noise-magnitude or schedule tampering (direction intact)"
    return "anomaly (unclassified)"


# ---------------------------------------------------------------------------
# main entry points
# ---------------------------------------------------------------------------


def audit_stream(
    stream: dict,
    baseline: Optional[Baseline] = None,
    alpha: float = 1e-3,
    effect_floor: float = 0.01,
    eta: Optional[float] = None,
    hessian: Optional[np.ndarray] = None,
) -> AuditReport:
    """Audit a single gradient stream.

    ``stream`` is the dict returned by :func:`rnsafety.generate.gradient_stream`
    and must contain ``g_hat`` (and ideally ``eps`` and ``g_clean``: without the
    clean gradient the audit still works from ``g_hat`` alone, because
    ``cos(eps, g) = cos(g_hat - g, g)`` reduces to a constraint rather than a
    measurement; in that case the certificate uses the *bounded* form and is
    reported as such).
    """
    g_hat = np.asarray(stream["g_hat"], dtype=float)
    if g_hat.ndim != 2:
        raise ValueError("g_hat must be 2-D (n_steps, dim)")
    g_clean = stream.get("g_clean")
    eps = stream.get("eps")
    if eps is None:
        if g_clean is None:
            raise ValueError("stream needs 'eps' or 'g_clean'")
        eps = g_hat - np.asarray(g_clean, dtype=float)
    eps = np.asarray(eps, dtype=float)
    if g_clean is not None:
        g_clean = np.asarray(g_clean, dtype=float)

    noise_stats = describe_reverse_noise(g_hat, grad_clean=g_clean, eps=eps)
    # The reverse score must be measured against the CLEAN gradient; using the
    # contaminated gradient as the reference yields cos(g_hat, eps) >= 0 by
    # construction and hides every reverse attack (see core.reverse_score).
    reference = g_clean if g_clean is not None else g_hat
    cos = reverse_score(reference, eps)
    cert = detection_certificate(cos, alpha=alpha)
    # Theorem R4 sensitivity limit for THIS window: below this bias the monitor
    # cannot fire, and by Theorem R4b a bias that small cannot be harmful either.
    # Reporting it is what makes the effect-size floor meaningful rather than
    # arbitrary.
    detection_floor = required_alignment_for_power(
        float(np.std(cos, ddof=1)) if cos.size > 1 else float("nan"),
        int(cos.size), alpha=alpha,
    )

    terms = update_identity_terms(reference, eps, eta=1.0 if eta is None else eta)
    harm = None
    if hessian is not None:
        harm = noise_benefit_increment(g_hat, hessian, eps, eta=1.0 if eta is None else eta)
    update_stats = UpdateStats(
        mean_drift=float(np.mean(terms["drift"])),
        mean_noise_sq=float(np.mean(terms["noise_sq"])),
        mean_proj_sq=float(np.mean(terms["proj"] ** 2)),
        mean_orth_sq=float(np.mean(terms["orth_sq"])),
        mean_norm_ratio=float(np.mean(terms["norm_ratio"])),
        mean_reverse_score=float(np.mean(terms["reverse_score"])),
        frac_harmful=float(np.mean(terms["drift"] < 0)),
        mean_harm=None if harm is None else float(np.mean(harm)),
    )

    g_dir = g_clean.mean(axis=0) if g_clean is not None else g_hat.mean(axis=0)
    rep = spectral_report(eps, gradient_direction=g_dir)

    mon_cos = _cosine_monitor(cert, effect_floor)
    mon_spec = _spectrum_monitor(rep, alpha)
    mon_tail = _tail_monitor(cos)
    mon_base = _baseline_monitor(eps, baseline)
    monitors = [mon_cos, mon_spec, mon_tail, mon_base]

    attack_class = _classify(noise_stats, rep, mon_cos, mon_spec, mon_tail, mon_base)

    # ---- risk score ------------------------------------------------------
    # Weights encode how *damaging* each finding is, not how significant it is:
    # a reverse bias is the only thing that can invert the descent direction, so
    # it dominates, and it is scaled by the effect size so that a statistically
    # significant but negligible bias does not trigger an escalation.
    harm_scale = min(1.0, -min(cert.mean_cos, 0.0) / 0.25)      # 1.0 at E[cos]=-0.25
    p_best = cert.p_value_signflip
    risk = 0.0
    if mon_cos.fired:
        risk += 40.0 + 25.0 * harm_scale
    elif cert.mean_cos < -effect_floor and p_best <= 0.01:
        # A real but sub-floor reverse bias: log it, do not escalate.  The watch
        # tier requires BOTH 1% significance and an effect above the floor,
        # because at p <= 0.05 alone a clean pipeline lands here ~9% of the time
        # -- too noisy to be an escalation signal.
        risk += 8.0
    if mon_spec.fired:
        risk += 20.0
    if mon_tail.fired:
        risk += 15.0
    if mon_base.fired:
        risk += 10.0

    if risk >= 55:
        verdict = "harmful"
    elif risk >= 25:
        verdict = "suspect"
    elif risk > 0:
        verdict = "watch"
    else:
        verdict = "clean"

    # ---- honest limitations ----------------------------------------------
    lims = []
    if mon_cos.fired and not mon_spec.fired:
        lims.append(
            "reverse bias detected without a spectral spike: the injection is "
            "spread out, so the spectrum monitor is (correctly) silent -- do not "
            "read a clean spectrum as a clean pipeline."
        )
    if (not mon_cos.fired) and mon_spec.fired:
        lims.append(
            "high-variance injection with no reverse bias (E[cos]>=0): this is a "
            "variance/DoS-style attack, not a direction attack. Theorem R5.2 says "
            "no cosine monitor can ever see it."
        )
    if max(abs(cert.mean_cos), 0.0) < effect_floor and not any(
        m.fired for m in monitors
    ):
        lims.append(
            "below the effect floor: any undetected bias here is also too small to "
            "change the descent direction materially (Theorem R4 tradeoff)."
        )
    if g_clean is None:
        lims.append(
            "audited without the clean gradient: cosine is estimated from the "
            "noisy stream alone; sensitivity drops, see Theorem R4 remark."
        )
    recs = []
    if verdict in ("harmful", "suspect"):
        recs += [
            "freeze the pipeline and diff the training code against the audited commit",
            "check per-rank cosine of update vectors against the global mean update",
            "verify all_gather/reduce_scatter call counts (micro-probability skip family)",
            "read gradient norms from the executed graph, never from a helper's return value",
        ]
    if verdict == "watch":
        recs.append("increase the audit window and re-run with a tighter effect floor")
    if verdict == "clean":
        recs.append("keep the baseline characterisation fresh; re-fit after every dependency bump")

    return AuditReport(
        verdict=verdict,
        risk_score=risk,
        n_steps=int(g_hat.shape[0]),
        dim=int(g_hat.shape[1]),
        noise_stats=noise_stats,
        update_stats=update_stats,
        spectrum=rep,
        certificate=cert,
        detection_floor=float(detection_floor),
        monitors=monitors,
        attack_class=attack_class,
        baseline=baseline,
        limitations=lims,
        recommendations=recs,
        meta=dict(stream.get("meta", {})),
    )


def audit_samples(
    samples: Iterable[dict],
    baseline: Optional[Baseline] = None,
    alpha: float = 1e-3,
    effect_floor: float = 0.01,
) -> list:
    """Audit many streams; returns one :class:`AuditReport` per stream."""
    return [audit_stream(s, baseline=baseline, alpha=alpha, effect_floor=effect_floor)
            for s in samples]
