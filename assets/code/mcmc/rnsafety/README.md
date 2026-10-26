# Reverse-noise safety audit toolkit

**反向噪声安全审计工具** —— 把论文的「噪声有害定理」（定理 3 / 负性条件）变成一条可执行的监控线。

理论、证明与可证性判定见 `../paper/反向噪声安全工具-定理与可证性.md`；
数值验证见 `../experiments_reverse.py` 与 `../figures/reverse_*.png`。

---

## 30 秒用法

```bash
cd C:\Financial-Data-Workflow\_mcmc\rnsafety

# 1) 内置六族注入基准（含误报率与响应时间）
python -m rnsafety.cli synthetic --seeds 12

# 2) 审计真实梯度流（每行一条 JSON）
python -m rnsafety.cli audit run.jsonl --baseline baseline.json

# 3) 先刻画干净噪声律，供以后比对
python -m rnsafety.cli fit-baseline clean.jsonl -o baseline.json

# 4) 误报率校准（证书的理论界 vs 实测）
python -m rnsafety.cli calibrate --trials 200
```

```python
from rnsafety import make_sample, audit_stream

sample = make_sample("reverse_spike", n_steps=512, dim=256, seed=0)
report = audit_stream(sample)
print(report.summary())          # 判定 + 证据 + 置信区间
print(report.verdict)            # clean | watch | suspect | harmful
print(report.to_json())          # 可直接进监控大盘
```

## 输入格式（JSONL）

每行一步，三种形态任选：

```json
{"grad_hat": [...], "grad_clean": [...]}
{"grad_hat": [...], "eps": [...]}
{"grad_hat": [...], "noise_sigma": 0.35}
```

`grad_clean` 可得时敏感度最高（余弦是**测量值**）；只有 `grad_hat` 时余弦退化为**约束**，
工具会在报告的 `limitations` 里明确标注。

## 五路监控器与它们各自能看见什么

| 监控器 | 检验 | 能看见 | 看不见 |
|---|---|---|---|
| `cosine` | 单边检验 $H_0: E[\cos(\epsilon,g)]\ge 0$ | 任何带反向偏置的注入 | 正交注入（定理 R5.2：原理上不可见） |
| `spectrum` | Marchenko–Pastur 上边缘 | 低秩尖峰（含正交尖峰） | 已铺开的各向同性注入 |
| `tail` | 下尾 vs 上尾对称性 | 微概率重尾注入（$2^{-18}$ 族） | 平滑的整体偏移 |
| `baseline` | 逐坐标 RMS 漂移 | 范数复原 / 调度篡改 | 幅度守恒的方向注入 |
| `certificate` | Bernstein 界 + 符号翻转置换 | 给出 p 值与置信区间（不是黑箱分数） | 同 `cosine` |

## 判定与风险分

`verdict ∈ {clean, watch, suspect, harmful}`，风险分 0–100 =
余弦 $40+25\cdot$效应量 + 谱 20 + 尾 15 + 基线 10。

**这是有意的粗粒度**：分数只用来排优先级，判据永远回到各监控器的 p 值与效应量地板
（`effect_floor`，默认 0.01——统计显著但小到 $10^{-4}$ 的反向偏置对攻击者没有价值，
不该触发封禁）。

## 实测性能（150 次重复、$n=512$、$d=128$）

| 注入族 | verdicts | 余弦 | 谱 | 尾 | 基线 | 首次告警步 |
|---|---|---|---|---|---|---|
| `clean` | clean 149 / watch 1 | 0.00 | 0.00 | 0.00 | 0.00 | — |
| `reverse_spike`（跟踪梯度） | harmful 150 | **1.00** | **1.00** | 0.00 | 1.00 | 8 |
| `reverse_spike_fixed` | harmful 150 | **1.00** | **1.00** | 0.00 | 1.00 | 16 |
| `norm_matched` | harmful 150 | **1.00** | **1.00** | 0.00 | 0.00 | 8 |
| `partial_rank_reversal` | harmful 129 / suspect 21 | **1.00** | 0.86 | 0.00 | 0.00 | 32 |
| `micro_spike` | suspect 93 / harmful 57 | 0.38 | **1.00** | **1.00** | **1.00** | 512 |
| `orthogonal_spike` | suspect 150 | 0.00 | **1.00** | 0.00 | 1.00 | — |

干净数据误报 **0.7%**，六族攻击 **100% 标记**。单次审计 0.11 s（$d=128$）到 0.34 s（$d=512$）。

监控器之间的**互补性**是设计要点：`micro_spike` 只能靠尾检验（余弦 0.38），
`orthogonal_spike` 只能靠谱/基线（余弦 0.00，且这是**原理性**失明）。

## 诚实边界

工具**主动**在报告里列出 ``limitations``，包括：

- 检到反向偏置但谱无尖峰 ⇒ 注入是铺开的，**不要**把「谱干净」读成「流程干净」；
  （实测：漂移 ≥0.08 时跟踪梯度的注入谱超标度 $-2$ 到 $-3.8$，而固定方向注入 $+520$）
- 谱有尖峰但无反向偏置 ⇒ 方差型（DoS 式）注入，余弦监控器**原理上**永远看不见；
- 低于效应量地板 ⇒ 该注入小到不足以实质改变下降方向（定理 R4b 的攻防权衡，上界 $1/\sqrt{dn}$）。

这三条不是免责声明，而是定理 R4b/R5.2 的直接推论：**任何足够强以破坏下降方向的反向噪声，
必然在「余弦」或「谱」至少一条线上留下痕迹**；两条线都干净的攻击，其破坏力被 $1/\sqrt{dn}$ 锁住。

## 测试与复现

```bash
cd C:\Financial-Data-Workflow\_mcmc\rnsafety
python -m pytest -q                      # 37 项单测：恒等式、反例、检测校准、CLI
python experiments_reverse.py            # 36 项定理验证（约 6.5 分钟）+ 图表 + JSON
python experiments_reverse.py --quick    # 同上但更少重复（约 40 秒）
```

`experiments_reverse.py` 对每条定理都配了一个**不共用代数**的独立检查（暴力可行性扫描、
解析 Beta 密度、最小二乘系数拟合、实测分位数），而不是复用实现里的公式自证——
本文作者自己的两个中间结论就是这样被推翻的（见论文 §5.2）。

## 许可与依赖

依赖仅 `numpy`（`matplotlib` 仅实验绘图需要，`pytest` 仅测试需要）。本工具复现的是论文与
拓展系列的**理论**，不包含也不实现任何受专利保护的约束噪声采样器（见 `拓展三-实现篇.md`
§5 的 FTO 提示）。
