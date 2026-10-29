---
layout: post
title: "08 · 多采样什么时候帮倒忙"
date: 2026-10-26 20:40:00 +0800
categories: 研究笔记
tags: [MCMC, 推理时缩放, Best-of-N, 验证器]
series: noise-mcmc
series_part: 8
nav_title: "多采样何时帮倒忙"
math: true
permalink: /mcmc/08-test-time-scaling/
description: "把 2020 年那套「噪声收益等于选择收益」搬到 2026 年的推理时缩放上：同一个不等式，换了一组坐标。多采样的收益来自覆盖率，天花板由验证器的尾部决定，而尾部不利时多采样会把准确率压到零。"
excerpt: "采样 N 个再挑一个，是 2023 年之后最有效的加速手段之一。它和我六年前研究的那套东西是同一个不等式。这篇把映射、两个可跑的实验，以及「多采样到底在赚什么」的分解放出来。"
---

2023 年之后，大模型能力提升最明显的一条来源是推理时缩放：同一个模型多采样几个候选，再用验证器挑一个。这件事和我 2020 年研究的东西是不是同一件事，是我这一轮想弄清楚的。

答案是一样的，而且逐条对得上。但先把优先权讲清楚，因为这一块已经有很硬的理论工作。

## 映射

2020 年那篇论文的骨架是：两个泛函、一个不等式、符号决定助害。推理时缩放的骨架是同一句话，只是两个泛函换了坐标。

| 2020（N-MCMC） | 2023–2026（推理时缩放） |
|---|---|
| 注入噪声 $N$ | 独立采 $N$ 个候选 |
| 提议 $Q(\cdot\mid x_t)$ | 基础策略，pass@1 记作 $p$ |
| 噪声不等式 $A\ge B$ | 正确/错误两总体的上尾支配条件 |
| 命题 1：盲注等于卷积提议 | 只加采样量等于加宽温度 |
| 推论 2.1：零均值盲噪声必然有害 | 只采样不挑选，期望准确率就是 $p$ |
| 定理 2：收益载体是确定性漂移 | 收益载体是验证器的排序能力 |
| 定理 3：不等式反向则有害 | 验证器尾部劣势导致 reward hacking |
| E3 的倒 U | 过度优化的倒 U |
| 方差匹配对照 | 覆盖率对照 |

## 先承认已有的工作

尾部竞争的渐近理论不是我做的。Yano、Ishibashi、Oyamada 在 2026 年用极值理论把 BoN 分成三个区域（正确尾支配、错误尾支配、临界），给出 Gaussian 下的 hacking 判据 $\mu_c>\mu_w$ 且 $\sigma_c<\sigma_w$，还给出交叉点 $n^\star$ 和无标签早停规则。他们的 Lemma 1 就是「典型区归约」，和下面第 5 节的覆盖率/选择分解是同一件事。

倒 U 也不是我发现的。Gao、Schulman、Hilton 在 2022 年系统测过：代理奖励随优化强度上升，金标奖励先升后降。

验证器 ROC 决定成败同样不是。Dorner 等人在 2025 年证明 BoN 与拒绝采样的实例级准确率由验证器 ROC 曲线的几何精确刻画。

我做的只有一件事：把这些独立长出来的结果，逐条映回 2020 年那套不等式的语言。另外做了两个可以跑的实验，用来说明映射确实成立，而不是一个类比。下面所有数字都是自己跑的。

## 实验一：不挑选就没收益

拿 $N$ 个候选，但把验证器换成随机挑一个，$p=0.05$：

| $N$ | 1 | 2 | 4 | 8 | 16 | 32 | 64 |
|---|---|---|---|---|---|---|---|
| 准确率 | 0.0495 | 0.0495 | 0.0496 | 0.0481 | 0.0532 | 0.0512 | 0.0497 |

最大偏差 $0.0032$，在蒙特卡洛噪声内。这与 2020 年实验里「B 组盲注与 C 组方差匹配不可区分」是同一个现象的两次观测，只换了混淆变量：当年是提议方差，现在是采样预算。

所以报告「多采样提升准确率」而不报 pass@N，和当年报告「加噪加速 42%」而不做方差匹配，是同一种归因错误。

## 实验二：尾部决定符号

设正确样本的验证器得分上尾是 Pareto，参数 $\alpha_C$；错误样本是 $\alpha_W$。注意 $P(S>s)=s^{-\alpha}$，所以 $\alpha$ 越小尾越重。BoN 取 $N$ 个里得分最高者，等价于比较两个总体的最大值。

$p=0.05$，$N$ 从 1 到 16384，每点 $2\times10^5$ 次：

| 情形 | 渐近预测 | 实测 | 判定 |
|---|---|---|---|
| 正确尾更重（$\alpha_C=0.8<\alpha_W=1.5$） | $1/\alpha_C>1/\alpha_W$，增益 | 0.048 → **0.921** | 增益 |
| 尾同重（1.2 vs 1.2） | 临界，持平 | 0.049 → 0.050 | 平 |
| 错误尾更重（$\alpha_C=1.5>\alpha_W=0.8$） | 反向，有害 | 0.049 → **0.0000** | 有害 |

第三行是这张表里唯一值得记住的。一个尾部更重的验证器会让多采样的准确率单调压到零。这不是收益递减，是负号。2020 年定理 3 说「不等式反向则噪声在平均意义下拖慢收敛」，这里是「不等式反向则挑出来的答案几乎必然错」。

## 交叉点在哪儿

Pareto 尾的最大值按 $n^{1/\alpha}$ 增长，于是让正确者胜出需要

$$
(Np)^{1/\alpha_C}>(N(1-p))^{1/\alpha_W},
$$

解出

$$
N^*\approx p^{-\gamma},\qquad \gamma=\frac{\alpha_W}{\alpha_W-\alpha_C}.
$$

$\alpha_C=0.8,\alpha_W=1.5$ 时 $\gamma\approx2.14$，$p=0.05$ 给出 $N^*\approx579$，与实测拐点一致。

这条式子解释了一件一直让我困惑的事：关于「BoN 是否随 $N$ 提升」的实证文献会互相矛盾。原因是它们在不同区间做实验。$p$ 小的时候 $N^*$ 指数级地大——$p=0.05$ 就要 600 次采样，远超多数论文用的 $N\le64$。在 $N<N^*$ 做实验得到「无帮助或有害」，在 $N>N^*$ 做得到「大幅帮助」。两批人都没做错。而当两侧尾部接近时 $N^*\to\infty$，临界线上采样再多也分不开。

## 多采样到底在赚什么

把整体准确率拆成两项：

$$
\text{overall}=\text{coverage}\times\text{selection}.
$$

coverage 是「至少采到一个正确样本」的概率 $1-(1-p)^N$；selection 是在两类样本都非空的条件下挑对的概率。

Gumbel 同尺度打分、$p=0.05$、6000 次重复：

| $N$ | overall | coverage | selection | selection 解析值 |
|---|---|---|---|---|
| 1 | 0.0485 | 0.0485 | — | — |
| 2 | 0.0707 | 0.1002 | 0.6990 | 0.6900 |
| 8 | 0.0925 | 0.3315 | 0.2790 | 0.2753 |
| 32 | 0.1017 | 0.8075 | 0.1259 | 0.1260 |
| 64 | 0.1067 | 0.9648 | 0.1106 | 0.1072 |
| 256 | 0.1033 | 1.0000 | 0.1033 | 0.1044 |

两项走向相反。coverage 从 0.0485 涨到 1.0，selection 从 0.699 掉到 0.103。

selection 为什么会跌：条件在「至少有一个正确样本」上，小 $N$ 时这个条件强制了一次幸运抽取；$N$ 大了以后要拿少数的正确样本去对抗大约 19 倍多的错误样本。乘积先升后稳，收敛到

$$
\frac{pA}{pA+(1-p)B}=0.1049,
$$

其中 $A,B$ 是 Gumbel 位置的指数。**无论采多少都超不过这个值**，它只有 pass@1 的 2.2 倍。指数尾的情形下，所谓「BoN 随 $N$ 提升」全部是覆盖率效应。

这对报告方式有直接影响。一篇写「$N=64$ 时准确率从 5% 提到 10.7%」的论文，如果不同时报 pass@64，读者无法判断这 5.7 个点来自验证器还是来自「终于采到了一个对的」。前者可复用，后者是预算换来的。

## 一个副作用：训练侧的噪声在消失

前面讲的都是采样太多。训练侧的现象反过来：GRPO 类的熵坍缩，探索在早期就没了。SCOPE-RL 的描述是探索迅速消失、策略过早收敛、样本多样性下降；RLVR 那边也诊断出「从同一策略反复采样会集中到相似的推理路径」。

用 2020 年的语言说，这是退火退过头。当年的工程结论是噪声方差随迭代衰减、接近平稳后扰动应当消失；这里的失败模式是在探索还没做完就把扰动掐掉了。

这一步是类比不是定理，我在文章里标了出来。要把它变成定理，需要先定义「探索完成」，我目前想到的候选是「策略熵对目标熵的伪距离首次单调下降」，用的还是当年那件工具。这是这条线上我最看好的下一步，但还没做。

## 证据等级

这一篇的引用里，只有 Yano 等人那篇我读了全文（到第 3 节，含 Theorem 1 与 Table 1）。其余全部只核对了摘要。所以凡是涉及「某工作没做某事」的判断，我写成「本轮检索范围内没见到」，不作绝对断言——检索当时只有 arXiv 一个通道，可能漏掉非预印本的工作。

文中的实验数字都是自己跑的，脚本在 `assets/code/mcmc/experiments_llm_scaling.py`。

---

### 文献与材料

- Yano T., Ishibashi Y., Oyamada M. Tail competition explains scaling in Best-of-N sampling for verifiable problems. *arXiv:2610.19362*, 2026.
- Gao L., Schulman J., Hilton J. Scaling laws for reward model overoptimization. *arXiv:2210.10760*, 2022.
- Dorner F. E., Chen Y., Cruz A. F. et al. ROC-n-reroll: how verifier imperfection affects test-time scaling. *arXiv:2507.12399*, 2025.
- Chen Y., Pan X., Li Y. et al. Provable scaling laws for the test-time compute of large language models. *arXiv:2411.19477*, 2024.
- Wang C., Li Z., Bai J. et al. SCOPE-RL: stable and quantitative control of policy entropy in RL post-training. *arXiv:2510.08141*, 2025.
- Zeng Y., Jing J., Cheng X. et al. Exploration via activation-space steering for reinforcement learning with verifiable rewards. *arXiv:2610.27012*, 2026.
- Miles R., Toker A., Oncescu A.-M. et al. Test-time scaling with diffusion language models via reward-guided stitching. *arXiv:2602.22871*, 2026.
- Franzke B., Kosko B. Noise can speed Markov chain Monte Carlo estimation and quantum annealing. *Physical Review E* 100: 053309, 2019.
