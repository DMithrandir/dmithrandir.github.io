---
layout: page
title: "评测这把尺子：怎么造、怎么校、怎么坏"
permalink: /eval/
eyebrow: "专题 · 模型评测 · 2026 →"
description: "五篇：从审核系统的旧账讲到 2026 年的榜单信任危机、指标口径、Rubrics-as-Rewards，以及把专家嵌进系统时的结算与信任基建。"
---

{%- assign parts = site.posts | where: "series", "ai-eval" | sort: "series_part" -%}

<p class="post-lead">
评测和审核做的是同一件事的两层：把高歧义的人类判断，工程化成一把握得住、量得准、并且知道自己什么时候会失准的尺子。
这一组从内容治理的旧账开始——SSOT 的三层结构、质检口径里隐含的惩罚函数、使用率趴在 29.51% 的那次返工——
再把同一套结构放到 2026 年的模型评测里验一遍：榜单怎么静默崩溃、指标为什么没有中立的、Rubric 为什么能当奖励、专家为什么留不住。
</p>

这套系列共 {{ parts.size }} 篇，正序读最省事；每篇末尾都写了它自己在什么条件下失效。

## 导读

- **同构在哪、哪儿失效**：第 1 篇把审核的 SSOT 三层与 Rubric 引擎并排放，末尾给出三条边界——单点判定对长程轨迹、合同工时对双边市场、静态 benchmark 对能力相变。
- **尺子怎么坏的**：第 2 篇是 2026 年的四记重锤加噪声地板；第 3 篇拆分母与代价比，说明 F1 其实是一条没人投过票的政策。
- **尺子怎么造**：第 4 篇讲 Rubrics-as-Rewards 的三道闸门，以及把它用歪的三条路径。
- **谁在修尺子**：第 5 篇是人、结算和信任基建。

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

## 看到分数先问三句

> 分母是什么？方差多大？这个指标默认了谁的代价更贵？

三句分别落在第 3 篇的分母偷换、第 2 篇的噪声地板、第 3 篇的代价比上。第 2 篇另有一条更粗的读数纪律：看到低分先查题目是不是错了，看到高分先查环境是不是漏了，2 分以内的差距直接当噪声跳过。

## 一点背景

这五篇写在 2026 年 11 月，材料来自公开审计报告、当年新出的几篇论文，以及我在内容治理一线做 SSOT 知识系统、漏放红线与仲裁池的几年。文中引用的数字都带出处，没有出处的部分是我自己的判断。

<p><a class="back-link" href="{{ '/blog/' | relative_url }}"><span aria-hidden="true">←</span> 回文章列表</a></p>
