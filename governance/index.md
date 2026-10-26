---
layout: page
title: "治理的机制"
permalink: /governance/
eyebrow: "SERIES · 2022 → 2026"
description: "判定、政策、知识系统：内容治理里三块最容易被写成口号、实际全是流程细节的东西。"
---

{%- assign parts = site.posts | where: "series", "governance" | sort: "series_part" -%}

<p class="post-lead">
内容治理最容易写成三种东西：一段使命宣言、一堆指标、一张流程图。但真正难的是三个具体问题——
规则判不了的案例怎么进流程、政策怎么在几十个市场里真的落地、同一个口径怎么不在几十个群里各说各话。
</p>

这套系列拆开写这三块。每篇都尽量给出当时的约束、取舍和踩过的坑，而不是结论。

{%- if parts.size > 0 %}

这套系列目前有 {{ parts.size }} 篇。

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

{%- else %}

<p>这个系列还在整理，第一批文章写完后会出现在这里。</p>

{%- endif %}
