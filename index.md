---
layout: home
title: "AI 治理与系统笔记"
hero_title: "AI 内容治理、模型评测与工程笔记"
hero_meta:
  - label: "主题"
    value: "审核策略 · 判定机制 · 知识系统"
  - label: "更新"
    value: "不定期，长文为主"
  - label: "三条线"
    value: '<a href="/trust-and-safety/">审核策略</a> · <a href="/research/">研究笔记</a> · <a href="/series/ai-harness/">AI 工程</a>'
  - label: "订阅"
    value: "RSS"
posts_title: "最近更新"
posts_sub: "LATEST"
posts_more: "全部文章"
projects_title: "项目"
projects_sub: "PROJECTS"
projects_more: "全部项目"
about_eyebrow: "ABOUT"
about_title: "关于这个博客"
about_band: "把判定标准变成可执行、可验证、可回流的链路：审核链路、模糊案例判定、知识系统、Agentic 审核。"
about_button: "关于本站"
facts:
  - label: "主题"
    value: "审核策略 · 判定机制 · 知识系统"
  - label: "节奏"
    value: "长文为主，不定期"
  - label: "订阅"
    value: "RSS"
cta_title: "想讨论审核策略、知识系统或 Agentic 审核，GitHub 上找我就行。"
cta_subscribe: "订阅 RSS"
---

{%- assign track_policy = site.posts | where_exp: "p", "p.categories contains '治理框架'" -%}
{%- assign track_notes = site.posts | where_exp: "p", "p.categories contains '研究笔记'" -%}
{%- assign track_eng = site.posts | where_exp: "p", "p.categories contains '工程笔记'" -%}

<section class="pillars" aria-label="三条主线">
  <div class="pillar">
    <p class="pillar-num">01 治理 · {{ track_policy.size }} 篇</p>
    <h3><a href="{{ '/trust-and-safety/' | relative_url }}">审核策略</a></h3>
    <p>审核链路、灰度判定、知识系统、Agentic 审核；一篇总纲带三篇长文，按链路 → 判定 → 知识 → Agentic 读。</p>
  </div>
  <div class="pillar">
    <p class="pillar-num">02 研究 · {{ track_notes.size }} 篇</p>
    <h3><a href="{{ '/research/' | relative_url }}">研究笔记</a></h3>
    <p>一条线一个专题。MCMC 与噪声注入已收 8 篇：从相对熵不等式讲到四组对照实验，再反过来做成审计工具；外加一个可以拖的<a href="{{ '/mcmc/lab/' | relative_url }}">交互实验台</a>。</p>
  </div>
  <div class="pillar">
    <p class="pillar-num">03 工程 · {{ track_eng.size }} 篇</p>
    <h3><a href="{{ '/series/ai-harness/' | relative_url }}">AI 工程</a></h3>
    <p>模型之外的那一层：上下文、工具、评测与失败形态；自己搭、自己测、自己踩坑。</p>
  </div>
</section>
