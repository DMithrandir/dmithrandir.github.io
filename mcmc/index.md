---
layout: page
title: "噪声、不等式与采样器"
permalink: /mcmc/
eyebrow: "SERIES · 2020 → 2026"
description: "给马尔可夫链的提议注入零均值噪声，一条不等式说它让提议离目标更近——但它量的是「提议」，不是「链」。"
---

{%- assign parts = site.posts | where: "series", "noise-mcmc" | sort: "series_part" -%}

<p class="post-lead">
给马尔可夫链的提议加一层零均值噪声，它生成的候选反而更贴近目标分布。Franzke–Kosko 的不等式把这件事写成一个可证的量：
目标与提议密度之间的相对熵在期望意义下变小。但这条不等式量的是「这一步的提议离目标多近」，不是「链的分布离目标多近」——
两者在 MCMC 的日常语言里经常被混为一谈，结论却差很远：无约束的盲噪声不改变提议形状，只等价于把提议方差调大；
受约束的噪声之所以不同，是因为它改变了有效步长。
</p>

这套系列共 {{ parts.size }} 篇：前六篇从定理讲到对照实验，后两篇把同一条不等式往外推了一步——一篇反过来做成审计工具，一篇接到推理时缩放上。

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
