---
layout: page
title: "研究笔记"
permalink: /research/
eyebrow: "RESEARCH · 研究笔记"
description: "一条线一个专题：自己定问题、自己跑实验、自己写复盘。这里放的是过程与证伪，不是结论合集。"
---

{%- assign topics = site.data.research_topics -%}

<div class="cards">
  {%- for t in topics %}
  <a class="card" href="{{ t.url | relative_url }}">
    <span class="card-index">{{ t.index }}</span>
    <h3 class="card-title">{{ t.title }}</h3>
    <p class="card-desc">{{ t.blurb }}</p>
    <p class="card-meta"><span>{{ t.meta }}</span><span class="dot">·</span><span>{{ t.years }}</span></p>
    {%- if t.tags %}
    <ul class="card-tags">
      {%- for tag in t.tags %}<li>{{ tag }}</li>{% endfor %}
    </ul>
    {%- endif %}
    <span class="card-arrow" aria-hidden="true">→</span>
  </a>
  {%- endfor %}
</div>

## 怎么读

- **从结论开始**：每个专题页开头都有「导读」，标明哪几篇是结论、哪几篇是推导。
- **按专题读**：专题内部的顺序是写作顺序，不是发布时间顺序；按编号走一遍最省事。
- **看证伪**：这套笔记里每一处对原论文的批评，同时适用于我自己的推导；被推翻的假设都留在正文里。

## 这一栏以后会增加什么

同一套做法会往三个方向长：更长的采样与加速实验（噪声、步长、批量）、评测与口径（怎么判断"变好了"）、
以及把研究结论压进可复现的工程实现。每个方向上线时开一个专题，编号顺延。
