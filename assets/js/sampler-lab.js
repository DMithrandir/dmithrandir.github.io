/*!
 * sampler-lab.js — 交互实验台的绘制与控件（依赖 sampler-lab-core.js）
 *
 * 页面里每个 <figure data-lab> 初始化一个实例：
 *   左：二维双峰目标上的采样轨迹  右/下：接受率与自相关时间 tau
 * 控件：盲注噪声 sigma_noise、三档对照模式、暂停 / 重置
 *
 * 数值内核在 sampler-lab-core.js；这里只管 DOM、canvas 和动画。
 */
(function () {
  'use strict';

  var core = window.MCMCLabCore;
  if (!core) return;

  var VIEW = { x0: -5.6, x1: 5.6, y0: -3.3, y1: 3.3 };
  var STEPS_PER_FRAME = 200;
  var MAX_STEPS = 100000;
  var TAU_EVERY = 5000;
  var TRAIL_DOTS = 240;

  var MODE_CHAINS = {
    blind: ['plain', 'blind'],
    matched: ['plain', 'blind', 'matched'],
    constrained: ['plain', 'constrained', 'equalmatch']
  };

  var NAME = {
    plain: '朴素 MH σ=1',
    blind: '盲注噪声',
    matched: '方差匹配',
    constrained: '约束噪声',
    equalmatch: '等步长 MH'
  };

  var MONO = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace';

  /* ---------- 小工具 ---------- */

  function parseColor(str) {
    var s = (str || '').trim();
    var m = /^#([0-9a-f]{3})$/i.exec(s);
    if (m) {
      return [
        parseInt(m[1][0] + m[1][0], 16),
        parseInt(m[1][1] + m[1][1], 16),
        parseInt(m[1][2] + m[1][2], 16)
      ];
    }
    m = /^#([0-9a-f]{6})$/i.exec(s);
    if (m) {
      return [
        parseInt(m[1].slice(0, 2), 16),
        parseInt(m[1].slice(2, 4), 16),
        parseInt(m[1].slice(4, 6), 16)
      ];
    }
    m = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i.exec(s);
    if (m) return [+m[1], +m[2], +m[3]];
    return [120, 110, 95];
  }

  function niceCeil(v) {
    if (!(v > 0)) return 1;
    var e = Math.pow(10, Math.floor(Math.log(v) / Math.LN10));
    var n = v / e;
    var m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
    return m * e;
  }

  function fmtSteps(n) {
    if (n >= 1000) {
      var k = Math.round(n / 100) / 10;
      return (k % 1 === 0 ? k.toFixed(0) : k.toFixed(1)) + 'k';
    }
    return String(Math.round(n));
  }

  function throttle(fn, ms) {
    var t = 0;
    return function () {
      var now = Date.now();
      if (now - t < ms) return;
      t = now;
      fn();
    };
  }

  /* ---------- 初始化 ---------- */

  function boot() {
    var nodes = document.querySelectorAll('[data-lab]');
    Array.prototype.forEach.call(nodes, initOne);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  function initOne(box) {
    var plot = box.querySelector('.lab-plot');
    var chart = box.querySelector('.lab-chart');
    var stats = box.querySelector('[data-stats]');
    var slider = box.querySelector('[data-ctl="noise"]');
    var output = box.querySelector('[data-out="noise"]');
    var toggle = box.querySelector('[data-act="toggle"]');
    var resetBtn = box.querySelector('[data-act="reset"]');
    var radios = box.querySelectorAll('input[type="radio"]');
    if (!plot || !chart) return;

    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var st = {
      sigmaN: slider ? parseFloat(slider.value) || 0 : 1,
      mode: box.getAttribute('data-mode') || 'matched',
      chains: [],
      history: {},
      nextTau: TAU_EVERY,
      measured: null,
      running: false,
      userPaused: !!reduce,
      raf: 0,
      bg: null,
      colors: null,
      fonts: null
    };

    function colors() {
      if (st.colors) return st.colors;
      var cs = window.getComputedStyle(box);
      function v(name, fallback) {
        var s = cs.getPropertyValue(name);
        return s && s.trim() ? s.trim() : fallback;
      }
      st.colors = {
        paper: v('--paper', '#f8f4ea'),
        ink: v('--ink', '#191510'),
        muted: v('--muted', '#776c5c'),
        rule: v('--rule', 'rgba(25,21,16,0.14)'),
        plain: v('--lab-plain', '#9a8f7f'),
        blind: v('--lab-blind', '#a83a2c'),
        matched: v('--lab-matched', '#3f6b66'),
        constrained: v('--lab-constrained', '#8a6d3b'),
        equalmatch: v('--lab-plain', '#9a8f7f')
      };
      return st.colors;
    }

    function font() {
      if (st.fonts) return st.fonts;
      var cs = window.getComputedStyle(box);
      var mono = cs.getPropertyValue('--mono');
      st.fonts = {
        mono: mono && mono.indexOf('"') >= 0 ? mono.trim() : MONO,
        sans: cs.fontFamily || 'sans-serif'
      };
      return st.fonts;
    }


    /* ---------- 背景：目标密度的对数级着色 ---------- */

    function buildBackground() {
      var rect = plot.getBoundingClientRect();
      if (!rect.width) return null;
      var w = Math.max(48, Math.round(rect.width * 0.55));
      var h = Math.max(36, Math.round(rect.height * 0.55));
      var cv = document.createElement('canvas');
      cv.width = w;
      cv.height = h;
      var ctx = cv.getContext('2d');
      if (!ctx) return null;
      var img = ctx.createImageData(w, h);
      var data = img.data;
      var C = colors();
      var paper = parseColor(C.paper);
      var accent = parseColor(C.blind);
      var lmax = core.logTarget(core.MU[0][0], core.MU[0][1]);
      var span = 4.6;

      for (var py = 0; py < h; py++) {
        var y = VIEW.y1 - ((py + 0.5) / h) * (VIEW.y1 - VIEW.y0);
        for (var px = 0; px < w; px++) {
          var x = VIEW.x0 + ((px + 0.5) / w) * (VIEW.x1 - VIEW.x0);
          var l = core.logTarget(x, y);
          var u = (l - (lmax - span)) / span;
          if (u < 0) u = 0;
          else if (u > 1) u = 1;
          u = Math.pow(u, 1.05);
          var t = 0.42 * u;
          var i = 4 * (py * w + px);
          data[i] = paper[0] + (accent[0] - paper[0]) * t;
          data[i + 1] = paper[1] + (accent[1] - paper[1]) * t;
          data[i + 2] = paper[2] + (accent[2] - paper[2]) * t;
          data[i + 3] = 255;
        }
      }
      ctx.putImageData(img, 0, 0);
      return cv;
    }

    /* ---------- 尺寸 ---------- */

    function fit(canvas) {
      var rect = canvas.getBoundingClientRect();
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      var w = Math.max(1, Math.round(rect.width * dpr));
      var h = Math.max(1, Math.round(rect.height * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        return true;
      }
      return false;
    }

    /* ---------- 轨迹 ---------- */

    function drawPlot() {
      var C = colors();
      if (fit(plot)) st.bg = null;
      var W = plot.width;
      var H = plot.height;
      if (!W || !H) return;
      var ctx = plot.getContext('2d');
      if (!ctx) return;
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, W, H);
      if (!st.bg) st.bg = buildBackground();
      if (st.bg) {
        ctx.imageSmoothingEnabled = true;
        ctx.drawImage(st.bg, 0, 0, W, H);
      }

      // 两峰中心
      ctx.strokeStyle = C.muted;
      ctx.globalAlpha = 0.5;
      ctx.lineWidth = Math.max(1, dpr);
      core.MU.forEach(function (m) {
        var p = toPx(m[0], m[1], W, H);
        ctx.beginPath();
        ctx.moveTo(p[0] - 4 * dpr, p[1]);
        ctx.lineTo(p[0] + 4 * dpr, p[1]);
        ctx.moveTo(p[0], p[1] - 4 * dpr);
        ctx.lineTo(p[0], p[1] + 4 * dpr);
        ctx.stroke();
      });
      ctx.globalAlpha = 1;

      // 起点
      var start = toPx(-4, 0, W, H);
      ctx.strokeStyle = C.muted;
      ctx.globalAlpha = 0.65;
      ctx.beginPath();
      ctx.arc(start[0], start[1], 2.4 * dpr, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;

      // 轨迹：朴素链在下层，且用虚线
      var order = st.chains.slice().sort(function (a, b) {
        return (a.kind === 'plain' ? 0 : 1) - (b.kind === 'plain' ? 0 : 1);
      });
      order.forEach(function (c) {
        var pts = [];
        c.forEachTail(function (x, y) {
          pts.push(toPx(x, y, W, H));
        });
        if (pts.length < 2) return;
        var stride = Math.max(1, Math.ceil(pts.length / TRAIL_DOTS));
        var color = C[c.kind] || C.muted;
        ctx.strokeStyle = color;
        ctx.lineWidth = Math.max(1, 1.35 * dpr);
        ctx.globalAlpha = 0.78;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.setLineDash(c.kind === 'plain' ? [3 * dpr, 4 * dpr] : []);
        ctx.beginPath();
        for (var i = 0; i < pts.length; i += stride) {
          if (i === 0) ctx.moveTo(pts[i][0], pts[i][1]);
          else ctx.lineTo(pts[i][0], pts[i][1]);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        var head = pts[pts.length - 1];
        ctx.globalAlpha = 1;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(head[0], head[1], 3.1 * dpr, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 0.9;
        ctx.fillStyle = C.paper;
        ctx.beginPath();
        ctx.arc(head[0], head[1], 1.1 * dpr, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      });

      // 边框
      ctx.strokeStyle = C.rule;
      ctx.lineWidth = Math.max(1, dpr);
      ctx.strokeRect(0.5 * dpr, 0.5 * dpr, W - dpr, H - dpr);
    }

    function toPx(x, y, W, H) {
      return [
        ((x - VIEW.x0) / (VIEW.x1 - VIEW.x0)) * W,
        H - ((y - VIEW.y0) / (VIEW.y1 - VIEW.y0)) * H
      ];
    }

    /* ---------- tau 曲线 ---------- */

    function drawChart() {
      fit(chart);
      var W = chart.width;
      var H = chart.height;
      if (!W || !H) return;
      var ctx = chart.getContext('2d');
      if (!ctx) return;
      var C = colors();
      var F = font();
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      var padL = 34 * dpr;
      var padR = 14 * dpr;
      var padT = 14 * dpr;
      var padB = 20 * dpr;
      var iw = Math.max(10, W - padL - padR);
      var ih = Math.max(10, H - padT - padB);

      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, W, H);

      var n = st.chains.length ? st.chains[0].iters : 0;
      var nMax = Math.max(TAU_EVERY * 2, n);
      var yMax = 1;
      st.chains.forEach(function (c) {
        (st.history[c.kind] || []).forEach(function (p) {
          if (isFinite(p.tau) && p.tau > yMax) yMax = p.tau;
        });
      });
      yMax = niceCeil(yMax * 1.18);

      function X(t) { return padL + (t / nMax) * iw; }
      function Y(tau) { return padT + ih - (tau / yMax) * ih; }

      // 网格
      ctx.strokeStyle = C.rule;
      ctx.lineWidth = Math.max(1, dpr * 0.8);
      [0, 0.5, 1].forEach(function (f) {
        var y = padT + ih - f * ih;
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(padL + iw, y);
        ctx.stroke();
      });
      [0, 0.5, 1].forEach(function (f) {
        var x = padL + f * iw;
        ctx.beginPath();
        ctx.moveTo(x, padT);
        ctx.lineTo(x, padT + ih);
        ctx.stroke();
      });

      // 刻度文字
      ctx.fillStyle = C.muted;
      ctx.font = (9.5 * dpr) + 'px ' + F.mono;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(Math.round(yMax)), padL - 6 * dpr, padT);
      ctx.fillText(String(Math.round(yMax / 2)), padL - 6 * dpr, padT + ih / 2);
      ctx.fillText('0', padL - 6 * dpr, padT + ih);

      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText('0', padL, padT + ih + 6 * dpr);
      ctx.fillText(fmtSteps(nMax / 2), padL + iw / 2, padT + ih + 6 * dpr);
      ctx.fillText(fmtSteps(nMax), padL + iw, padT + ih + 6 * dpr);

      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillStyle = C.muted;
      ctx.font = (10 * dpr) + 'px ' + F.mono;
      ctx.fillText('τ · 全历史 IPS，滞后 ≤ 256', padL + 2 * dpr, 1 * dpr);

      // 线
      st.chains.forEach(function (c) {
        var hist = st.history[c.kind] || [];
        if (hist.length < 2) return;
        var color = C[c.kind] || C.muted;
        ctx.strokeStyle = color;
        ctx.lineWidth = Math.max(1, (c.kind === 'plain' ? 1.2 : 1.8) * dpr);
        ctx.setLineDash(c.kind === 'plain' ? [3 * dpr, 3 * dpr] : []);
        ctx.beginPath();
        hist.forEach(function (p, i) {
          if (!isFinite(p.tau)) return;
          var px = X(p.n);
          var py = Y(p.tau);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.stroke();
        ctx.setLineDash([]);
        var last = hist[hist.length - 1];
        if (last && isFinite(last.tau)) {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(X(last.n), Y(last.tau), 2.1 * dpr, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      ctx.strokeStyle = C.rule;
      ctx.strokeRect(padL, padT, iw, ih);
    }

    /* ---------- 数字 ---------- */

    function drawStats() {
      if (!stats) return;
      var C = colors();
      var html = st.chains.map(function (c) {
        var acc = c.iters ? (100 * c.accepted / c.iters) : 0;
        var hist = st.history[c.kind] || [];
        var tau = hist.length ? hist[hist.length - 1].tau : NaN;
        return '<div class="lab-chip">' +
          '<span class="chip-dot" style="background:' + (C[c.kind] || C.muted) + '"></span>' +
          '<span class="chip-name">' + NAME[c.kind] + '</span>' +
          '<span class="chip-nums"><b>' + acc.toFixed(1) + '%</b> 接受 · τ <b>' +
          (isFinite(tau) ? tau.toFixed(1) : '—') + '</b></span>' +
          '</div>';
      });
      var n = st.chains.length ? st.chains[0].iters : 0;
      html.push('<div class="lab-chip lab-chip-meta">' +
        '<span class="chip-name">已跑</span>' +
        '<span class="chip-nums"><b>' + n.toLocaleString('en-US') + '</b> 步</span>' +
        '</div>');
      if (st.measured) {
        html.push('<div class="lab-chip lab-chip-meta">' +
          '<span class="chip-name">约束链实测步长</span>' +
          '<span class="chip-nums">σ <b>' + st.measured.mean.toFixed(2) + '</b></span>' +
          '</div>');
      }
      stats.innerHTML = html.join('');
    }

    /* ---------- 状态机 ---------- */

    function done() {
      return st.chains.length > 0 && st.chains[0].iters >= MAX_STEPS;
    }

    function reset() {
      stop();
      st.chains = [];
      st.history = {};
      st.nextTau = TAU_EVERY;
      st.measured = null;

      var kinds = MODE_CHAINS[st.mode] || MODE_CHAINS.matched;
      var sigmaFixed = core.SIGMA_PROP;
      if (st.mode === 'constrained') {
        var m = core.measureConstrainedStep(st.sigmaN, 4000, 4242, -4);
        st.measured = m;
        sigmaFixed = m.mean;
      }
      kinds.forEach(function (kind) {
        var c = core.makeChain(kind, {
          seed: 20260117,
          x0: -4,
          sigmaFixed: kind === 'equalmatch' ? sigmaFixed : undefined
        });
        c.key = kind;
        st.chains.push(c);
        st.history[kind] = [];
      });

      drawStats();
      drawPlot();
      drawChart();
      if (!st.userPaused) start();
      else if (toggle) toggle.textContent = done() ? '重跑' : '播放';
    }

    function checkpoint() {
      var n = st.chains.length ? st.chains[0].iters : 0;
      if (n < st.nextTau) return;
      st.chains.forEach(function (c) {
        st.history[c.kind].push({ n: c.iters, tau: c.tau() });
      });
      st.nextTau += TAU_EVERY;
    }

    function loop() {
      if (!st.running) return;
      var perFrame = reduce ? 2500 : STEPS_PER_FRAME;
      var cur = st.chains[0].iters;
      var batch = Math.min(perFrame, MAX_STEPS - cur);
      for (var i = 0; i < batch; i++) {
        for (var j = 0; j < st.chains.length; j++) st.chains[j].step(st.sigmaN);
      }
      checkpoint();
      drawPlot();
      drawChart();
      drawStats();
      if (done()) {
        stop();
        if (toggle) toggle.textContent = '重跑';
        return;
      }
      st.raf = window.requestAnimationFrame(loop);
    }

    function start() {
      if (st.running || !st.chains.length) return;
      if (done()) return;
      st.running = true;
      st.userPaused = false;
      if (toggle) toggle.textContent = '暂停';
      st.raf = window.requestAnimationFrame(loop);
    }

    function stop() {
      st.running = false;
      if (st.raf) window.cancelAnimationFrame(st.raf);
      st.raf = 0;
      if (toggle && !done()) toggle.textContent = '继续';
    }

    /* ---------- 绑定 ---------- */

    Array.prototype.forEach.call(radios, function (r) {
      r.checked = r.value === st.mode;
      r.addEventListener('change', function () {
        if (!r.checked) return;
        st.mode = r.value;
        reset();
      });
    });

    if (slider) {
      slider.addEventListener('input', function () {
        st.sigmaN = parseFloat(slider.value);
        if (output) output.textContent = st.sigmaN.toFixed(2);
      });
      slider.addEventListener('change', function () {
        st.sigmaN = parseFloat(slider.value);
        if (output) output.textContent = st.sigmaN.toFixed(2);
        reset();
      });
    }

    if (toggle) {
      toggle.addEventListener('click', function () {
        if (done()) {
          st.userPaused = false;
          reset();
          return;
        }
        if (st.running) {
          st.userPaused = true;
          stop();
        } else {
          st.userPaused = false;
          start();
        }
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        st.userPaused = false;
        reset();
      });
    }

    // 主题切换后重取颜色与背景
    if (window.MutationObserver) {
      var mo = new MutationObserver(function () {
        st.colors = null;
        st.fonts = null;
        st.bg = null;
        drawPlot();
        drawChart();
        drawStats();
      });
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    }

    // 尺寸变化
    var onResize = throttle(function () {
      st.bg = null;
      drawPlot();
      drawChart();
    }, 180);
    window.addEventListener('resize', onResize);
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(onResize);
      ro.observe(plot);
      ro.observe(chart);
    }

    // 滚出视口就停，回来再继续（用户手动暂停的除外）
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            if (!st.userPaused && !done()) start();
          } else {
            stop();
          }
        });
      }, { threshold: 0.2 });
      io.observe(box);
    }

    if (output) output.textContent = st.sigmaN.toFixed(2);
    reset();
    if (!st.userPaused) start();
  }
})();

