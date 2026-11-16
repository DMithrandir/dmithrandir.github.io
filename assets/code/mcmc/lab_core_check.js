/* 交互实验台数值内核的独立校验：node assets/code/mcmc/lab_core_check.js
 *
 * 校验 1  目标密度与 A(x) 的符号
 * 校验 2  sigmaN = 0 时，盲注链与朴素链逐点同轨迹（同一随机流）
 * 校验 3  提议步长的实测 sd：盲注 / 方差匹配 / 等步长
 * 校验 4  60k 步下四组对照的接受率与自相关时间（这是网页实验台要复现的结论）
 */
const path = require('path');
const core = require(path.resolve(__dirname, '..', '..', 'js', 'sampler-lab-core.js'));

const SEED = 20260117;
const N = 60000;
let fails = 0;
function check(label, ok, detail) {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? '  ' + detail : ''}`);
  if (!ok) fails++;
}

/* 1. 密度与 A(x) */
const lpA = core.logTarget(-2, 0);
const lpMid = core.logTarget(0, 0);
const lpFar = core.logTarget(0, 2.6);
check('log pi 在峰心最高', lpA > lpMid && lpMid > lpFar,
  `lpA=${lpA.toFixed(2)} lpMid=${lpMid.toFixed(2)} lpFar=${lpFar.toFixed(2)}`);
check('密度在峰心归一化合理', Math.abs(core.density(-2, 0) - 0.5 / (2 * Math.PI * 0.5625)) < 1e-6,
  `rho(峰心)=${core.density(-2, 0).toFixed(6)}`);
// 坐在峰心时，把噪声云摊开平均只会更低 -> A < 0（约束因此在峰附近生效）；
// 在两峰之间（鞍点）与远尾，log pi 是凸的，A 反而 > 0 —— 那一片约束退化成 n = 0。
const aTail = core.aValue(0, 2.6, 1.0);
const aMode = core.aValue(-2, 0, 1.0);
const aMid = core.aValue(0, 0, 1.0);
check('A(峰心) < 0（约束真正生效的区域）', aMode < 0, `A(峰心)=${aMode.toFixed(3)}`);
check('A(鞍点/远尾) > 0（凸区，拒绝采样退化成不加噪）',
  aMid > 0 && aTail > 0,
  `A(中点)=${aMid.toFixed(3)}  A(0,2.6)=${aTail.toFixed(3)}`);

/* 2. sigmaN = 0：盲注链与朴素链应当逐点相同 */
const plain0 = core.makeChain('plain', { seed: SEED });
const blind0 = core.makeChain('blind', { seed: SEED });
for (let t = 0; t < 5000; t++) { plain0.step(0); blind0.step(0); }
let identical = plain0.samples.length === blind0.samples.length;
for (let i = 0; identical && i < plain0.samples.length; i++) {
  if (plain0.samples[i] !== blind0.samples[i]) identical = false;
}
check('sigmaN=0 时盲注链 ≡ 朴素链（逐点）', identical,
  `accept ${plain0.accepted}/${plain0.iters} vs ${blind0.accepted}/${blind0.iters}`);

/* 3. 实测提议步长 */
function chains(sigmaN) {
  const kinds = ['plain', 'blind', 'matched', 'constrained', 'equalmatch'];
  const meas = core.measureConstrainedStep(sigmaN, 6000, 4242, -4);
  const out = {};
  kinds.forEach(k => {
    const opt = { seed: SEED };
    if (k === 'equalmatch') opt.sigmaFixed = meas.mean;
    out[k] = core.makeChain(k, opt);
  });
  for (let t = 0; t < N; t++) kinds.forEach(k => out[k].step(sigmaN));
  return { chains: out, meas };
}

const sig = 1.0;
const run = chains(sig);
const C = run.chains;
const sd = k => { const s = C[k].stepSd(); return 0.5 * (s.x + s.y); };
console.log(`\n实测每坐标提议步长 sd（sigmaN=${sig}）`);
check('盲注链步长 ≈ sqrt(1+1) = 1.414', Math.abs(sd('blind') - Math.SQRT2) < 0.03, `sd=${sd('blind').toFixed(3)}`);
check('方差匹配链步长 ≈ 1.414', Math.abs(sd('matched') - Math.SQRT2) < 0.01, `sd=${sd('matched').toFixed(3)}`);
check('约束链步长 > 1（噪声被拉向跳跃方向，等步长控制由它决定）', sd('constrained') > 1.05,
  `sd=${sd('constrained').toFixed(3)}（暖机实测 ${run.meas.mean.toFixed(3)}）`);
check('等步长控制链的步长 ≈ 约束链暖机实测值', Math.abs(sd('equalmatch') - run.meas.mean) < 0.02,
  `sd=${sd('equalmatch').toFixed(3)} vs ${run.meas.mean.toFixed(3)}`);

/* 4. 接受率与 tau（在线累加器 vs 离线重算，两者应当一致） */
function stats(k) {
  const c = C[k];
  const online = c.tau();
  const offline = core.estimateTau(c.samples, 400);
  return { acc: c.accepted / c.iters, tau: online, offline, n: c.iters };
}
console.log(`\n${N} 步、sigmaN=${sig} 的四组数字（二维双峰目标）`);
const table = {};
['plain', 'blind', 'matched', 'constrained', 'equalmatch'].forEach(k => {
  const s = stats(k);
  table[k] = s;
  console.log(`  ${k.padEnd(12)} accept=${(100 * s.acc).toFixed(1)}%   tau=${s.tau.toFixed(1)}  (离线重算 ${s.offline.toFixed(1)})`);
});

check('在线 tau 与离线重算相差 < 8%（滞后上限相同）',
  ['plain', 'blind', 'matched'].every(k => {
    const d = Math.abs(table[k].tau - table[k].offline) / table[k].offline;
    return d < 0.08;
  }),
  Object.keys(table).map(k => `${k}:${((table[k].tau - table[k].offline) / table[k].offline * 100).toFixed(1)}%`).join(' '));

check('盲注与方差匹配的接受率差 < 1.5 个百分点',
  Math.abs(table.blind.acc - table.matched.acc) < 0.015,
  `Δ=${(100 * Math.abs(table.blind.acc - table.matched.acc)).toFixed(2)}pp`);
check('盲注与方差匹配的 tau 差 < 12%（同一转移核，只差蒙特卡洛误差）',
  Math.abs(table.blind.tau - table.matched.tau) / table.blind.tau < 0.12,
  `τ=${table.blind.tau.toFixed(1)} vs ${table.matched.tau.toFixed(1)}`);
check('约束组与等步长组的 tau 差 < 15%',
  Math.abs(table.constrained.tau - table.equalmatch.tau) / table.constrained.tau < 0.15,
  `τ=${table.constrained.tau.toFixed(1)} vs ${table.equalmatch.tau.toFixed(1)}`);
check('盲注比朴素 MH 快（tau 更小）——原论文那条曲线',
  table.blind.tau < table.plain.tau,
  `τ=${table.blind.tau.toFixed(1)} vs ${table.plain.tau.toFixed(1)}`);
check('约束链的拒绝采样回退比例可以忽略', C.constrained.fallbacks / C.constrained.iters < 0.01,
  `fallback=${C.constrained.fallbacks}/${C.constrained.iters}`);

console.log(fails ? `\n${fails} 项未通过` : '\n全部通过');
process.exit(fails ? 1 : 0);

