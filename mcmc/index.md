---
layout: page
title: "噪声、不等式与采样器"
permalink: /mcmc/
eyebrow: "专题 01 · MCMC · 2011 → 2026"
math: true
description: "给马尔可夫链的提议注入零均值噪声，一条不等式说它让提议离目标更近——但它量的是「提议」，不是「链」。"
---

{%- assign parts = site.posts | where: "series", "noise-mcmc" | sort: "series_part" -%}

<p class="post-lead">
给马尔可夫链的提议加一层零均值噪声，它生成的候选更贴近目标分布。Franzke–Kosko 的不等式把这件事写成一个可证的量：
目标与提议密度之间的相对熵在期望意义下变小。这条不等式量的是「这一步的提议离目标多近」，不是「链的分布离目标多近」——
两者在 MCMC 的日常语言里经常被混为一谈：无约束的盲噪声不改变提议形状，只等价于把提议方差调大；
受约束的噪声之所以不同，是因为它改变了有效步长。
</p>

这套系列共 {{ parts.size }} 篇：前六篇从定理讲到对照实验，后两篇把同一条不等式往外推了一步——一篇反过来做成审计工具，一篇接到推理时缩放上。专题页旁边还挂着两样东西：一个可以拖的[实验台](/mcmc/lab/)，一份 2020 年之后的[采样器地图](/mcmc/frontier/)。

## 导读

- **结论**：第 3 篇（盲注噪声等于方差调参）与第 6 篇（三处错误与这条线的去向）。
- **正序推导**：第 2 篇给出定理与证明骨架，第 4 篇是全文的智识核心——约束噪声到底做了什么。
- **实验结果**：第 5 篇有完整的四组对照与噪声扫描，配图与可复现代码。
- **拓展应用**：第 7 篇把它反过来做成审计工具（含两个反例和一处我自己写反的公式），第 8 篇把它接到多采样与验证器上。

## 目录

<ul class="series-index">
  {%- for p in parts %}
  <li class="series-index-item">
    <a href="{{ p.url | relative_url }}">
      <span class="si-num">{{ p.series_part | prepend: "0" | slice: -2, 2 }}</span>
      <span class="si-title">{{ p.nav_title | default: p.title }}</span>
      <span class="si-arrow" aria-hidden="true">→</span>
    </a>
    <p class="si-desc">{{ p.excerpt | default: p.description | strip_html | strip_newlines | truncate: 140 }}</p>
  </li>
  {%- endfor %}
</ul>

## 先动手，再往下读

<div class="cards">
  <a class="card" href="{{ '/mcmc/lab/' | relative_url }}">
    <span class="card-index">01</span>
    <h3 class="card-title">交互实验台</h3>
    <p class="card-desc">二维双峰目标上的四组对照：拨动噪声强度，看接受率与 τ 会不会一起动。默认场景就是「盲注 ≡ 方差匹配」那条曲线。</p>
    <p class="card-meta"><span>纯前端</span><span class="dot">·</span><span>约 10 秒一轮</span></p>
    <span class="card-arrow" aria-hidden="true">→</span>
  </a>
  <a class="card" href="{{ '/mcmc/frontier/' | relative_url }}">
    <span class="card-index">02</span>
    <h3 class="card-title">2020 年之后</h3>
    <p class="card-desc">扩散采样器、GPU 并行短链、解码期 SMC，以及化学、格点场论、宇宙学里的落地。每条都指到原文。</p>
    <p class="card-meta"><span>综述</span><span class="dot">·</span><span>2011 → 2026</span></p>
    <span class="card-arrow" aria-hidden="true">→</span>
  </a>
</div>

## 这条线现在站在哪儿

2026 年的重算把结论压成了一句话：**定理是对的，数字能复现，但「为什么有用」的解释是错的**。把这句话放进 2020 年之后的采样器版图里，位置大概是这样：

| 对照维度 | 现在的做法 | 与本系列的差别 | 一句话 |
| :--- | :--- | :--- | :--- |
| 梯度连续空间 | HMC / NUTS | 一阶信息直接消掉对提议方差调参的依赖 | 「单链省 29% 步数」在 ESS/s 上不是主战场 |
| GPU 并行多短链 | ChEES-HMC、[BlackJAX](https://arxiv.org/abs/2402.10797) 的单卡多链 | 向量化把瓶颈从单链混合挪到多链诊断 | 单链的收益退居二线，诊断成了瓶颈 |
| 无梯度多峰空间 | [DDS](https://arxiv.org/abs/2302.13834) / [CMCD](https://arxiv.org/abs/2307.01050) | 全局连续时间传输，替代单步局部加噪 | 跨模态上比的不是同一量级的东西 |

这张表在[2020 年之后](/mcmc/frontier/)那一页展开：四个主干的机制差异、单链 $\tau$ 的两个现代替代品（耦合 $f$-散度诊断、多短链的 Nested $\hat R$），以及 Best-of-N 的 KL 上界——第 8 篇那条不等式的定量版。

## 还没做完的

| 优先级 | 内容 | 状态 |
| :--- | :--- | :--- |
| **P0** | 第 3、4 篇的交互实验台；专题页改造 | ✅ 已上线 |
| **P1** | JAX / BlackJAX 上补 NUTS 与 ChEES 并行短链对照；把实验台的单链 $\tau$ 换成多链诊断 | ⬜ 计划 |
| **P2** | 第 8 篇的「多采样失效边界」做成 Python 模块：$N^*$ 与过优化熔断阈值 | ⬜ 计划 |

## 一点背景

这条线的主角是 Bart Kosko 与其学生 Brandon Franzke、Osonde Osoba 在 USC 的工作。他们证明：如果噪声分布满足一个关于两个期望的不等式，
那么注入噪声会让每一步的跳跃密度在相对熵意义下更接近目标（N-MCMC，2011/2015/2019）；EM 算法有完全平行的结论（N-EM，2013/2016）。
2019 年的定版论文报告了 Lennard-Jones 分子模拟步数减少 42%、模拟退火最高加速 76%；2022 年，这条线的核心不等式被写进了美国专利 US 11,276,009 B2 的权利要求。

我 2020 年的论文综述了它。2026 年重跑时，增补：**方差匹配对照**、**约束噪声的实现**、
以及**把"加速"这个词拆成混合与燃烧期两种语境**。结果是：定理是对的，但论文对"为什么有用"的解释是错的——真正起作用的是步长，
不是"选择"。

> 系列中所有对原论文的批评，都同时适用于我自己的那份毕业论文。这也是它值得写下来的原因。
---

<p><a class="back-link" href="{{ '/research/' | relative_url }}"><span aria-hidden="true">←</span> 回研究笔记</a></p>
