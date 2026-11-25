---
layout: page
title: "研究笔记"
permalink: /research/
eyebrow: "RESEARCH · 研究笔记"
description: "一条线一个专题：自己定问题、自己跑实验、自己写复盘。这里放的是过程与证伪，不是结论合集。"
wide: true
---

{%- assign topics = site.data.research_topics -%}

<div class="cards cards--topics">
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
