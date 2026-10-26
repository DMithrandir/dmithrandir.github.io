---
layout: page
title: "噪声、不等式与采样器"
permalink: /mcmc/
eyebrow: "SERIES · 2020 → 2026"
description: "一条 MCMC 加速研究线的六年复核：从 Kosko 的噪声不等式，到我重跑自己 2020 年毕业论文时发现的三处错误。"
---

{%- assign parts = site.posts | where: "series", "noise-mcmc" | sort: "series_part" -%}

<p class="post-lead">
向一个马尔可夫链里注入噪声，它反而更快到达目标分布。这件事有定理、有专利、有一整条 2011–2019 的研究线，
却几乎没进入主流采样器的工程实践。2020 年我为它写了一篇本科毕业论文；2026 年我把它连同实验一起重跑了一遍，
发现定理是对的、数字也能复现，但我当年对"为什么有用"的解释站不住。
</p>

这套系列共 {{ parts.size }} 篇。前六篇是 2020 年论文的复盘，第七、八篇把同一条不等式往外推了一步：
一篇把它反过来，做成可检测的监控；一篇把它搬到 2023 年之后的推理时缩放上。

## 怎么读

- **想先看结论**：第 3 篇（盲注噪声等于方差调参）与第 6 篇（三处错误与这条线的去向）。
- **想跟着推一遍**：第 2 篇给出定理与证明骨架，第 4 篇是全文的智识核心——约束噪声到底做了什么。
- **想看实验**：第 5 篇有完整的四组对照与噪声扫描，配图与可复现代码。
- **想看这条线能走多远**：第 7 篇把它反过来做成审计工具（含两个反例和一处我自己写反的公式），第 8 篇把它接到多采样与验证器上。

所有实验都是独立重写、独立复算的；文中每个数字都能在仓库的 `assets/code/mcmc/` 里找到对应的脚本与输出。

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

## 一点背景

这条线的主角是 Bart Kosko 与其学生 Brandon Franzke、Osonde Osoba 在 USC 的工作。他们证明：如果噪声分布满足一个关于两个期望的不等式，
那么注入噪声会让每一步的跳跃密度在相对熵意义下更接近目标（N-MCMC，2011/2015/2019）；EM 算法有完全平行的结论（N-EM，2013/2016）。
2019 年的定版论文报告了 Lennard-Jones 分子模拟步数减少 42%、模拟退火最高加速 76%；2022 年，这条线的核心不等式被写进了美国专利 US 11,276,009 B2 的权利要求。

我 2020 年的论文综述了它，但没有做任何实验。2026 年重跑时，我补上了三件当年没做的事：**方差匹配对照**、**约束噪声的实现**、
以及**把"加速"这个词拆成混合与燃烧期两种语境**。结果是：定理是对的，但论文对"为什么有用"的解释是错的——真正起作用的是步长，
不是"选择"。
> 系列中所有对原论文的批评，都同时适用于我自己的那份毕业论文。这也是它值得写下来的原因。
