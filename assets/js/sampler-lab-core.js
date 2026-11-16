/*!
 * sampler-lab-core.js — 交互实验台的数值内核（无 DOM 依赖，node 下可 require 直接校验）
 *
 * 目标：二维等权双峰高斯  pi(x) = 0.5 N(mu1, s^2 I) + 0.5 N(mu2, s^2 I)
 * 提议：对称随机游走，基础步长 SIGMA_PROP（每个坐标）。
 *
 * 四组链（与 experiments.py / matched_step_control.py 的实现对齐）：
 *   plain       朴素 MH，x' = x + s
 *   blind       盲注噪声，x' = x + s + n            n ~ N(0, sigmaN^2 I)
 *   matched     方差匹配 MH，x' = x + s'            s' ~ N(0, (SIGMA_PROP^2 + sigmaN^2) I)
 *   constrained 约束噪声，n 按 Corollary 3 的条件拒绝采样：
 *                 |n|^2 - 2 n.s <= -2 SIGMA_PROP^2 A(x),
 *               A(x) = E_N[ ln pi(x+N) - ln pi(x) ]，用 8x8 高斯–埃尔米特张量积求积
 *   equalmatch  等步长朴素 MH，x' = x + s''，步长取约束链实测的 sd
 *
 * 常数说明：logTarget 省略了归一化常数（比值的计算不受影响），
 * 但 A(x) 是同一 x 上两点的差，同样不受影响。
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.MCMCLabCore = factory();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var MU = [[-2, 0], [2, 0]];
  var TARGET_SD = 0.75;
  var SIGMA_PROP = 1.0;
  var WEIGHT = 0.5;

  /* 8 点高斯–埃尔米特节点与权重（sum(w) = sqrt(pi)） */
  var GH_X = [
    -2.930637420257244, -1.981656756695843, -1.157193712446780, -0.381186990207322,
    0.381186990207322, 1.157193712446780, 1.981656756695843, 2.930637420257244
  ];
  var GH_W = [
    0.000199604072211, 0.017077983007, 0.207802325815, 0.661147012558,
    0.661147012558, 0.207802325815, 0.017077983007, 0.000199604072211
  ];

  function logAddExp(a, b) {
    var m = a > b ? a : b;
    return m + Math.log(Math.exp(a - m) + Math.exp(b - m));
  }

  function logTarget(x, y) {
    var twoK = 2 * TARGET_SD * TARGET_SD;
    var d1x = x - MU[0][0], d1y = y - MU[0][1];
    var d2x = x - MU[1][0], d2y = y - MU[1][1];
    return Math.log(WEIGHT) + logAddExp(
      -(d1x * d1x + d1y * d1y) / twoK,
      -(d2x * d2x + d2y * d2y) / twoK
    );
  }

  function density(x, y) {
    var k = TARGET_SD * TARGET_SD;
    var c = WEIGHT / (2 * Math.PI * k);
    var d1x = x - MU[0][0], d1y = y - MU[0][1];
    var d2x = x - MU[1][0], d2y = y - MU[1][1];
    return c * (
      Math.exp(-(d1x * d1x + d1y * d1y) / (2 * k)) +
      Math.exp(-(d2x * d2x + d2y * d2y) / (2 * k))
    );
  }

  /* ---------- 随机数：mulberry32 + Box–Muller ---------- */

  function rng(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function normal(r) {
    var u = r();
    var v = r();
    if (u < 1e-12) u = 1e-12;
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  /* ---------- A(x)：噪声带来的平均对数密度增量 ---------- */

  function aValue(x, y, sigmaN) {
    if (!(sigmaN > 0)) return 0;
    var scale = Math.SQRT2 * sigmaN;
    var base = logTarget(x, y);
    var acc = 0;
    for (var i = 0; i < 8; i++) {
      var xi = scale * GH_X[i];
      var wi = GH_W[i];
      for (var j = 0; j < 8; j++) {
        acc += wi * GH_W[j] * (logTarget(x + xi, y + scale * GH_X[j]) - base);
      }
    }
    // 二维张量积下 sum_i sum_j w_i w_j = (sqrt(pi))^2 = pi
    return acc / Math.PI;
  }

  /* ---------- 一条链 ---------- */

  var TAIL = 320;
  var MAX_TRIES = 32;
  var TAU_LAGS = 256;

  function makeChain(kind, opt) {
    opt = opt || {};
    var seed = opt.seed == null ? 20260117 : opt.seed;
    var sigmaFixed = opt.sigmaFixed == null ? SIGMA_PROP : opt.sigmaFixed;
    var L = opt.tauLags || TAU_LAGS;

    /* 在线自相关：lag[k] = sum_t x_t x_{t+k}，配一个长 L+1 的环形缓冲。
       这样 tau 用的是全部历史，代价是每步 O(L)，而不是每个检查点重扫一遍窗口
       ——双峰目标上窗口估计会被「这一窗里有几次跨峰」支配，抖动比信号大。 */
    var lag = new Float64Array(L + 1);
    var ring = new Float64Array(L + 1);
    var ri = 0;
    var sum = 0;
    var sumSq = 0;

    var rJump = rng(seed);
    var rAccept = rng(seed ^ 0x9E3779B9);
    var rNoise = rng(seed ^ 0x85EBCA6B);

    var tailX = new Float64Array(TAIL);
    var tailY = new Float64Array(TAIL);
    var tailHead = 0;
    var tailCount = 0;

    var chain = {
      kind: kind,
      x: opt.x0 == null ? -4 : opt.x0,
      y: opt.y0 == null ? 0 : opt.y0,
      iters: 0,
      accepted: 0,
      fallbacks: 0,
      samples: [],
      sumX: 0, sumY: 0, sqX: 0, sqY: 0
    };
    chain.lp = logTarget(chain.x, chain.y);

    chain.step = function (sigmaN) {
      var s = SIGMA_PROP;
      var sx = 0, sy = 0, nx = 0, ny = 0;
      var u = rAccept();

      if (kind === 'matched') {
        var sm = Math.sqrt(s * s + sigmaN * sigmaN);
        sx = sm * normal(rJump);
        sy = sm * normal(rJump);
      } else if (kind === 'equalmatch') {
        sx = sigmaFixed * normal(rJump);
        sy = sigmaFixed * normal(rJump);
      } else {
        sx = s * normal(rJump);
        sy = s * normal(rJump);
        if (kind === 'blind' && sigmaN > 0) {
          nx = sigmaN * normal(rNoise);
          ny = sigmaN * normal(rNoise);
        } else if (kind === 'constrained' && sigmaN > 0) {
          var A = aValue(chain.x, chain.y, sigmaN);
          var bound = -2 * s * s * A;
          if (bound > 0) {
            var found = false;
            for (var t = 0; t < MAX_TRIES; t++) {
              var cx = sigmaN * normal(rNoise);
              var cy = sigmaN * normal(rNoise);
              if (cx * cx + cy * cy - 2 * (cx * sx + cy * sy) <= bound) {
                nx = cx;
                ny = cy;
                found = true;
                break;
              }
            }
            if (!found) chain.fallbacks++;
          }
        }
      }

      var stepX = sx + nx;
      var stepY = sy + ny;
      chain.sumX += stepX;
      chain.sumY += stepY;
      chain.sqX += stepX * stepX;
      chain.sqY += stepY * stepY;
      chain.iters++;

      var xp = chain.x + stepX;
      var yp = chain.y + stepY;
      var lpp = logTarget(xp, yp);
      // 对称提议（含盲注与卷积写法）用 Metropolis 比值；
      // 约束组的提议对 x 不对称，这里沿用 experiments.py 的实现、不做 Hastings 校正。
      var acc = Math.log(u) < lpp - chain.lp;
      if (acc) {
        chain.x = xp;
        chain.y = yp;
        chain.lp = lpp;
        chain.accepted++;
      }

      chain.samples.push(chain.x);
      tailX[tailHead] = chain.x;
      tailY[tailHead] = chain.y;
      tailHead = (tailHead + 1) % TAIL;
      if (tailCount < TAIL) tailCount++;

      // 在线自相关累加
      var xv = chain.x;
      var upto = Math.min(L, chain.iters - 1);
      for (var k = 1; k <= upto; k++) {
        lag[k] += xv * ring[(ri - k + L + 1) % (L + 1)];
      }
      ring[ri] = xv;
      ri = (ri + 1) % (L + 1);
      sum += xv;
      sumSq += xv * xv;

      return acc;
    };

    chain.stepSd = function () {
      var n = chain.iters || 1;
      var mx = chain.sumX / n;
      var my = chain.sumY / n;
      return {
        x: Math.sqrt(Math.max(chain.sqX / n - mx * mx, 0)),
        y: Math.sqrt(Math.max(chain.sqY / n - my * my, 0))
      };
    };

    /* 全历史的 IPS 估计（滞后上限 L） */
    chain.tau = function () {
      var n = chain.iters;
      if (n < 64) return NaN;
      var mean = sum / n;
      var v = sumSq / n - mean * mean;
      if (!(v > 1e-12)) return 1;
      var tau = 0.5;
      var upto = Math.min(L, n - 1);
      for (var k = 1; k <= upto; k++) {
        var r = (lag[k] / (n - k) - mean * mean) / v;
        if (r <= 0) break;
        tau += r;
      }
      return Math.max(2 * tau, 1);
    };

    chain.forEachTail = function (cb) {
      var start = tailCount < TAIL ? 0 : tailHead;
      for (var i = 0; i < tailCount; i++) {
        var idx = (start + i) % TAIL;
        cb(tailX[idx], tailY[idx], i);
      }
    };

    return chain;
  }

  /* ---------- 诊断 ---------- */

  /* 积分自相关时间，初始正序列截断（与 core.py 的 IPS 规则一致） */
  function estimateTau(xs, maxLag) {
    var n = xs.length;
    if (n < 32) return NaN;
    var i, d;
    var mean = 0;
    for (i = 0; i < n; i++) mean += xs[i];
    mean /= n;
    var v = 0;
    for (i = 0; i < n; i++) {
      d = xs[i] - mean;
      v += d * d;
    }
    v /= n;
    if (v <= 1e-12) return 1;
    var L = Math.min(maxLag || 400, Math.floor(n / 4));
    var tau = 0.5;
    for (var k = 1; k <= L; k++) {
      var s = 0;
      for (i = 0; i < n - k; i++) s += (xs[i] - mean) * (xs[i + k] - mean);
      s /= (n - k) * v;
      if (s <= 0) break;
      tau += s;
    }
    return Math.max(2 * tau, 1);
  }

  /* 先跑一段约束链，量出它在这次 sigmaN 下的实际步长 sd */
  function measureConstrainedStep(sigmaN, nSteps, seed, x0) {
    var n = nSteps || 4000;
    var c = makeChain('constrained', { seed: seed == null ? 4242 : seed, x0: x0 == null ? -4 : x0 });
    for (var t = 0; t < n; t++) c.step(sigmaN);
    var sd = c.stepSd();
    return {
      x: sd.x,
      y: sd.y,
      mean: 0.5 * (sd.x + sd.y),
      fallbacks: c.fallbacks,
      steps: n
    };
  }

  return {
    MU: MU,
    TARGET_SD: TARGET_SD,
    SIGMA_PROP: SIGMA_PROP,
    logTarget: logTarget,
    density: density,
    aValue: aValue,
    rng: rng,
    normal: normal,
    makeChain: makeChain,
    estimateTau: estimateTau,
    measureConstrainedStep: measureConstrainedStep
  };
});
