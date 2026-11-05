---
layout: post
title: 'Harness：从“使用 AI”到“驾驭 AI”'
date: 2026-10-25 21:30:00 +0800
categories: 工程笔记
tags: [Harness, AI 工程, Vibe Coding, 技术债务, 技术复盘]
series: ai-harness
series_part: 1
nav_title: "从使用 AI 到驾驭 AI"
math: false
permalink: /harness/
description: '一场技术分享的复盘：生成门槛降了，验证、迁移、担责没有跟着变便宜。三本账逐条核对，再加上 harness 的定义与四根柱子。'
excerpt: '代码生成变便宜之后，贵的是验证、迁移和担责。METR 的随机对照试验里，资深开发者用上 AI 反而慢了 19%，自己却觉得快了 20%。这篇把分享里的判断逐条对表：三本账、七个子系统，以及“国家级新学科”这类说法该往回收多少。'
---

一场 Tech Meetup，地点在一家精酿酒吧风格的餐吧。没有讲台，题目却一点也不轻松：《Harness：从“使用 AI”到“驾驭 AI”》。

分享想回答的问题很具体：当大模型已经能把代码写出来，剩下的工作是什么。现场给的答案是一张架构图，五个模块，三根柱子。听的时候觉得清楚，回去把每一项拆开核对，才发现有的地方比图上复杂，有的地方比图上简单。

以下是核对后的版本。能查的数值都查了，查不到的直接标成判断；口径需要改的地方，放在最后一节。

## 一、门槛降了，账没降

"Vibe coding" 这个词 2025 年 2 月出现在 X 上，作者是 Andrej Karpathy [1]。当年 11 月，Collins 把它选进年度词汇 [2]。一个带着玩笑口吻的说法，不到一年就进了词典、招聘启事和研究论文。

采纳率的数据也支持这个说法：DORA 2025 年的报告里，90% 的受访者用过 AI，中位数每天投入两小时 [3]；Stack Overflow 2025 年的调查里，84% 的受访者正在使用或计划使用 [4]。

问题在于，采纳率之后要算账。分享把代价归成三类：代码质量、可维护性、技术债务。三类证据的强度并不一样，得分开说。

## 二、三本账

**质量。** 最常被引用的是 Pearce 等人 2021 年的研究：Copilot 生成的 1,689 个程序里，约 40% 含安全漏洞 [5]。这个数字说明初次生成的水平，不说明长期使用。

更贴近日常的是迭代带来的变化。Shukla 等人拿 400 个样本做了 40 轮"改进"，仅 5 轮之后，严重漏洞增加 37.6% [6]。"你帮我改一下"这个动作会引入新风险，因为每次局部改写都缺一份全局不变量。

**可维护性。** 行业数据能支持其中一部分，前提是分清相关和因果。DORA 的报告给出了一组同时成立的结论：AI 采纳与交付吞吐量正相关，与交付稳定性负相关；它没有做因果识别，但对机制的解释值得记下来：生成阶段省下的时间，常被重新分配到审计与验证上 [3]。Stack Overflow 的调查从开发者一侧印证：66% 的人遇到过"几乎正确但不完全对"的输出，45% 的人认为调试 AI 生成的代码更费时间 [4]。

**债务。** 这个词最早由 Ward Cunningham 在 1992 年提出，本意是用未来的理解力换现在的交付速度，不是"写了烂代码"。按这个定义看，AI 的典型行为是在原有代码上做局部修改；修改本身没问题，问题是它手里没有一份写明全局不变量的材料。

GitClear 的统计提供了一个结构性侧面：2026 年的报告统计了 6.23 亿行变更，每百万变更行里的重复代码块从 2023 年的 40.3 升到 73.0，与被移动、重构相关的代码占比从 13% 降到 3.8% [7]。这是厂商自己的数据，不同版本口径不一致，方向仍然清楚。

边界也要说：一篇覆盖 39 篇同行评审研究的系统综述指出，多数研究报告了显著收益，但证据多为自报、短期、任务级，缺少对长期维护成本和团队级影响的度量 [8]。

## 三、如果开发成本趋近于零

现场最有价值的是一个假设：如果开发成本低到可以忽略，技术债务是不是就不再是大问题。

这个假设问的其实是：既然代码可以随时重写，关于架构和可维护性的顾虑是不是都过时了。

先看成本结构。把软件的总成本拆开，被压缩的只有"写"这一段：

| 成本项 | 能否被压缩 | 原因 |
|---|---|---|
| 生成 | 显著压缩 | 唯一被压缩的部分 |
| 理解 | 不可压缩 | 理解的对象是系统，不是文件 |
| 验证 | 反而上升 | 生成量上升，待验证面积上升 |
| 数据迁移 | 不可压缩 | 数据不能重新生成，只能迁移和兼容 |
| 责任归属 | 不可压缩 | 复盘时"模型写的"不构成解释 |

"既然改起来贵，那就让 AI 重写一遍"是最自然的推论，也是最危险的。旧系统经过生产验证，是判断新系统是否等价的唯一基线；隐性知识散落在提交信息、工单和离职同事的脑子里，重写必然丢；数据不会跟着代码走；有足够多的用户依赖，任何可观察行为都会变成事实上的契约 [9]。

经验证据里最硬的是 METR 2025 年 7 月的随机对照试验 [10]。16 名资深开源维护者，246 个真实任务，平均耗时 2 小时，每个人在自己平均 5 年经验的项目上工作。开始前，他们估计自己会快 24%；完成后，感觉快了 20%；实测完成时间慢了 19%。外部专家同样乐观：经济学家预测快 39%，机器学习专家预测快 38%。

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig3-metr-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig3-metr-light.svg' | relative_url }}" alt="METR 试验的三个数字：预期 +24%、体感 +20%、实测 −19%" width="900" height="360" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig3-metr-dark.svg' | relative_url }}" alt="METR 试验的三个数字：预期 +24%、体感 +20%、实测 −19%" width="900" height="360" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 1 · 预期、体感与实测</strong>　同一批开发者给出的三个数：事前预测快 24%，事后自评快 20%，实测完成时间慢 19%。</figcaption>
</figure>

三个数字放在一起，比任何争论都清楚：模型让人感觉更快，实际更慢，当事人自己也察觉不到。

这项研究的工具链停在 2025 年上半年，不能当作今天的能力结论。它给的是一条机制提醒：当成本从生成偏移到集成与验证，更强的模型不一定让总时间下降，因为被优化的那一项占比已经很小。

推论只有一句：生成越便宜，架构越值钱。架构的作用之一，是让改动的影响范围可预测。

## 四、Harness：把运行时当作工程对象

分享用"驾驭"来概括解法。两年前这还是个比喻；到 2026 年，它有了定义，也有了 11 个生产系统的源码解剖。

定义来自一份预印本：harness 是"模型之外的一切"，即把大模型与世界耦合起来的运行时，包括循环、工具、上下文、安全控制、编排、扩展面；harness engineering 是设计与演化这个运行时的学科 [11]。论文把运行时拆成七个子系统：循环（D1）、模型集成（D2）、工具与动作（D3）、记忆与上下文（D4）、安全与权限（D5）、编排（D6）、扩展性（D7），另有界面层与会话底座两个横切面。

分享的五个模块和这张表并不一一对应：工具系统对应 D3，安全对应 D5，记忆与上下文被论文合成 D4，会话管理更接近会话底座；D1、D2、D7 在分享里没有单列。作为演讲用的归纳，这没问题；当成检查表用，需要补上缺的三项。

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig1-map-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig1-map-light.svg' | relative_url }}" alt="两套划分的对照：分享的五模块与论文的七子系统" width="1000" height="650" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig1-map-dark.svg' | relative_url }}" alt="两套划分的对照：分享的五模块与论文的七子系统" width="1000" height="650" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 2 · 两套划分的对照</strong>　左边是讲演归纳的五模块加三根柱子，右边是 11 个生产系统源码解剖出的七个子系统与两个横切面。实线是直接对应，虚线是需要改动或本就不存在对应。</figcaption>
</figure>

四个发现里，有三个值得单独记：

- 约 100 行代码也能实现全部七个子系统，自报成绩与代码量大三个数量级的系统处在同一区间。论文注明这些数字不能直接比较；地板与生产系统的差别写在别处，安全、恢复、成本、扩展。
- 11 个生产 harness 里，没有一个在可检视的依赖与 import 路径上使用 agent 框架，连 Gemini CLI 也跳过了 Google 自家的 Genkit 和 ADK [11]。要改真实源码的系统，宁可手写也不复用抽象。
- 同一模型换一套 harness，安全水平可以差四倍。一项覆盖 6 个模型、3 个 harness、128 个用例的基准里，攻击成功率从 12.6% 到 80.9%；GLM-5.2 在一个 harness 上是 54.7%，换到另一个只有 12.6% [12]。

这三条的共同点，是把"AI 应用好不好"从模型能力问题，变成可以逐项检查的工程结构问题。

## 五、四根柱子，压成两件事

分享的解法排了五层。落到工程上，其实只有四件事：规范写得可执行，领域模型里的不变量挑得出来，验证放在前面，失败可以恢复。

**规范要能编译成检查。** 测试侧的证据是同行评审的：让 agent 先写出前置条件、后置条件与未定义行为，再生成测试，在 Google 的真实缺陷上把检出率提高了 9.8 个百分点（p=0.0352），分支覆盖率提高 2.5 个百分点（p=0.0034）[13]。另一面来自源码研究：提示词文本是行为上的愿望，不是机制 [11]；它的消融实验显示，只改系统提示词会让成绩下降 2.3 个百分点。两句话合起来，结论很具体：规范的价值取决于它能不能被编译成检查。

**验证要前置。** 契约测试、属性测试、金丝雀发布、回滚预案、可观测性埋点，这些在手写时代可以慢慢补，在生成时代必须提前，因为要防的是你不会去读的那部分代码里的错误。

**恢复要能重放。** 源码研究里有个细节：生产系统在恢复上的投入远超预期，事件溯源的会话、上下文压缩、可 fork 的会话树、把失败回滚成可以重放的事件 [11]。

## 六、“国家级新学科”要往回收

复盘里提到，卡内基梅隆的软件工程研究所（SEI）成立了 AI Division，INCOSE 发布了系统工程指南，标志着这成了国家级、行业级的新学科。

核查之后，三句话都要改。

INCOSE 在 2026 年 4 月的一份征集方案里写得很直接：关于 AI 在系统工程流程中何处带来价值、如何原生集成，目前没有权威的 INCOSE 指南 [14]。被当成"指南"引用的那份 PDF，本身是招标文件。

SEI 这边，AI Division 确实存在，成立于 2021 年 6 月，不是新设机构；SEI 是国防部门资助、卡内基梅隆运营的联邦资助研发中心 [15]。能支撑"国家级"的只有当年新闻稿里的一句自我描述：牵头一项国家级倡议。它说的是倡议，不是学科认定。

准确的说法是：一家联邦资助研发中心把 AI 工程当作学科来建设，并自称牵头一项国家级倡议。

另有三处说法在传播，本文没有采用：DORA 2024 的"AI 采纳率每提高 25%，吞吐下降 1.5%、稳定性下降 7.2%"未能与报告正文核对；"AI 代码缺陷率是人工 N 倍"能追到的倍数是扫描器漏洞数或每个 PR 的问题数，口径不同；"验证成本大于生成成本"没有直接测量，正文用的是 DORA 的表述。

## 七、结语

分享被总结成"旧秩序在崩坏，新秩序在建立"。这个判断我同意，但想把新秩序说得朴素一点。

新秩序的内容，是为 AI 写软件所需要的那套工程。它没有发明新原理，做的是把经典软件工程里那些显得啰嗦的东西（权限、约束、恢复、可观测、验收标准、非功能需求）从加分项变成准入条件。

核心资产也随之挪了位置：手写代码的年代，代码本身就是资产；现在更值钱的是规范、领域模型、验证体系，以及"什么不可改变"这类判断。它们都不产生代码行数。

Vibe coding 降低了进入成本。harness 决定这套系统能走多远，也决定出问题的时候，能不能退回昨天。

## 参考资料

[1] Karpathy, A. (2025-02-02). *"There's a new kind of coding I call 'vibe coding'"*. <https://x.com/karpathy/status/1886192184808149383>
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

*说明：文中标注编号的数值与结论来自上述来源；核查中放弃的口径与理由，写在第六节末尾。*
