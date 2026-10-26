---
layout: page
title: "AI Harness"
permalink: /series/ai-harness/
eyebrow: "SERIES · 2026 →"
description: "模型之外的那一层：上下文、工具、重试、回放与评测。同样的模型，换一层外框，完成率可以差一倍。"
---

{%- assign parts = site.posts | where: "series", "ai-harness" | sort: "series_part" -%}

<p class="post-lead">
同一个模型，包在不同的一层里，做同一个任务的完成率可以差一倍。这一层没有统一叫法：有人叫 agent 框架，
有人叫 harness，有人叫脚手架。这里统一叫 harness——模型之外、让任务真正跑起来、并且能复现的那部分。
</p>

这套系列不写框架对比，只写自己搭过的东西：上下文怎么组织、工具怎么给、评测怎么跑、失败长什么样。

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
