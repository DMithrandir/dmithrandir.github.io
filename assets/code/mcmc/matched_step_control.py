"""Decisive control: is group D's burn-in advantage explained by its EFFECTIVE STEP SIZE alone?

Stage 1  run constrained MH from x0=-5, record the realised step sd along the path.
Stage 2  run PLAIN MH with sigma equal to that step sd (200 seeds) and compare the
         first-passage time with D's.

If plain MH at the matched step size reproduces D's steps-to-threshold, then the
"selection" adds nothing beyond a magnitude effect -- the honest attribution of E3.
"""
import numpy as np
import time

MEANS = np.array([-2.0, 2.0]); SIGS = np.array([0.75, 0.75]); W = np.array([0.5, 0.5])
def mixlog(x):
    x = np.asarray(x, float)
    c = W * np.exp(-0.5 * ((x[..., None] - MEANS) / SIGS) ** 2) / (SIGS * np.sqrt(2 * np.pi))
    return np.log(c.sum(-1) + 1e-300)

GH_X, GH_W = np.polynomial.hermite.hermgauss(48)
def A_grid(sn, lo=-30.0, hi=30.0, n=60001):
    g = np.linspace(lo, hi, n)
    ns = np.sqrt(2.0) * sn * GH_X
    lp0 = mixlog(g)
    acc = np.zeros_like(g)
    for k, w in zip(ns, GH_W):
        acc += w * (mixlog(g + k) - lp0)
    return g, acc / np.sqrt(np.pi)

def run_constrained(sn, n_iter=20000, seeds=120, x0=-5.0, prop=1.0, seed=4242):
    g, A = A_grid(sn)
    rng = np.random.default_rng(seed)
    x = np.full(seeds, float(x0)); lp = mixlog(x)
    hit = np.full(seeds, np.inf); steps = []
    Acur = np.interp(x, g, A)
    for t in range(n_iter):
        s = prop * rng.standard_normal(seeds)
        b = -2.0 * prop ** 2 * Acur
        n = np.zeros(seeds); found = ~(b > 0)
        if not found.all():
            for _ in range(32):
                if found.all():
                    break
                c = sn * rng.standard_normal(seeds)
                ok = (~found) & (c * c - 2.0 * c * s <= b)
                n = np.where(ok, c, n); found |= ok
        step = s + n
        steps.append(step.copy())
        xp = x + step; lpp = mixlog(xp)
        acc = np.log(rng.random(seeds) + 1e-300) < (lpp - lp)
        x = np.where(acc, xp, x); lp = np.where(acc, lpp, lp)
        Acur = np.interp(x, g, A)
        newly = (~np.isfinite(hit)) & (x > 1.25)
        hit[newly] = t
    hit[~np.isfinite(hit)] = n_iter
    sv = np.concatenate(steps)
    return float(sv.std()), float(hit.mean()), float(hit.std() / np.sqrt(seeds))

def run_plain(sigma, n_iter=20000, seeds=400, x0=-5.0, seed=777):
    rng = np.random.default_rng(seed)
    x = np.full(seeds, float(x0)); lp = mixlog(x)
    hit = np.full(seeds, np.inf)
    for t in range(n_iter):
        xp = x + sigma * rng.standard_normal(seeds); lpp = mixlog(xp)
        acc = np.log(rng.random(seeds) + 1e-300) < (lpp - lp)
        x = np.where(acc, xp, x); lp = np.where(acc, lpp, lp)
        newly = (~np.isfinite(hit)) & (x > 1.25)
        hit[newly] = t
    hit[~np.isfinite(hit)] = n_iter
    return float(hit.mean()), float(hit.std() / np.sqrt(seeds))

print("=" * 94)
print("M  IS D's BURN-IN ADVANTAGE JUST ITS EFFECTIVE STEP SIZE?")
print("=" * 94)
print(f"  {'sn':>5}{'sd_D(path)':>12}{'D steps':>10}{'plain sigma=sd_D':>20}{'plain steps':>13}")
t0 = time.time()
for sn in [0.25, 0.5, 1.0, 2.0, 3.0]:
    sdD, fpD, seD = run_constrained(sn)
    fpP, seP = run_plain(sdD)
    print(f"  {sn:>5}{sdD:>12.3f}{fpD:>10.2f}{sdD:>20.3f}{fpP:>13.2f}")
    print(f"        D se={seD:.2f}   plain se={seP:.2f}   difference = {fpD - fpP:+.2f}")
print(f"  [{time.time()-t0:.0f}s]")

print()
print("=" * 94)
print("M2  REFERENCE: the sigma=1 baseline and the blind-vs-matched pairs (200 seeds)")
print("=" * 94)
for lab, sig in [("A sigma=1", 1.0), ("C matched sn=1", np.sqrt(2.0)), ("sigma=2", 2.0)]:
    fp, se = run_plain(sig)
    print(f"  {lab:<20} sigma={sig:.3f}  steps={fp:7.2f} +- {se:.2f}")

print()
print("Reading: if 'D steps' and 'plain steps' agree within a few percent, then group D's")
print("first-passage improvement is a STEP-SIZE effect, and the paper's 'selection' label")
print("adds no explanatory content for E3.")
