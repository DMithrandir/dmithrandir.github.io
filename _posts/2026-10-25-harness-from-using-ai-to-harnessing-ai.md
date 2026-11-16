---
layout: post
title: 'Harness Engineering：从“使用 AI”到“驾驭 AI 运行时”'
date: 2026-10-25 21:30:00 +0800
categories: 工程笔记
tags: [Harness, AI 工程, Vibe Coding, 技术债务, 运行时工程]
series: ai-harness
series_part: 1
nav_title: "从使用 AI 到驾驭 AI 运行时"
math: false
permalink: /harness/
description: '代码生成变便宜之后，贵的是验证、迁移和担责。三本实证账、11 个生产级 harness 的源码解剖，以及四条能进主干的工程准则。'
excerpt: 'AI 写下的程序约 40% 含漏洞，五轮迭代后严重漏洞再多 37.6%；METR 的随机对照试验里，资深开发者用上 AI 反而慢了 19%，自己却觉得快了 20%。harness 是模型之外的一切，它决定这套系统能走多远。'
---

这篇把三件事放在一起算：AI 辅助编程在质量、可维护性与技术债务上的三本实证账；11 个生产级 coding agent 的运行时结构；以及一套能落到一线的工程准则。

## 一、生成门槛降了，工程总账没降

2025 年 2 月，Andrej Karpathy 在 X 上提出“Vibe coding”；同年 11 月，这个词被柯林斯词典收进 2025 年度词汇 [1][2]。

一线研发的采纳率印证了这个趋势：DORA 2025 年的报告里，90% 的受访开发者已经用上 AI，日均投入中位数 2 小时 [3]；Stack Overflow 2025 年的调查里，正在使用或计划使用 AI 工具的比例达到 84% [4]。

但高采纳率之后必须算总账。把 AI 编程的工程代价拆成代码质量、可维护性、技术债务三本账，现有实证证据呈现出相当一致的结构性风险。

**质量账。** 最早被引用的是 Pearce 等人 2021 年的检测：Copilot 生成的 1,689 个程序里，约 40% 含安全漏洞 [5]。这个数字反映的是单次生成的基线，不反映真实研发里的多轮修改。更贴近日常场景的是 Shukla 等人 2025 年的实验：400 个样本跑了 40 轮“改进”，仅 5 轮之后，严重安全漏洞的数量就增加了 37.6% [6]。

每一次“帮我改一下”的局部改写，本质上都是在缺乏全局不变量约束的情况下给系统打补丁，新引入的状态冲突与安全隐患是必然结果。

**可维护性账。** DORA 2025 的报告给出了一组同时成立的观测：AI 采纳率与交付吞吐量正相关，与交付稳定性负相关 [3]。报告没有做严格的因果识别，但指出了底层的资源重分配机制——生成阶段省下的时间，往往被转移并消耗在后续的代码审计与验证上。

Stack Overflow 2025 年的开发者反馈印证了这层摩擦：66% 的受访者频繁遇到“几乎正确但存在细微错误”的 AI 输出，45% 的受访者直言调试 AI 生成的代码比手写更耗时 [4]。

**债务账。** Ward Cunningham 在 1992 年提出“技术债务”，本意是透支未来的系统理解力去换当下的交付速度，不是指写了烂代码。AI 擅长在存量代码上做局部增补，却不掌握系统的全局契约。

GitClear 2026 年的报告统计了 6.23 亿行代码变更：每百万行变更里的重复代码块从 2023 年的 40.3 升到 73.0，反映架构整理与模块复用的“代码移动 / 重构”占比则从 13% 降到 3.8% [7]。厂商报告的统计口径在不同版本之间有差异；覆盖 39 篇同行评审论文的系统综述也指出，当前学界证据仍以短期、任务级的自报数据为主 [8]。但代码库朝“高重复、低重构”演化的方向已经比较清楚。

## 二、“坏了就让 AI 重写”是危险幻觉

面对日益沉重的技术债，有一种很有诱惑力的推论：既然 AI 让写代码的成本趋近于零，可维护性是不是就不再重要了？旧代码改不动的时候，让 AI 重写一套不就行了。

这个推论的盲点，在于把“代码生成成本”和“软件全生命周期总成本”混成了一件事：

| 成本维度 | AI 的压缩弹性 | 工程上的约束 |
|---|---|---|
| 代码生成 | 显著压缩 | 全生命周期里唯一被大模型直接压缩的一环 |
| 系统理解 | 不可压缩 | 要理解的是跨模块的系统拓扑与业务状态，不是孤立的代码文件 |
| 正确性验证 | 反而上升 | 生成吞吐越大，待验证的状态空间与边界条件面积越大 [3] |
| 数据迁移 | 不可压缩 | 存量状态与历史数据无法重新生成，只能双向兼容、平滑迁移 |
| 责任归属 | 不可压缩 | 事故复盘与合规审计里，“代码是模型写的”不构成免责解释 |

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig2-cost-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig2-cost-light.svg' | relative_url }}" alt="五类成本在 AI 前后的相对权重：生成被压缩，验证被放大" width="1000" height="470" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig2-cost-dark.svg' | relative_url }}" alt="五类成本在 AI 前后的相对权重：生成被压缩，验证被放大" width="1000" height="470" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 1 · 五类成本的权重变化</strong>　生成变便宜，待验证的面积和迁移的代价没有跟着变；验证从一段流程变成主成本。示意图，非实测。</figcaption>
</figure>

因此，“坏了直接重写”在生产工程里几乎不可行：

- **丧失等价性基线。** 经过长期生产检验的旧系统，是判断新系统行为是否等价的唯一基准。
- **隐性知识永久丢失。** 边界条件与历史妥协散落在提交记录、工单，甚至离职同事的记忆里，推倒重写必然抹平这些隐性防御逻辑。
- **存量数据与隐性契约无法重置。** 数据不会跟着新代码迁移；更要紧的是 Hyrum 定律：当下游用户足够多时，系统暴露出的一切可观测行为，无论有没有写进接口文档，都会变成下游实际依赖的事实契约 [9]。

这一定性推论在 METR 2025 年的随机对照试验里得到了最硬的支撑 [10]。16 名平均有 5 年项目维护经验的资深开源维护者，在各自熟悉的大型真实代码库里完成了 246 个真实开发任务，平均每项约 2 小时，工具链停在 2025 年上半年的 Cursor Pro + Claude 3.5/3.7。结果是一组认知倒挂：

- 事前预期：外部经济学家预测 AI 能让开发快 39%，机器学习专家预测快 38%，开发者本人预计快 24%。
- 事后体感：任务完成后，开发者自评依然觉得快了 20%。
- 客观实测：允许使用 AI 的任务组，端到端完成时间反而慢了 19%。

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig3-metr-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig3-metr-light.svg' | relative_url }}" alt="METR 试验的三个数字：预期 +24%、体感 +20%、实测 −19%" width="900" height="360" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig3-metr-dark.svg' | relative_url }}" alt="METR 试验的三个数字：预期 +24%、体感 +20%、实测 −19%" width="900" height="360" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 2 · 预期、体感与实测</strong>　同一批开发者给出的三个数：事前预测快 24%，事后自评快 20%，实测完成时间慢 19%。</figcaption>
</figure>

三个数字放在一起比任何争论都清楚。背后是一条不随模型升级而消失的机制：当研发成本的重心从“代码生成”偏移到“上下文对齐、系统集成与正确性验证”，单纯提高生成速度不但缩短不了总工期，还可能因为审查负担加重而拖慢交付；而身处其中的开发者拿到了高频生成的即时反馈，根本察觉不到自己变慢了。

推论只有一句：代码生成越便宜，用来收敛变更影响半径的架构越值钱。

## 三、Harness：把模型之外的运行时当一等工程对象

单靠模型能力无法闭环，工程界的重心于是转向 harness。Barbaste 等人 2026 年对 11 个主流生产级 coding agent 做了源码级解剖，给出的定义是：harness 是“模型之外的一切”，即把大模型与外部世界耦合起来的完整运行时；harness engineering 则是设计、实现与演化这套运行时的工程学科 [11]。

这份研究把生产级运行时拆成 7 个正交子系统：

- **D1 · 执行循环（Loop）**：状态流转、停止条件判定与故障恢复。
- **D2 · 模型集成（Model Integration）**：多模型路由、接口适配与推理参数协同。
- **D3 · 工具与动作（Tools & Actions）**：文件读写、Shell 执行与外部环境交互原语。
- **D4 · 记忆与上下文（Memory & Context）**：上下文窗口裁剪、状态压缩与长期记忆检索。
- **D5 · 安全与权限（Safety & Permissions）**：沙箱隔离、高危指令拦截与权限边界控制。
- **D6 · 多 Agent 编排（Orchestration）**：子任务拆解、并发调度与跨 Agent 状态同步。
- **D7 · 扩展性（Extensibility）**：Hooks、Skills、插件机制与 MCP 接入面。

界面层（UI/UX）与会话底座（Session Substrate）作为两个横切面贯穿上述子系统；业界常混为一谈的“评估与可观测性”（evaluation harness）则是独立于运行时本体之外的另一套测试基础设施 [11]。

源码比对下来，有三条事实打破了行业早期的直觉。

**跑分下限极低，生产壁垒全在非功能性设计。** 约 100 行代码就能实现涵盖 D1–D7 的极简原型，自报基准得分与代码量大出三个数量级的商业系统处在同一区间。论文特别注明这类跑分不能横向比较：玩具原型与生产系统的鸿沟不在“能不能跑通一次任务”，而在安全边界、故障恢复、token 成本控制与扩展能力 [11]。

**生产级 coding agent 全部弃用通用 agent 框架。** 被解剖的 11 个系统里，没有一个在可检视的依赖与 import 路径上使用现成的第三方 agent 框架，连 Google 的 Gemini CLI 也直接跳过了自家的 Genkit 和 ADK [11]。凡是要深度读写和修改真实代码库的系统，团队无一例外手写确定性的底层控制流。

**harness 架构决定模型安全水位的上下限。** 在覆盖 6 个大模型、3 套 harness、128 个用例的生命周期安全基准 HarnessRisk 里，全样本攻击成功率跨度从 12.6% 到 80.9%；同一个 GLM-5.2 模型，在其中一套 harness 上被攻破率高达 54.7%，换到另一套有严密权限与循环约束的 harness 上则降到 12.6%，差四倍以上 [12]。

三条事实指向同一个结论：AI 应用的可信度不是单纯的模型能力问题，而是可以逐项审计的运行时工程结构问题。

## 四、落地：收敛成四项硬性准则

拿掉宣传包装，构建高可靠的 harness 落到一线只有四件实事。

**一、把提示词里的愿望编译成契约检查。** 源码消融实验显示，自然语言提示词只是行为上的愿望，不是强制机制——单独修改系统提示词，任务得分反而下降 2.3 个百分点 [11]。另一侧的证据来自 Google 真实缺陷数据集上的同行评审研究：强制 agent 先写出前置条件、后置条件与未定义行为，再把它编译成可执行契约去生成测试，真实缺陷检出率提高 9.8 个百分点（p=0.0352），分支覆盖率提高 2.5 个百分点（p=0.0034）[13]。规范的价值，取决于它能不能被编译成自动化检查。

**二、显式提取并守护领域不变量。** AI 做局部修改时最容易击穿跨模块的业务约束。工程师要把“什么绝对不能变”从隐性默契提炼成代码库里的显式断言。

**三、验证全面前置。** 契约测试、基于属性的测试、金丝雀发布、自动回滚预案、可观测性埋点，这些在手写时代可以事后补齐，在生成时代必须前置到合入之前，因为它们防的正是人不会再逐行细读的那部分生成代码。

**四、基于事件溯源做可重放的恢复。** 生产级 harness 在状态恢复上的投入远超外界想象：事件溯源的会话底座、确定性上下文压缩、可 fork 的会话树，把每一次执行失败变成可回滚、可重放的事件流，而不是清空重来 [11]。

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig4-loop-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig4-loop-light.svg' | relative_url }}" alt="从规范到恢复的闭环：规范、生成、验证、发布、恢复" width="1000" height="460" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig4-loop-dark.svg' | relative_url }}" alt="从规范到恢复的闭环：规范、生成、验证、发布、恢复" width="1000" height="460" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 3 · 从规范到恢复的闭环</strong>　规范写在前面，验证放在中间；未通过不入主干，恢复的目标是回到上一个可复现的良好状态，不是“修好”。</figcaption>
</figure>

## 五、勘误：几个被传歪的口径

为了保证工程讨论的严谨，原分享与后续传播里有几处失真需要纠偏。

**关于“INCOSE 发布权威系统工程指南”。** 核查 INCOSE 2026 年 4 月发布的 CFS-C5-02 文件，那份 PDF 实为公开征集解决方案的招标书（Call for Solutions），文中明说：关于 AI 在系统工程流程里何处产生价值、如何原生集成，目前还没有权威的 INCOSE 指南 [14]。

**关于“CMU SEI 新设 AI Division 标志国家级新学科诞生”。** 软件工程研究所（SEI）是美国国防部资助、卡内基梅隆运营的联邦资助研发中心（FFRDC），其 AI Division 早在 2021 年 6 月就已成立，不是近期新设机构；当年新闻稿的原话是“牵头一项国家级倡议”，并把 AI 工程作为学科方向建设，而非获得了官方的“国家级新学科”认定 [15]。

**三类未采信的二手传播数据。**

- “DORA 2024 报告称 AI 采纳率每提高 25%，吞吐量下降 1.5%、稳定性下降 7.2%”未能与报告正文核对一致。
- “AI 代码缺陷率是人工的 N 倍”混淆了静态扫描器告警数与单 PR 缺陷数这两种不同分母。
- “验证成本大于生成成本”缺乏直接的量化测度；严谨的说法应取 DORA 的表述——生成省下的时间被重新分配到了审计与验证。

## 六、结语：核心资产的位移

旧秩序在崩坏，新秩序在建立。这套新秩序没有发明什么玄妙的新原理，它做的是把经典软件工程里那些曾被视为繁琐负担的东西——权限边界、契约约束、故障恢复、可观测性、验收标准与非功能需求——从加分项变成准入条件。

开发者的核心资产也随之位移：手写代码的年代，代码本身就是资产；AI 生成的年代，值钱的是可执行规范、领域模型、前置验证体系，以及对“什么不可改变”的架构判断力。它们都不产生代码行数。

Vibe coding 决定了系统启动有多快，harness 决定了这套系统能走多远，以及出问题的那一刻，能不能安全地退回昨天。

## 参考资料

[1] Karpathy, A. (2025-02-02). *“There's a new kind of coding I call 'vibe coding'”*. <https://x.com/karpathy/status/1886192184808149383>
[2] *Vibe coding picked as Collins' Word of the Year 2025*（TASS，2025-11-06）. <https://tass.com/society/2040125> ｜ 官网存档：<https://web.archive.org/web/20251209085408/https://www.collinsdictionary.com/woty>
[3] DORA. *State of AI-assisted Software Development*（2025）；*Balancing AI tensions: Moving from AI adoption to effective SDLC use*. <https://dora.dev/insights/balancing-ai-tensions/>
[4] Stack Overflow. *2025 Developer Survey — AI*. <https://survey.stackoverflow.co/2025/ai>
[5] Pearce, H., Ahmad, B., Tan, B., Dolan-Gavitt, B., & Karri, R. (2021). *Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions*. arXiv:2108.09293. <https://arxiv.org/abs/2108.09293>
[6] Shukla, S., Joshi, H., & Syed, R. (2025). *Security Degradation in Iterative AI Code Generation — A Systematic Analysis of the Paradox*. IEEE-ISTAS 2025. arXiv:2506.11022. <https://arxiv.org/abs/2506.11022>
[7] GitClear. (2026). *The AI Code Quality Maintainability Gap*. <https://www.gitclear.com/the_ai_code_quality_maintainability_gap>
[8] Mohamed, A., Assi, M., & Guizani, M. (2025). *The Impact of LLM-Assistants on Software Developer Productivity: A Systematic Review and Mapping Study*. arXiv:2507.03156. <https://arxiv.org/abs/2507.03156>
[9] Wright, H. *Hyrum's Law*. <https://www.hyrumslaw.com/>
[10] Becker, J., Rush, N., Barnes, B., & Rein, D. (2025). *Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity*. METR. arXiv:2507.09089. <https://arxiv.org/abs/2507.09089>
[11] Barbaste, P., Darrigol, T., Vu, G., & Wiltberger, T. (2026). *Harness Engineering: Anatomy, Architecture, and Evolution of Coding Agents — A Source-Code Study of Eleven Systems*（预印本）. arXiv:2609.00006. <https://arxiv.org/abs/2609.00006>
[12] Bai, Y., Duan, J., Peng, J., Wu, X., Liu, S., Wang, S., & Chen, T. (2026). *HarnessRisk: A Lifecycle-Oriented Benchmark for Agent Harness Safety*（预印本，审稿中）. arXiv:2608.17597. <https://arxiv.org/abs/2608.17597>
[13] Tufano, M., McClure, J., Cambronero, J., et al. (2026). *Grounding AI Agents in Contracts: An Empirical Evaluation of Spec-Driven Test Generation*. SpecOps '26. DOI: 10.1145/3842652.3843195. arXiv:2608.17177. <https://arxiv.org/abs/2608.17177>
[14] INCOSE. (2026-04-08). *AI in SE Practice: Use Cases, Native Integration Patterns, and Quality Governance*（Call for Solutions，CFS-C5-02）. <https://www.incose.org/wp-content/uploads/2026/04/CFS-C5-02.pdf>
[15] Carnegie Mellon University, Software Engineering Institute. (2021-06-28). *Software Engineering Institute Announces Establishment of New AI Division, Names Director*. <https://www.sei.cmu.edu/news/software-engineering-institute-announces-establishment-of-new-ai-division-names-director/> ｜ *About the SEI*：<https://www.sei.cmu.edu/about/>

---

*说明：文中标注编号的数值与结论来自上述来源；核查中放弃的口径与理由，写在第五节末尾。*
