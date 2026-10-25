"""Reference implementations for the thesis reproduction.

Implements:
  * Metropolis-Hastings with a general symmetric random-walk proposal
  * Noisy MCMC (N-MCMC) following Franzke & Kosko / the thesis's Algorithm 2
  * Expectation-Maximization and the Noisy EM (N-EM) algorithm
  * Convergence diagnostics: KL divergence to the target, ESS, autocorrelation
    time, mean-squared error of the chain mean, and the empirical validity
    check for the thesis's "noise inequality".

The module is deliberately dependency-light: numpy + scipy only, so the whole
reproduction runs from a clean environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np

# ----------------------------------------------------------------------------
# Target distributions
# ----------------------------------------------------------------------------


class Target:
    """Base class: a 1-D (or vectorised) unnormalised log-density on R^d."""

    name: str = "target"
    d: int = 1

    def logpdf(self, x: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def pdf(self, x: np.ndarray) -> np.ndarray:
        return np.exp(self.logpdf(x))

    def sample(self, n: int, rng: np.random.Generator) -> np.ndarray:
        raise NotImplementedError

    def grid(self, lo: float, hi: float, n: int) -> np.ndarray:
        return np.linspace(lo, hi, n).reshape(-1, 1)


class Gaussian1D(Target):
    """Univariate normal N(mu, sigma^2) treated as a 1-D chain."""

    def __init__(self, mu: float = 0.0, sigma: float = 1.0):
        self.mu, self.sigma = float(mu), float(sigma)
        self.name = f"Gaussian(mu={mu}, sigma={sigma})"

    def logpdf(self, x):
        x = np.atleast_2d(np.asarray(x, dtype=float)).reshape(-1, 1)
        return -0.5 * ((x[:, 0] - self.mu) / self.sigma) ** 2 - np.log(
            self.sigma * np.sqrt(2 * np.pi)
        )

    def sample(self, n, rng):
        return (self.mu + self.sigma * rng.standard_normal((n, 1)))


class GaussianMixture1D(Target):
    """Two-component Gaussian mixture -- the bimodal test case."""

    def __init__(
        self,
        means: Sequence[float] = (-2.0, 2.0),
        sigmas: Sequence[float] = (0.75, 0.75),
        weights: Optional[Sequence[float]] = None,
    ):
        self.means = np.asarray(means, dtype=float)
        self.sigmas = np.asarray(sigmas, dtype=float)
        if weights is None:
            weights = np.ones_like(self.means) / len(self.means)
        self.weights = np.asarray(weights, dtype=float)
        self.name = "GaussianMixture(means=%s, sigmas=%s, w=%s)" % (
            list(self.means), list(self.sigmas), list(self.weights),
        )

    def logpdf(self, x):
        x = np.atleast_2d(np.asarray(x, dtype=float)).reshape(-1, 1)
        comp = (
            self.weights[None, :]
            * np.exp(
                -0.5 * ((x - self.means[None, :]) / self.sigmas[None, :]) ** 2
            )
            / (self.sigmas[None, :] * np.sqrt(2 * np.pi))
        )
        return np.log(comp.sum(axis=1) + 1e-300)

    def sample(self, n, rng):
        idx = rng.choice(len(self.means), size=n, p=self.weights)
        return (self.means[idx] + self.sigmas[idx] * rng.standard_normal(n)).reshape(-1, 1)


# ----------------------------------------------------------------------------
# Relative entropy helpers
# ----------------------------------------------------------------------------


def kl_divergence(
    p_unnorm: Callable[[np.ndarray], np.ndarray],
    q_unnorm: Callable[[np.ndarray], np.ndarray],
    lo: float,
    hi: float,
    n: int = 4001,
) -> float:
    """Kullback-Leibler divergence D(p || q) on a fine 1-D grid.

    Both inputs are unnormalised densities; the grid must cover essentially all
    of p's mass so the trapezoid rule is accurate.
    """
    xs = np.linspace(lo, hi, n)
    pts = xs.reshape(-1, 1)
    p = np.asarray(p_unnorm(pts), dtype=float)
    q = np.asarray(q_unnorm(pts), dtype=float)
    # normalise
    Zp = np.trapezoid(p, xs) if hasattr(np, "trapezoid") else np.trapz(p, xs)
    Zq = np.trapezoid(q, xs) if hasattr(np, "trapezoid") else np.trapz(q, xs)
    p = p / Zp
    q = q / Zq
    mask = p > 1e-14
    integrand = np.zeros_like(p)
    integrand[mask] = p[mask] * np.log(p[mask] / np.maximum(q[mask], 1e-300))
    trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    return float(trapz(integrand, xs))


def empirical_kl(xs: np.ndarray, target: Target, lo: float, hi: float, n: int = 512) -> float:
    """KL( empirical histogram || target ) on a common grid, in nats.

    This is the direct numerical analogue of the thesis's relative-entropy
    pseudo-distance between the simulated chain's marginal and the equilibrium
    pdf pi.
    """
    edges = np.linspace(lo, hi, n + 1)
    counts, _ = np.histogram(xs[:, 0], bins=edges)
    p = counts / max(counts.sum(), 1)
    centres = 0.5 * (edges[:-1] + edges[1:])
    q = target.pdf(centres.reshape(-1, 1))
    Zq = q.sum()
    if Zq <= 0:
        return float("nan")
    q = q / Zq
    mask = p > 0
    return float(np.sum(p[mask] * np.log(p[mask] / np.maximum(q[mask], 1e-300))))


# ----------------------------------------------------------------------------
# Samplers
# ----------------------------------------------------------------------------


@dataclass
class MHResult:
    chain: np.ndarray
    accepted: np.ndarray
    logpdf: np.ndarray
    noise: Optional[np.ndarray] = None
    n_benefit: int = 0
    n_benefit_tested: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def accept_rate(self) -> float:
        return float(self.accepted.mean()) if len(self.accepted) else float("nan")


def metropolis_hastings(
    target: Target,
    n_iter: int,
    x0: float,
    proposal_sd: float = 1.0,
    rng: Optional[np.random.Generator] = None,
    burn_in: int = 0,
) -> MHResult:
    """Symmetric random-walk Metropolis-Hastings.

    Proposal x' ~ N(x, proposal_sd^2); acceptance min(1, pi(x')/pi(x)).
    """
    rng = rng or np.random.default_rng()
    x = float(x0)
    chain = np.empty((n_iter, 1))
    accepted = np.zeros(n_iter, dtype=bool)
    lps = np.empty(n_iter)
    lp = float(target.logpdf(np.array([[x]]))[0])
    for t in range(n_iter):
        xp = x + proposal_sd * rng.standard_normal()
        lpp = float(target.logpdf(np.array([[xp]]))[0])
        acc = np.log(rng.random() + 1e-300) < (lpp - lp)
        if acc:
            x, lp = xp, lpp
        chain[t, 0] = x
        accepted[t] = acc
        lps[t] = lp
    start = min(burn_in, n_iter)
    return MHResult(chain=chain[start:], accepted=accepted[start:], logpdf=lps[start:])


def noisy_metropolis_hastings(
    target: Target,
    n_iter: int,
    x0: float,
    proposal_sd: float = 1.0,
    noise_sd: float = 0.5,
    noise_kind: str = "state",
    rng: Optional[np.random.Generator] = None,
    burn_in: int = 0,
    record_noise: bool = True,
) -> MHResult:
    """Noisy MCMC (N-MCMC).

    ``noise_kind`` selects where the injected noise enters, matching the two
    readings of the published algorithm:

    ``"state"``
        Propose x' from the base jump pdf q(.|x), then perturb the *candidate
        state*: x~ = x' + n with n ~ N(0, noise_sd^2), and run the standard
        Metropolis test on pi(x~)/pi(x).  This is the reading in which the
        noise function enters the jump density as q_n(x'|x) = q(x'-x-n), i.e.
        the noisy jump pdf is the base jump pdf shifted by the noise draw.

    ``"proposal_pdf"``
        Keep the proposal draw x' = x + s with s ~ N(0, proposal_sd^2), but
        evaluate the acceptance ratio using the *noisy* jump density evaluated
        at the noise-shifted argument, q(x' - x - n), as the thesis's Algorithm
        2 suggests.

    Both routes are recorded so the empirical study can report which (if any)
    reproduces an actual speed-up.
    """
    rng = rng or np.random.default_rng()
    x = float(x0)
    chain = np.empty((n_iter, 1))
    accepted = np.zeros(n_iter, dtype=bool)
    lps = np.empty(n_iter)
    noise_draws = np.empty(n_iter) if record_noise else None
    lp = float(target.logpdf(np.array([[x]]))[0])
    n_benefit = 0
    n_tested = 0

    def base_logq(delta: float) -> float:
        """log of the symmetric Gaussian jump pdf evaluated at a step delta."""
        return -0.5 * (delta / proposal_sd) ** 2 - np.log(
            proposal_sd * np.sqrt(2 * np.pi)
        )

    for t in range(n_iter):
        n = noise_sd * rng.standard_normal()
        if record_noise:
            noise_draws[t] = n

        if noise_kind == "state":
            s = proposal_sd * rng.standard_normal()
            xp = x + s + n
            lpp = float(target.logpdf(np.array([[xp]]))[0])
            # symmetric proposal: the Metropolis ratio is pi(xp)/pi(x)
            log_ratio = lpp - lp
            # noise benefit test: does the noisy jump beat the noiseless one?
            n_tested += 1
            if base_logq(s + n) >= base_logq(s):
                n_benefit += 1
        elif noise_kind == "proposal_pdf":
            s = proposal_sd * rng.standard_normal()
            xp = x + s
            lpp = float(target.logpdf(np.array([[xp]]))[0])
            # noisy jump density evaluated at the noise-shifted step,
            # against the plain jump density at the actual step
            log_ratio = lp - lpp + base_logq(s - n) - base_logq(s)
            n_tested += 1
            if base_logq(s - n) >= base_logq(s):
                n_benefit += 1
        else:
            raise ValueError(f"unknown noise_kind {noise_kind!r}")

        acc = np.log(rng.random() + 1e-300) < log_ratio
        if acc:
            x, lp = xp, lpp
        chain[t, 0] = x
        accepted[t] = acc
        lps[t] = lp

    start = min(burn_in, n_iter)
    return MHResult(
        chain=chain[start:],
        accepted=accepted[start:],
        logpdf=lps[start:],
        noise=None if noise_draws is None else noise_draws[start:],
        n_benefit=n_benefit,
        n_benefit_tested=n_tested,
    )


# ----------------------------------------------------------------------------
# Diagnostics
# ----------------------------------------------------------------------------


def running_kl(
    chain: np.ndarray,
    target: Target,
    lo: float,
    hi: float,
    checkpoints: Sequence[int],
    n_bins: int = 256,
) -> np.ndarray:
    """KL( running empirical marginal || target ) measured at checkpoints."""
    out = np.empty(len(checkpoints))
    for i, k in enumerate(checkpoints):
        k = int(min(k, len(chain)))
        out[i] = empirical_kl(chain[:k], target, lo, hi, n_bins)
    return out


def autocorr(x: np.ndarray, max_lag: int) -> np.ndarray:
    x = np.asarray(x, dtype=float).ravel()
    x = x - x.mean()
    n = len(x)
    var = np.dot(x, x) / n
    if var <= 0:
        return np.ones(max_lag + 1)
    ac = np.empty(max_lag + 1)
    for k in range(max_lag + 1):
        ac[k] = np.dot(x[: n - k], x[k:]) / ((n - k) * var)
    return ac


def integrated_autocorrelation_time(x: np.ndarray, max_lag: Optional[int] = None) -> float:
    """Integrated autocorrelation time tau via the initial-positive-sequence rule."""
    x = np.asarray(x, dtype=float).ravel()
    n = len(x)
    if max_lag is None:
        max_lag = min(n // 2, 2000)
    ac = autocorr(x, max_lag)
    tau = 0.5
    for k in range(1, max_lag + 1):
        if ac[k] <= 0:
            break
        tau += ac[k]
    return float(max(2.0 * tau, 1.0))


def effective_sample_size(x: np.ndarray) -> float:
    """ESS = n / tau, where tau is the integrated autocorrelation time."""
    x = np.asarray(x, dtype=float).ravel()
    return float(len(x) / integrated_autocorrelation_time(x))


def running_mean_mse(chain: np.ndarray, true_mean: float) -> np.ndarray:
    """Squared error of the running sample mean against the true mean."""
    return (np.cumsum(chain[:, 0]) / np.arange(1, len(chain) + 1) - true_mean) ** 2


def gelman_rubin(chains: np.ndarray) -> float:
    """Gelman-Rubin R-hat across m chains given as an (m, n) array."""
    m, n = chains.shape
    if m < 2:
        return float("nan")
    means = chains.mean(axis=1)
    vars_ = chains.var(axis=1, ddof=1)
    W = vars_.mean()
    B = n * means.var(ddof=1)
    var_hat = (n - 1) / n * W + B / n
    return float(np.sqrt(var_hat / W))
