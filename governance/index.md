---
layout: page
title: "内容治理的机制"
permalink: /governance/
eyebrow: "SERIES · 2022 → 2026"
description: "从一条投稿往下拆：信号怎么来、规则怎么定、谁来审、审错了怎么推翻、用什么口径证明变好了。一份总纲、十一个模块，和几篇跨层的长文。"
---

{%- assign parts = site.posts | where: "series", "governance" | sort: "series_part" -%}

<p class="post-lead">
这套东西是从一条投稿开始往下拆的：内容进平台之后，先被哪些信号发现，按什么规则判定，
由谁审、审不完的怎么办，判错了谁来推翻，最后用什么口径证明它真的变好了。
十一块机制各自负责其中一段，另外几篇把整条链路串起来讲，或者专门拆一个口径。
</p>

每篇尽量写清当时的约束、取舍和踩过的坑，而不只是结论。凡引用平台公布的数字都标了出处与口径；
没有一手出处的，会直接写明是推论。

{%- if parts.size > 0 %}

这套目前有 {{ parts.size }} 篇。

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

## 三种速览

正文太长的场合，可以先看这三个：

- [一页纸（PDF）]({{ '/assets/governance/framework-onepager.pdf' | relative_url }})——A4 单页，可直接打印或转发。
- [顶层设计（交互）]({{ '/assets/governance/framework-map.html' | relative_url }})——五个分支、六十余节点，可展开三级。
- [思维导图]({{ '/assets/governance/framework-mindmap.html' | relative_url }})——四百余节点，用来查模块、案例与指标口径。
