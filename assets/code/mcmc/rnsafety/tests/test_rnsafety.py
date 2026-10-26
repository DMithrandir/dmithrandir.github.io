"""Test suite for the reverse-noise safety toolkit.

Three kinds of test, in order of how much they are worth:

1. **Exact identities** (machine precision).  ``noise_benefit_increment`` must equal
   the difference of the two quadratic increments; the delta/w decomposition must
   be exact; ``power_spectrum`` must agree with a directly formed covariance.
   These catch sign and factor errors, which is how three real bugs in this
   toolkit were found.
2. **Counterexamples and bounds** — the two refutations of "a singularity is
   inevitable" (R5.1, R5.2), the Theorem R3 scaling, the Theorem R4 false-alarm
   calibration, and the Theorem R4b invisibility/effectiveness trade-off.
3. **Tool behaviour** — the auditor catches the six attack families, does not
   flag clean streams, reports its own limitations, and round-trips through JSON
   and the CLI.

Run::

    cd C:\\Financial-Data-Workflow\\_mcmc\\rnsafety
    python -m pytest -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rnsafety import (  # noqa: E402
    FAMILIES,
    AttackSpec,
    audit_stream,
    fit_baseline,
    gradient_stream,
    make_stream,
)
from rnsafety.core import (  # noqa: E402
    detection_certificate,
    direction_condition_number,
    effective_condition_number,
    exchangeable_null_spectrum,
    gradient_loss_increment,
    noise_benefit_condition_boundary,
    noise_benefit_increment,
    noise_covariance,
    power_spectrum,
    quadratic_loss_increment,
    random_matrix_edge_quantile,
    reverse_noise_effect,
    reverse_score,
    robust_noise_scale,
    set_n_jobs,
    spectral_report,
    update_identity_terms,
)

set_n_jobs(1)          # keep the tests deterministic and fast


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def problem():
    rng = np.random.default_rng(0)
    n, d = 64, 8
    g = rng.standard_normal((n, d))
    eps = 0.3 * rng.standard_normal((n, d))
    h = rng.standard_normal((d, d))
    H = (h + h.T) / 2 + 3.0 * np.eye(d)
    return g, eps, H, 0.05


# ---------------------------------------------------------------------------
# 1. exact identities
# ---------------------------------------------------------------------------


def test_harm_equals_increment_difference(problem):
    """Theorem R1: the closed-form harm equals noisy-minus-clean, exactly."""
    g, eps, H, eta = problem
    harm = noise_benefit_increment(g, H, eps, eta)
    exact = (quadratic_loss_increment(g, H, eps, eta)
             - gradient_loss_increment(g, H, eta))
    assert np.allclose(harm, exact, rtol=0, atol=1e-14)


def test_harm_decomposition_coefficients(problem):
    """The four coefficients of the harm identity are (-2, -1, +1, +1/2)."""
    g, eps, H, eta = problem
    y = noise_benefit_increment(g, H, eps, eta)
    basis = np.column_stack([
        eta * np.sum(eps * g, axis=1),
        eta * np.sum(eps * eps, axis=1),
        eta**2 * np.einsum("ni,ij,nj->n", eps, H, g),
        eta**2 * np.einsum("ni,ij,nj->n", eps, H, eps),
    ])
    coef, *_ = np.linalg.lstsq(basis, y, rcond=None)
    assert np.allclose(coef, [-2.0, -1.0, 1.0, 0.5], atol=1e-8)


def test_reverse_noise_increases_loss():
    """A reverse noise loses ground relative to the clean step (Theorem R1/R3)."""
    rng = np.random.default_rng(3)
    n, d = 200, 16
    g = rng.standard_normal((n, d))
    g /= np.linalg.norm(g, axis=1, keepdims=True)
    u = g
    eps = -0.8 * u + 0.1 * rng.standard_normal((n, d))
    h = rng.standard_normal((d, d))
    H = (h + h.T) / 2 + 4.0 * np.eye(d)
    harm = noise_benefit_increment(g, H, eps, eta=0.01)
    assert float(np.mean(harm)) > 0.0


def test_delta_decomposition_is_exact(problem):
    g, eps, H, eta = problem
    t = update_identity_terms(g, eps)
    assert np.allclose(t["proj"] ** 2 + t["orth_sq"], t["noise_sq"], atol=1e-12)


def test_reverse_score_matches_manual_cosine(problem):
    g, eps, H, eta = problem
    manual = np.sum(eps * g, axis=1) / (np.linalg.norm(g, axis=1)
                                        * np.linalg.norm(eps, axis=1))
    assert np.allclose(reverse_score(g, eps), manual, atol=1e-14)


def test_contaminated_reference_is_biased_positive():
    """The documented trap: cos(g_hat, eps) is positive and has a closed form.

    ``E[cos(g_hat,eps)] = ||eps|| / sqrt(||g||^2 + ||eps||^2)``, i.e. it grows
    monotonically with the noise-to-signal ratio and is positive for *any* noise
    level -- which is exactly why it must never be used as the security statistic.
    """
    rng = np.random.default_rng(4)
    n, d = 4096, 32
    g = rng.standard_normal((n, d))
    eps = 0.6 * rng.standard_normal((n, d))
    gn = np.linalg.norm(g, axis=1)
    en = np.linalg.norm(eps, axis=1)
    predicted = float(np.mean(en / np.sqrt(gn**2 + en**2)))
    observed = float(np.mean(reverse_score(g + eps, eps)))
    assert predicted > 0.3
    assert abs(observed - predicted) < 0.02
    assert abs(float(np.mean(reverse_score(g, eps)))) < 0.05


def test_power_spectrum_matches_direct_covariance():
    rng = np.random.default_rng(5)
    e = rng.standard_normal((64, 24))
    ev, vecs, total = power_spectrum(e, top_k=4, center=False)
    direct = np.sort(np.linalg.eigvalsh(e.T @ e / 64))[::-1][:4]
    assert np.allclose(ev, direct, rtol=1e-8)
    assert abs(total - float(np.trace(e.T @ e / 64))) < 1e-9
    # centered path
    ev_c, _, total_c = power_spectrum(e, top_k=4, center=True)
    ec = e - e.mean(axis=0)
    direct_c = np.sort(np.linalg.eigvalsh(ec.T @ ec / 63))[::-1][:4]
    assert np.allclose(ev_c, direct_c, rtol=1e-8)
    assert abs(total_c - float(np.trace(ec.T @ ec / 63))) < 1e-9


def test_power_spectrum_gram_route_agrees():
    """n < d uses the Gram route; the eigenvalues must still be the covariance's."""
    rng = np.random.default_rng(6)
    e = rng.standard_normal((32, 96))
    ev, _, total = power_spectrum(e, top_k=4, center=False)
    direct = np.sort(np.linalg.eigvalsh(e.T @ e / 32))[::-1][:4]
    assert np.allclose(ev, direct, rtol=1e-7)
    assert abs(total - float(np.trace(e.T @ e / 32))) < 1e-9


def test_noise_covariance_shape_and_symmetry():
    rng = np.random.default_rng(7)
    e = rng.standard_normal((50, 12))
    c = noise_covariance(e)
    assert c.shape == (12, 12)
    assert np.allclose(c, c.T, atol=1e-12)


def test_robust_scale_is_mean_eigenvalue():
    rng = np.random.default_rng(8)
    e = 0.5 * rng.standard_normal((128, 40))
    ell = robust_noise_scale(e)
    assert abs(ell - float(np.sum(e**2) / (128 * 40))) < 0.01


def test_direction_condition_number_of_isotropic_noise():
    rng = np.random.default_rng(9)
    e = 0.7 * rng.standard_normal((4096, 64))
    u = rng.standard_normal(64)
    kappa = direction_condition_number(e, u)
    assert abs(kappa - 1.0) < 0.1        # 1 +/- sampling error sqrt(2/n)


def test_effective_condition_number_is_finite_and_rank_aware():
    """The condition number is defined over the well-determined modes only.

    When ``n < d`` the sample second moment is singular by construction, so a
    ``lambda_min``-based value would report the sample size rather than the noise.
    The reported number must therefore be finite and stable, while an *exactly*
    rank-deficient stream -- a real signature, e.g. a low-rank injection -- still
    reports ``inf`` when asked to include the zero modes.
    """
    rng = np.random.default_rng(10)
    e = rng.standard_normal((64, 32))
    full_rank = effective_condition_number(e)
    assert np.isfinite(full_rank) and full_rank > 0.0
    e_rank_deficient = e.copy()
    e_rank_deficient[:, 16:] = 0.0
    assert np.isinf(effective_condition_number(e_rank_deficient, top_k=32, ridge=0.0))
    assert np.isfinite(effective_condition_number(e_rank_deficient, top_k=16,
                                                 ridge=0.0))


# ---------------------------------------------------------------------------
# 2. counterexamples and bounds
# ---------------------------------------------------------------------------


def test_counterexample_r51_isotropic_noise_has_unit_condition_number():
    """R5.1: an isotropic injection never creates a condition-number singularity."""
    rng = np.random.default_rng(11)
    n, d = 2048, 64
    g = rng.standard_normal((n, d))
    g /= np.linalg.norm(g, axis=1, keepdims=True)
    kappas = []
    for a in (1e-3, 1.0, 1e3):
        eps = a * rng.standard_normal((n, d))
        proj = np.sum(eps * g, axis=1)
        ell = float(np.mean(np.sum(eps**2, axis=1))) / d
        kappas.append(float(np.mean(proj**2)) / ell)
    assert max(abs(k - 1.0) for k in kappas) < 0.1


def test_counterexample_r52_cosine_density_is_smooth():
    """R5.2: the cosine law is a smooth Beta density; no atom, no pole."""
    rng = np.random.default_rng(12)
    n, d = 20000, 64
    t = reverse_score(rng.standard_normal((n, d)),
                      0.4 * rng.standard_normal((n, d)))
    # variance 1/d, and the empirical CDF tracks Phi(t*sqrt(d/2))
    assert abs(float(np.var(t)) - 1.0 / d) < 0.002
    from math import erf
    grid = np.linspace(-0.5, 0.5, 41)
    theory = np.array([0.5 * (1 + erf(x * np.sqrt(d / 2.0))) for x in grid])
    empirical = np.array([float(np.mean(t <= x)) for x in grid])
    assert float(np.max(np.abs(theory - empirical))) < 0.02
    # no atom: the largest bin mass is far below a point mass
    counts, _ = np.histogram(t, bins=512, range=(-1, 1))
    assert float(counts.max()) / n < 20.0 / 512


def test_theorem_r3_scaling():
    """R3: the closed-form reverse cosine and the conditioning cost."""
    rng = np.random.default_rng(13)
    n, d = 512, 32
    kappas = []
    for a in (0.1, 0.5, 2.0, 8.0):
        u = rng.standard_normal((n, d))
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        w = rng.standard_normal((n, d))
        w -= np.sum(w * u, axis=1, keepdims=True) * u
        eps = -a * u + 0.4 * w
        r = reverse_noise_effect(u + eps, u)
        pred = -a / np.sqrt(a**2 + 0.4**2 * float(np.mean(np.sum(w**2, axis=1))))
        assert abs(r["mean_cos"] - pred) < 0.01
        kappas.append(r["directional_condition_number"])
    assert all(kappas[i] < kappas[i + 1] for i in range(len(kappas) - 1))


def test_theorem_r3_independent_noise_is_benign():
    """Independent zero-mean noise gives E[cos(g_hat,g)] > 0, never reverse.

    The exact value is ``E[||g||/||g+eps||] > 0``; the empirical mean of the
    random cosine has standard error ``1/sqrt(nd)``, which is much larger than the
    expectation itself, so the assertion is on the exact identity rather than on a
    noisy sample that can legitimately land on either side of zero.
    """
    rng = np.random.default_rng(14)
    n, d = 4096, 64
    g = rng.standard_normal((n, d))
    eps = 0.5 * rng.standard_normal((n, d))
    exact = float(np.mean(np.linalg.norm(g, axis=1)
                          / np.linalg.norm(g + eps, axis=1)))
    assert exact > 0.0
    observed = float(np.mean(reverse_score(g + eps, g)))
    assert abs(observed - exact) < 5.0 / np.sqrt(n * d)
    # and the noise never has a reverse bias in expectation
    assert abs(float(np.mean(reverse_score(g, eps)))) < 5.0 / np.sqrt(n * d)


def test_theorem_r2_admissible_set_is_a_ball():
    """R2: the admissible set of condition (2) is B(s, sqrt(||s||^2 - 2 sigma^2 A)).

    Condition (2) is ``||n||^2 - 2<n,s> + 2 sigma^2 A <= 0``, which completes the
    square to ``||n - s||^2 <= ||s||^2 - 2 sigma^2 A``.  Everything about the
    theorem follows from that one line.

    Regression: three earlier versions reasoned about a *direction* bound
    ``cos(n,s) >= c*`` and concluded the admissible cone points backwards with
    ``c* -> -1``.  Both are wrong -- ``f(-s) = 3||s||^2 + 2 sigma^2 A > 0``
    whenever the ball exists, and at the threshold the ball collapses onto
    ``n = s``, i.e. ``cos -> +1``.  The parent paper's own E1-D measurement
    (accepted noise correlates *positively* with the jump, r = 0.453) agrees with
    the corrected geometry and not with the old one.
    """
    sigma = 1.0
    for A in (2.0, 0.5, -0.5, -2.0):
        for s_norm in (0.3, 1.0, 3.0):
            s = np.array([s_norm, 0.0])
            info = noise_benefit_condition_boundary(s_norm, A, sigma=sigma)
            r2 = s_norm**2 - 2.0 * sigma**2 * A
            if A > 0.0 and r2 < 0.0:
                assert not info["feasible"]
                continue
            r = np.sqrt(r2)
            assert info["feasible"]
            assert info["radius"] == pytest.approx(r, rel=1e-12)
            # the ball is centred at n = s, so n = s is always admissible
            f_s = float(s @ s) - 2.0 * float(s @ s) + 2.0 * sigma**2 * A
            assert f_s <= 1e-12
            # fully reversed noise never is, whenever the ball excludes the origin
            if r < s_norm:
                f_neg = 3.0 * s_norm**2 + 2.0 * sigma**2 * A
                assert f_neg > 0.0


def test_theorem_r2_threshold_and_direction():
    """R2: threshold sqrt(2 sigma^2 A); the cone closes onto cos = +1, not -1.

    For ``A > 0`` the condition is unsatisfiable below ``||s|| = sqrt(2 sigma^2 A)``
    -- no injection of any magnitude or direction helps.  Above it, the admissible
    half-angle is ``asin(r/||s||)`` and shrinks to zero at the threshold, so the
    most-backward admissible direction has cosine tending to **+1**.
    """
    A = 2.0
    thr = float(np.sqrt(2.0 * A))
    assert not noise_benefit_condition_boundary(thr * 0.99, A)["feasible"]
    at = noise_benefit_condition_boundary(thr, A)
    assert at["feasible"]
    assert at["radius"] == pytest.approx(0.0, abs=1e-12)
    assert at["min_cos"] == pytest.approx(1.0, abs=1e-12)
    prev = 1.0
    for mult in (1.01, 1.2, 2.0, 5.0, 20.0):
        info = noise_benefit_condition_boundary(thr * mult, A)
        assert info["feasible"]
        assert info["min_cos"] > 0.0            # never backwards
        assert info["min_cos"] < prev           # and monotonically opening
        prev = info["min_cos"]
    # brute-force cross-check at one interior point
    s_norm = thr * 2.0
    vs = np.linspace(0.0, 20.0, 800)
    th = np.linspace(0.0, 2.0 * np.pi, 800)
    V, T = np.meshgrid(vs, th, indexing="ij")
    f = V**2 - 2.0 * V * s_norm * np.cos(T) + 2.0 * A
    assert bool(np.any(f <= 0.0))


def test_theorem_r2_nonpositive_A_is_always_satisfiable():
    """R2: with A <= 0 the ball contains the origin, so (2) is vacuous.

    That is not a defect: when the target density is lower at the perturbed point,
    the sufficient condition is met trivially by *not perturbing*.  The
    interesting content of R2 lives entirely in the ``A > 0`` branch.
    """
    for A in (-0.5, -2.0, -10.0):
        for s_norm in (0.01, 0.5, 5.0):
            info = noise_benefit_condition_boundary(s_norm, A)
            assert info["feasible"]
            assert info["zero_reachable"]
            assert info["regime"] == "always"
            assert info["radius"] >= s_norm


def test_theorem_r4_false_alarm_control():
    """R4: on symmetric heavy-tailed H0 data the certificate does not over-fire."""
    rng = np.random.default_rng(15)
    n, trials = 512, 40
    alarms = 0
    for t in range(trials):
        x = rng.standard_t(4.0, size=n) / np.sqrt(2.0) * 0.7
        cert = detection_certificate(x, alpha=1e-2, n_signflip=4000, seed=t)
        if min(cert.p_value_signflip, cert.p_value_bernstein) <= 1e-2:
            alarms += 1
    assert alarms <= 3, f"{alarms}/{trials} false alarms at alpha=1e-2"


def test_theorem_r4_power_on_shifted_data():
    rng = np.random.default_rng(16)
    x = -0.3 + 0.7 * rng.standard_normal(512)
    cert = detection_certificate(x, alpha=1e-3, n_signflip=20_000)
    assert cert.reject_h0
    assert cert.mean_cos < 0
    assert cert.ci_high < 0.0


def test_theorem_r4b_orthogonal_spike_is_a_covariance_spike():
    """R4b: the spectrum monitor sees what the cosine monitor cannot."""
    s = make_stream("orthogonal_spike", n_steps=512, dim=64, seed=17)
    rep = spectral_report(s["eps"])
    assert rep.is_spiked
    cos = reverse_score(s["g_clean"], s["eps"])
    assert abs(float(np.mean(cos))) < 0.05          # invisible to the cosine test


def test_theorem_r4b_tracking_spike_is_strong_and_iso_spectral():
    """R4b caveat: a *gradient-tracking* reverse spike can be spectrally quiet."""
    s = make_stream("reverse_spike", n_steps=512, dim=64, seed=18, drift=0.15)
    assert float(np.mean(reverse_score(s["g_clean"], s["eps"]))) < -0.3
    rep = spectral_report(s["eps"])
    assert rep.boot_exceedance < 2.0


def test_random_matrix_edge_quantile_matches_ensemble():
    """The closed-form threshold reproduces a measured Gaussian ensemble.

    The target is ``lambda_max`` of the uncentred second moment ``X'X/n``; the
    Gram route computes ``XX'/n`` whose nonzero spectrum is identical, so no
    rescaling is applied.
    """
    rng = np.random.default_rng(19)
    n, d, ell = 256, 128, 0.25
    closed, _ = random_matrix_edge_quantile(ell, n, d, n_boot=0)
    tops = []
    for b in range(64):
        x = np.sqrt(ell) * rng.standard_normal((n, d))
        tops.append(float(np.linalg.eigvalsh(x @ x.T / n)[-1]))
    empirical = float(np.quantile(tops, 0.99))
    assert abs(closed / empirical - 1.0) < 0.15, f"{closed:.4f} vs {empirical:.4f}"


def test_rotation_null_preserves_energies():
    """The isotropisation null must not change the total energy of the stream."""
    rng = np.random.default_rng(20)
    e = rng.standard_normal((256, 32)) * 0.3
    floor, sd, ell = exchangeable_null_spectrum(e, n_draw=8, seed=0, n_jobs=1)
    assert abs(ell - float(np.sum(e**2) / (255 * 32))) < 0.02
    assert floor > 0.0 and sd >= 0.0


# ---------------------------------------------------------------------------
# 3. tool behaviour
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def baseline():
    clean = np.concatenate([
        gradient_stream(AttackSpec(family="clean", n_steps=512, dim=64, seed=s))
        ["eps"] for s in range(4)])
    return fit_baseline(clean)


@pytest.mark.parametrize("family", [f for f in FAMILIES if f != "clean"])
def test_every_attack_family_is_flagged(family, baseline):
    rep = audit_stream(make_stream(family, n_steps=512, dim=64, seed=21),
                       baseline=baseline)
    assert rep.verdict in ("watch", "suspect", "harmful"), \
        f"{family}: verdict was {rep.verdict}"
    assert rep.risk_score > 0.0


def test_clean_streams_are_not_flagged(baseline):
    verdicts = [audit_stream(make_stream("clean", n_steps=512, dim=64, seed=100 + s),
                             baseline=baseline).verdict for s in range(6)]
    assert verdicts.count("clean") >= 5, verdicts


def test_report_states_its_limitations(baseline):
    tracking = audit_stream(make_stream("reverse_spike", n_steps=512, dim=64,
                                        seed=22, drift=0.15), baseline=baseline)
    assert tracking.limitations, "a spectrally silent finding must say so"
    orth = audit_stream(make_stream("orthogonal_spike", n_steps=512, dim=64,
                                    seed=22), baseline=baseline)
    assert orth.limitations, "a cosine-invisible finding must say so"


def test_report_round_trips_through_json(baseline):
    rep = audit_stream(make_stream("reverse_spike", n_steps=256, dim=32, seed=23),
                       baseline=baseline)
    payload = json.loads(rep.to_json())
    assert payload["verdict"] == rep.verdict
    assert set(payload) >= {"noise_stats", "spectrum", "certificate", "monitors"}
    assert {m["name"] for m in payload["monitors"]} == {
        "cosine", "spectrum", "tail", "baseline"}


def test_auditor_without_clean_gradient_still_works():
    """An auditor that sees only g_hat must not crash and must report the gap."""
    stream = make_stream("reverse_spike", n_steps=256, dim=32, seed=24)
    stream.pop("g_clean")
    rep = audit_stream(stream)
    assert rep.verdict in ("clean", "watch", "suspect", "harmful")
    assert any("clean gradient" in l for l in rep.limitations)


def test_cli_synthetic_runs():
    out = subprocess.run(
        [sys.executable, "-m", "rnsafety.cli", "synthetic", "--seeds", "2",
         "--steps", "128", "--dim", "32"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True, text=True, timeout=600,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert "Summary table" in out.stdout
    assert "clean" in out.stdout


def test_cli_audit_round_trip(tmp_path):
    """Write a JSONL stream, audit it through the CLI, expect the exit code contract."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stream = make_stream("reverse_spike", n_steps=256, dim=24, seed=25)
    path = tmp_path / "run.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for gh, gc in zip(stream["g_hat"], stream["g_clean"]):
            fh.write(json.dumps({"grad_hat": gh.tolist(),
                                 "grad_clean": gc.tolist()}) + "\n")
    out = subprocess.run(
        [sys.executable, "-m", "rnsafety.cli", "audit", str(path)],
        cwd=root, capture_output=True, text=True, timeout=600,
    )
    assert "verdict" in out.stdout.lower()
    assert out.returncode == 2, "a harmful verdict must exit non-zero"


def test_baseline_monitor_auto_mode_detects_energy_inflation():
    """A pure magnitude attack is caught without a supplied baseline."""
    rng = np.random.default_rng(26)
    eps = 0.3 * rng.standard_normal((512, 32))
    eps[:64] *= 8.0                                  # 12.5% of steps inflated
    g_hat = rng.standard_normal((512, 32))
    stream = {"g_hat": g_hat, "g_clean": g_hat - eps, "eps": eps, "meta": {}}
    rep = audit_stream(stream)
    assert rep.monitor("baseline").fired
