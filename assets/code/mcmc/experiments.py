"""Paper experiments: the decisive four-group comparison and the noise sweep.

Groups (all with the same bimodal target and base proposal sd sigma=1):
  A. plain MH, proposal sd = 1
  B. blind noise: candidate = x + s + n, s~N(0,1), n~N(0,sigma_n^2)   [thesis Algorithm 2]
  C. variance-matched plain MH, proposal sd = sqrt(1+sigma_n^2)       [control implied by Prop. 1]
  D. constrained noise: n rejection-sampled per the Corollary 3 quadratic condition
       n^2 + 2 n (x_t - x) <= -2 sigma^2 A(x_t),   A(x_t) = E_N[ln pi(x_t+N) - ln pi(x_t)]
     computed by Gauss-Hermite quadrature on the BASE noise law N(0, sigma_n^2)
     (the "naive implementation" of the 2019 PRE paper).

Outputs: figures (PNG) + results JSON in ./output/ (created on first run).
"""
import json
import os
import sys
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (  # noqa: E402
    Gaussian1D, GaussianMixture1D, metropolis_hastings, noisy_metropolis_hastings,
    integrated_autocorrelation_time, empirical_kl,
)

FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
import os
os.makedirs(FIG, exist_ok=True)

GH_X, GH_W = np.polynomial.hermite.hermgauss(48)


def A_value(target, x_t, noise_sd):
    """A(x_t) = E_N[ ln pi(x_t + N) - ln pi(x_t) ], N ~ N(0, noise_sd^2)."""
    ns = np.sqrt(2.0) * noise_sd * GH_X
    lp = target.logpdf((x_t + ns).reshape(-1, 1))
    lp0 = float(target.logpdf(np.array([[x_t]]))[0])
    return float(np.sum(GH_W * (lp - lp0)) / np.sqrt(np.pi))


def constrained_mh(target, n_iter, x0, proposal_sd, noise_sd, rng,
                   max_tries=32, record=False):
    """MH with noise rejection-sampled to satisfy the Corollary-3 condition."""
    x = float(x0)
    chain = np.empty(n_iter)
    accepted = np.zeros(n_iter, dtype=bool)
    lp = float(target.logpdf(np.array([[x]]))[0])
    ns_used, ss_used = [], []
    n_fallback = 0
    for t in range(n_iter):
        s = proposal_sd * rng.standard_normal()
        A = A_value(target, x, noise_sd)
        bound = -2.0 * proposal_sd ** 2 * A  # >= 0 whenever A <= 0
        n = 0.0
        if bound > 0:
            found = False
            for _ in range(max_tries):
                cand = noise_sd * rng.standard_normal()
                if cand * cand + 2.0 * cand * (x - (x + s)) <= bound:
                    # i.e. n^2 - 2 n s <= bound  (x_t - x = -s)
                    n = cand
                    found = True
                    break
            if not found:
                n_fallback += 1
        xp = x + s + n
        lpp = float(target.logpdf(np.array([[xp]]))[0])
        if np.log(rng.random() + 1e-300) < lpp - lp:
            x, lp = xp, lpp
            accepted[t] = True
        chain[t] = x
        if record and t % 25 == 0:
            ns_used.append(n)
            ss_used.append(s)
    out = {"chain": chain, "accepted": accepted,
           "accept_rate": float(accepted.mean()),
           "noise_fallback_frac": n_fallback / n_iter}
    if record:
        out["noise"] = np.array(ns_used)
        out["jump"] = np.array(ss_used)
    return out


def first_passage(chain, level):
    idx = np.argmax(chain > level)
    return int(idx) if chain[idx] > level else len(chain)


def main():
    tgt = GaussianMixture1D((-2.0, 2.0), (0.75, 0.75))
    SIG, NSIG = 1.0, 1.0
    matched = float(np.sqrt(SIG ** 2 + NSIG ** 2))
    lo, hi = -8.0, 8.0

    # ------------------------------------------------------------------ E1
    print("E1: four-group comparison ...", flush=True)
    N1 = 60000
    checkpoints = np.unique(np.round(
        np.logspace(np.log10(200), np.log10(N1), 28)).astype(int))
    kl_curves, taus, accs = {}, {}, {}
    groups = {
        "A plain MH (sd=1)": lambda s: metropolis_hastings(
            tgt, N1, 0.0, SIG, rng=np.random.default_rng(s)),
        "B blind noise (sd=1, n=1)": lambda s: noisy_metropolis_hastings(
            tgt, N1, 0.0, SIG, NSIG, noise_kind="state",
            rng=np.random.default_rng(s)),
        "C matched MH (sd=sqrt2)": lambda s: metropolis_hastings(
            tgt, N1, 0.0, matched, rng=np.random.default_rng(s)),
    }
    for name, fn in groups.items():
        kls, ttaus, aaccs = [], [], []
        for seed in range(8):
            r = fn(1000 + seed)
            c = r.chain[:, 0]
            kls.append([empirical_kl(r.chain[:k], tgt, lo, hi, 256) for k in checkpoints])
            ttaus.append(integrated_autocorrelation_time(c))
            aaccs.append(r.accept_rate)
        kl_curves[name] = np.mean(kls, axis=0)
        taus[name] = (float(np.mean(ttaus)), float(np.std(ttaus)))
        accs[name] = float(np.mean(aaccs))
        print(f"  {name}: accept={accs[name]:.3f} tau={taus[name][0]:.1f}", flush=True)

    # constrained group (slower, fewer seeds but still 6)
    kls, ttaus, aaccs = [], [], []
    mech = None
    for seed in range(6):
        r = constrained_mh(tgt, N1, 0.0, SIG, NSIG,
                           np.random.default_rng(2000 + seed),
                           record=(seed == 0))
        c = r["chain"]
        c2 = c.reshape(-1, 1)
        kls.append([empirical_kl(c2[:k], tgt, lo, hi, 256) for k in checkpoints])
        ttaus.append(integrated_autocorrelation_time(c))
        aaccs.append(r["accept_rate"])
        if seed == 0:
            mech = r
    name = "D constrained noise (sd=1, n=1)"
    kl_curves[name] = np.mean(kls, axis=0)
    taus[name] = (float(np.mean(ttaus)), float(np.std(ttaus)))
    accs[name] = float(np.mean(aaccs))
    print(f"  {name}: accept={accs[name]:.3f} tau={taus[name][0]:.1f} "
          f"fallback={mech['noise_fallback_frac']:.3f}", flush=True)

    plt.figure(figsize=(7.2, 4.6))
    for name, curve in kl_curves.items():
        plt.plot(checkpoints, curve, label=name, lw=1.8)
    plt.xscale("log")
    plt.xlabel("iteration t")
    plt.ylabel(r"KL( empirical marginal $\Vert$ target )  [nats]")
    plt.title("E1  Running KL to target: four groups (bimodal mixture)")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(FIG + r"\e1_kl_decay.png", dpi=150)
    plt.close()

    # mechanism evidence: selected noise vs jump direction
    plt.figure(figsize=(6.4, 4.2))
    plt.scatter(mech["jump"], mech["noise"], s=4, alpha=0.35)
    plt.xlabel("jump s")
    plt.ylabel("accepted noise n")
    plt.title("E1-mech  Constrained noise is selected along the jump direction")
    plt.tight_layout()
    plt.savefig(FIG + r"\e1_mechanism.png", dpi=150)
    plt.close()
    corr = float(np.corrcoef(mech["jump"], mech["noise"])[0, 1])
    print(f"  corr(selected noise, jump) = {corr:.3f}", flush=True)

    # ------------------------------------------------------------------ E2
    print("E2: Gaussian anatomy ...", flush=True)
    mu, sd_pi, sd_q, x_t = 2.0, 1.0, 1.0, 0.0
    d_t = 0.5 * (np.log(sd_q ** 2 / sd_pi ** 2)
                 + (sd_pi ** 2 + (x_t - mu) ** 2) / sd_q ** 2 - 1)
    ms = np.linspace(-1.0, 3.0, 400)
    plt.figure(figsize=(7.0, 4.6))
    for v, style in [(0.01, "-"), (0.25, "--"), (1.0, ":")]:
        Ed = 0.5 * (np.log(sd_q ** 2 / sd_pi ** 2)
                    + (sd_pi ** 2 + v + (x_t + ms - mu) ** 2) / sd_q ** 2 - 1)
        plt.plot(ms, Ed, style, label=f"Var N = {v}")
    plt.axhline(d_t, color="k", lw=1.2, ls="-.")
    plt.annotate(f"$d_t$ = {d_t:.2f} (no-noise)", (0.02, d_t + 0.04))
    plt.axvline(0.0, color="gray", lw=0.8)
    plt.axvline(mu - x_t, color="gray", lw=0.8)
    plt.annotate("zero-mean noise\n(always harmful)", (0.03, 3.4))
    plt.annotate("mode-centering\nnoise (oracle)", (2.03, 0.15))
    plt.xlabel("E[N]")
    plt.ylabel(r"$E_N[d_t(N)]$  [nats]")
    plt.title("E2  Gaussian anatomy: benefit iff  2(x_t - mu) E[N] + E[N^2] <= 0")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG + r"\e2_gaussian_anatomy.png", dpi=150)
    plt.close()

    # ------------------------------------------------------------------ E3
    print("E3: noise-level sweep, steps-to-threshold ...", flush=True)
    X0, LEVEL, NMAX, SEEDS = -5.0, 1.25, 20000, 200
    grid = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]
    res = {"blind": [], "matched": [], "constrained": []}
    for nsig in grid:
        fp_b, fp_m, fp_c = [], [], []
        sm = float(np.sqrt(SIG ** 2 + nsig ** 2))
        for seed in range(SEEDS):
            r = noisy_metropolis_hastings(
                tgt, NMAX, X0, SIG, nsig, noise_kind="state",
                rng=np.random.default_rng(100000 + seed))
            fp_b.append(first_passage(r.chain[:, 0], LEVEL))
            r = metropolis_hastings(
                tgt, NMAX, X0, sm, rng=np.random.default_rng(100000 + seed))
            fp_m.append(first_passage(r.chain[:, 0], LEVEL))
        for seed in range(60):  # constrained is pricier
            r = constrained_mh(tgt, NMAX, X0, SIG, nsig,
                               np.random.default_rng(300000 + seed))
            fp_c.append(first_passage(r["chain"], LEVEL))
        res["blind"].append((float(np.mean(fp_b)), float(np.std(fp_b) / np.sqrt(len(fp_b)))))
        res["matched"].append((float(np.mean(fp_m)), float(np.std(fp_m) / np.sqrt(len(fp_m)))))
        res["constrained"].append((float(np.mean(fp_c)), float(np.std(fp_c) / np.sqrt(len(fp_c)))))
        print(f"  sigma_n={nsig}: blind={np.mean(fp_b):.0f} matched={np.mean(fp_m):.0f} "
              f"constrained={np.mean(fp_c):.0f}", flush=True)

    plt.figure(figsize=(7.0, 4.6))
    for key, lab, mk in [("blind", "blind noise", "o"),
                         ("matched", "variance-matched plain MH", "s"),
                         ("constrained", "constrained noise", "^")]:
        m = np.array([v[0] for v in res[key]])
        e = np.array([v[1] for v in res[key]])
        plt.errorbar(grid, m, yerr=e, marker=mk, ms=4, lw=1.6, capsize=3, label=lab)
    plt.xlabel(r"noise sd $\sigma_n$")
    plt.ylabel("mean steps to reach opposite mode")
    plt.title("E3  Burn-in: steps from x0=-5 to x>1.25 (bimodal target)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG + r"\e3_noise_sweep.png", dpi=150)
    plt.close()

    # ------------------------------------------------------------------ dump
    out = {
        "target": str(tgt.name),
        "E1": {
            "checkpoints": checkpoints.tolist(),
            "kl_curves": {k: [float(v) for v in vv] for k, vv in kl_curves.items()},
            "tau": {k: list(v) for k, v in taus.items()},
            "accept": accs,
            "mech_corr": corr,
            "fallback_frac": mech["noise_fallback_frac"],
        },
        "E2": {"mu": mu, "sd_pi": sd_pi, "sd_q": sd_q, "x_t": x_t, "d_t": d_t},
        "E3": {"grid": grid, "results": {k: [list(v) for v in vv] for k, vv in res.items()},
               "x0": X0, "level": LEVEL, "seeds": SEEDS},
    }
    with open(FIG + r"\results.json", "w") as f:
        json.dump(out, f, indent=1)
    print("done. figures + results.json in", FIG)


if __name__ == "__main__":
    main()
