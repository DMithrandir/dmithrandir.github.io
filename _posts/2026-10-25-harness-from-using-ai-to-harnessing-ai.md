---
layout: post
title: 'Harness：从"使用 AI"到"驾驭 AI"'
date: 2026-10-25 21:30:00 +0800
categories: 工程笔记
tags: [Harness, AI 工程, Vibe Coding, 技术债务, 技术复盘]
permalink: /harness/
description: '一场技术分享的复盘，加上逐条核对过的证据：门槛确实降了，但验证、迁移、担责没有跟着变便宜；harness 这门 2026 年才被命名的工程学科，到底管什么。'
excerpt: 'Vibe coding 让生成变便宜。METR 的随机对照试验里，资深开发者用上 AI 反而慢了 19%，自己却觉得快了 20%。这篇把分享里的判断逐条拆开核对：七个子系统与五个模块怎么对表，技术债的账怎么记，验证为什么成了主成本，以及"国家级新学科"这类说法该往回收多少。'
---

一场 Tech Meetup，地点在一家精酿酒吧风格的餐吧。没有讲台，题目却一点也不轻松：《Harness：从"使用 AI"到"驾驭 AI"》。

分享想回答的问题很具体：当大模型已经能替你把代码写出来，剩下的工作是什么。现场给的答案是一张架构图，五个模块，三根柱子。听的时候觉得清楚，回去把每一项拆开核对，才发现有的地方比图上复杂，有的地方比图上简单。

下面这篇是重写过的版本。能查的数值都查了，查不到的直接标明是判断；引用落在参考文献里，核查过程和反例放在第九节。

## 一、分享给出的结构

分享的骨架是一张架构图：请求进来，响应出去，中间夹着大模型和一层工程框架。框架拆成五个模块：会话管理、记忆管理（状态与记忆）、上下文管理、工具系统、安全与质量管理。图的下方并排三根柱子：编排、约束与恢复、评估与可观测性。

这张图的说服力在于，它把"AI 应用"从一句口号拆成了可以逐项检查的东西。它也留下一个问题：这五块是怎么切出来的。

这套划分与 2026 年 7 月挂上 arXiv 的一份预印本基本对应。四位作者解剖了 11 个生产级编程 agent 的源码，共约 400 万行（[1]），把"模型之外的一切"称为 harness。论文把运行时拆成七个子系统：循环（D1，负责停止条件与故障恢复）、模型集成（D2）、工具与动作（D3）、记忆与上下文（D4）、安全与权限（D5）、编排（D6）、扩展性（D7）。除这七项之外，还有两个横切面：界面层（终端、IDE、SDK）和会话底座（对话记录、持久化、恢复与分叉）。

对照之后可以发现几处错位。分享的五个模块里，工具系统对应 D3，安全与质量管理对应 D5，记忆管理与上下文管理在论文里是同一个 D4；会话管理更接近横切面里的会话底座。D1、D2、D7 在分享的模块里没有单列。三根柱子中，编排在论文里是独立子系统 D6，约束与恢复分散在 D1 与 D5；评估与可观测性则不属于 harness 本身，论文明确区分了 agent harness 与 evaluation harness。

我最初以为七个子系统只是把五个模块拆得更细，对照之后发现不是。有的模块被合并，有的子系统在分享里根本没有出现。对照结果画在图 1 里。

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig1-map-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig1-map-light.svg' | relative_url }}" alt="两套划分的对照：分享的五模块与论文的七子系统" width="1000" height="650" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig1-map-dark.svg' | relative_url }}" alt="两套划分的对照：分享的五模块与论文的七子系统" width="1000" height="650" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 1 · 两套划分的对照</strong>　左边是讲演归纳的五模块加三根柱子，右边是 11 个生产系统源码解剖出的七个子系统与两个横向面。实线是直接对应，虚线是需要改动或本就不存在对应。</figcaption>
</figure>

这些错位不说明分享的框架错了。作为演讲用的归纳，它抓住了主要矛盾；作为检查表用，需要补上 D2、D7 和两个横切面，把评估单独列为相邻系统。安全要拆成四个问题分别回答：什么能跑、什么要问、什么禁止、怎么隔离。编排要单独设计：谁生成子 agent、结果怎么汇总、失败怎么回收。

分享里有一句话，是整场的骨架："经典软件工程告诉我们，不但要关注功能需求，还要关注非功能需求。"后面关于质量、债务、验证的讨论，都是这句话在不同层面的展开。

## 二、门槛确实降了

"Vibe coding" 这个词是 2025 年 2 月出现在 X 上的，作者是 Andrej Karpathy（[2]）。当年 11 月，Collins 把它选为年度词汇（[3]）。一个带着玩笑口吻的说法，不到一年就进了词典、招聘启事和研究论文。采纳率的数据也支持这一点：DORA 2025 的报告称受访者中使用 AI 的比例达到 90%，中位数每天投入两小时；Stack Overflow 2025 的调查里，84% 的受访者正在使用或计划使用 AI（[4][5]）。

采纳率已经很高。接下来是算账：用了之后，质量、成本和责任怎么变。

分享把它概括成四个转变：过程式到声明式，语法驱动到意图驱动，线性流程到迭代式，人类主导到人机协作。这四句话在 2025 年的几项实证研究里有对应。Sarkar 与 Drosos 用八小时以上的录屏和出声思考，把 vibe coding 描述成一个迭代式的目标满足循环：开发者反复描述、运行、观察、再描述（[6]）。Chou 等人分析了 20 个视频，包括 7 场直播编码、约 16 小时、254 条提示词，发现从业者对这个词的定义本身就有分歧，"感觉对了"经常取代明确的完成标准（[7]）。Pimenova 等人的定性研究关注信任校准：效率感与对输出的信任程度相关，信任偏高时风险也随之上升（[8]）。

这些研究支持一个判断：反馈回路从"编译—测试"挪到了"描述—观察"。声明式的前提是声明得足够清楚，而清楚本身有成本。这一点会在后面反复出现。

分享也把生命周期各环节的变化列了一遍：需求用对话替代文档，设计由描述生成原型，编码变成生成加审查，测试由场景描述生成，部署在云端一键接通。这些变化在单点上都成立。问题在于，单点成本下降不等于整条链路成本下降。生命周期还是那几个阶段，变化的是每个阶段由谁执行、由谁验收。

## 三、三本账

分享把代价归成三类，像记一本账：代码质量、可维护性、技术债务。账要一笔一笔看，因为三类证据的强度不一样：质量有随机对照试验撑着，可维护性靠行业数据和厂商报告，技术债到 2026 年还多半是直觉。

### 3.1 质量：错误会随迭代累积

最常被引用的证据来自 Pearce 等人 2021 年的研究：Copilot 生成的 1,689 个程序里，约 40% 含安全漏洞（[9]）。这个数字说明初次生成的水平，不说明长期使用的情况。

更贴近日常的是迭代带来的变化。Shukla 等人用 400 个代码样本做了 40 轮"改进"，仅 5 轮迭代之后，严重漏洞增加 37.6%，不同提示策略还留下了不同的漏洞模式（[10]）。"你帮我改一下"这个动作会引入新的风险，因为每次局部改写都缺少全局不变量。

分享说的"风格不一、过度工程、缺少最佳实践"属于同一类问题，更难量化。能查到的一个侧面是自我承认的技术债：一项 2026 年的研究扫描公开仓库里 6,540 条提到大模型的代码注释，识别出 81 条开发者自认的债务，例如"测试先推后""这里只是临时方案"（[11]）。样本不大，方向清楚：债务没有消失，它被写进注释，等待某个还没排期的人来处理。

### 3.2 可维护性：成本转移给了谁

"AI 写的代码难维护"，这句抱怨这两年几乎成了口头禅。它可能对，但口头禅不能当证据。行业数据能支持其中一部分，需要说清的是相关与因果的区别。

DORA 2025 的报告给出了一组同时成立的结论：AI 采纳与交付吞吐量、产品表现正相关，与交付稳定性负相关（[4]）。报告没有做因果识别，但它对机制的解释值得引用：生成阶段省下的时间，经常被重新分配到审计与验证上。Stack Overflow 2025 的调查从开发者一侧印证了这一点：66% 的人遇到过"几乎正确但不完全对"的 AI 输出，45% 的人认为调试 AI 生成的代码更费时间（[5]）。

直接一点的证据来自评估环节。Khalid 等人的研究用 100 名参与者做远程观察，专门隔离出"评估 AI 生成代码"这一步，看人能否识别漏洞、依赖什么线索、信任如何影响判断（[12]）。这类研究问的问题很关键：生成变便宜之后，"人能不能看出问题"成为系统的单点。

工具厂商的数据也指向同一方向。CodeRabbit 在 2025 年 12 月分析了 470 个开源 PR，其中 320 个有 AI 参与撰写，AI 相关的 PR 平均每个带 10.83 个问题，纯人工的是 6.45 个（[13]）。作者自己承认，判断一个 PR 是否有 AI 参与靠的是署名信号，口径不严；这份报告也没有经过同行评审。它可以作为方向性的旁证，不能当作定论。

这些数据合起来说明的是：AI 采纳与交付效能之间没有单调关系，维护成本正在从写代码转移到读代码和验代码。因果还需要更严格的研究。

### 3.3 债务：局部改写与全局不变量

技术债这个说法最早由 Ward Cunningham 在 1992 年提出（[14]），本意是用未来的理解力换现在的交付速度，并不指"写了烂代码"。

按这个定义看 AI 生成代码，结论会清楚一些。AI 的典型行为是在原有代码上做局部修改。局部修改本身没有问题，问题在于修改时缺少一份写明全局不变量的材料。次数多了，代码就离"存在一个可以陈述的正确性论证"越来越远。

GitClear 的报告提供了结构性的侧面数据。2026 年的报告统计了 6.23 亿行变更：每百万变更行里的重复代码块从 2023 年的 40.3 升到 2026 年的 73.0；复制粘贴的代码比例从 2022 年的 9.4% 升到 2026 年上半年的 15.7%；与被移动、重构相关的代码占比从 2023 年的 13% 降到 2026 年的 3.8%（[15]）。这些是厂商自己的统计，不同版本报告对同一指标给出的数字并不一致。方向仍然清楚：新代码越来越多以复制和自成一体的小文件形式出现，被编织进既有结构的部分在变少。

证据本身也有边界。一篇覆盖 39 篇同行评审研究的系统综述指出，多数研究报告了显著收益，但证据多为自报、短期、任务级，缺乏对长期维护成本与团队级影响的度量（[16]）。能可靠测量的是任务级速度和代码级缺陷，尚不能可靠测量的是系统级演进能力。

## 四、如果开发成本趋近于零

这是现场最有价值的一个假设：如果开发成本低到可以忽略，技术债务可能就不再是大问题。

这个问题比听起来更狠。它问的其实是：既然代码可以随时重写，那些关于架构、关于可维护性的顾虑，是不是都过时了。

回答要分三步：成本结构变了什么，为什么"全部重写"救不了，以及有没有经验证据。

### 4.1 成本结构

把软件的总成本拆开，AI 压缩的只是其中一段。目前没有研究直接测量"验证成本与生成成本"的比值，最接近的是 DORA 的观察：省下的生成时间常被重新分配到审计与验证（[4]）。下面这张表是我根据前几节的证据做的分析，不是测量结果。

| 成本项 | 能否被 AI 压缩 | 原因 |
|---|---|---|
| 生成（打字） | 显著压缩 | 这是唯一被压缩的部分 |
| 理解 | 不可压缩 | 理解的对象是系统，不是文件 |
| 验证 | 反而上升 | 生成量上升，待验证面积上升；黑盒代码更难验证 |
| 数据与状态迁移 | 不可压缩 | 数据不能重新生成，只能迁移、兼容、偿还 |
| 责任归属 | 不可压缩 | 事故复盘里"模型写的"不构成解释 |

画成权重带之后，被压缩的和被放大的会更清楚（图 2）。

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig2-cost-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig2-cost-light.svg' | relative_url }}" alt="五类成本在 AI 前后的相对权重示意" width="1000" height="470" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig2-cost-dark.svg' | relative_url }}" alt="五类成本在 AI 前后的相对权重示意" width="1000" height="470" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 2 · 成本结构示意</strong>　生成变便宜之后，被压缩的只有最左边那一段；待验证的面积、数据迁移的代价、出事时的责任，都没有跟着缩小。比例是示意，不是测量结果。</figcaption>
</figure>

### 4.2 重写为什么救不了

"既然改起来贵，让 AI 重写一遍"是最自然的推论，也是最危险的。四条理由：

1. 隐性知识不在规范里。"为什么这里要加一个 sleep""为什么这个字段不能为空"，这类知识散落在提交信息、工单和离职同事的脑子里。AI 看不到，重写必然丢。
2. Hyrum 定律：有足够多的用户依赖，API 的任何可观察行为都会变成事实上的契约（[17]）。你以为是 bug 的行为，下游可能在依赖它。
3. 数据不会跟着代码走。表结构、历史脏数据、对账口径不能重新生成。
4. 你会失去唯一的验证基线。旧系统经过生产验证，是判断新系统是否等价的参照物。

### 4.3 经验证据

2025 年 7 月，METR 发布了一项随机对照试验，至今仍是这个领域设计最严格的研究之一（[18]）。参数值得写全：

- 16 名开发者，都是经验丰富的开源维护者；
- 246 个真实任务，平均耗时 2 小时，来自平均 23,000 star 的成熟仓库；
- 每个人在自己平均有 5 年经验的项目上工作；
- 任务随机分为允许用 AI 和不允许用 AI 两组；
- 工具以 Cursor Pro 加 Claude 3.5/3.7 Sonnet 为主。

结果是：开始前，开发者估计自己会快 24%；完成后，他们感觉快了 20%；实际测量，完成时间慢了 19%。外部专家的预测同样乐观，经济学家预测快 39%，机器学习专家预测快 38%。

三个数字放在一起，比任何争论都清楚：模型让人感觉更快，实际更慢，而且连当事人都察觉不到（图 3）。

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig3-metr-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig3-metr-light.svg' | relative_url }}" alt="METR 试验的三个数字：预期 +24%、体感 +20%、实测 −19%" width="900" height="360" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig3-metr-dark.svg' | relative_url }}" alt="METR 试验的三个数字：预期 +24%、体感 +20%、实测 −19%" width="900" height="360" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 3 · 预期、体感与实测</strong>　同一批开发者在同一个试验里给出的三个数：事前预测快 24%，事后自评快 20%，实测完成时间慢 19%。</figcaption>
</figure>

这项研究的工具链停留在 2025 年上半年，不能当作 2026 年能力的结论。它提供的是一条机制性提醒：当成本从生成偏移到集成与验证，更强的模型不一定让总时间下降，因为被优化的那一项占比已经很小。

推论：生成越便宜，架构越值钱。架构的作用之一是让改动的影响范围可预测。在一个能快速产出大量代码的系统里，稀缺的是在改动发生时迅速说清影响面和验证方式的能力。

## 五、Harness：把运行时当作工程对象

分享用"驾驭"来概括解法。两年前这还是个比喻；到 2026 年，它有了自己的定义，也有 11 个生产系统的源码解剖和一份跨模型的安全基准。

### 5.1 定义

前述源码研究给出的定义是：harness 是"模型之外的一切"，即把大模型与世界耦合起来的运行时，包括循环、工具、上下文、安全控制、编排、扩展面；harness engineering 是设计与演化这个运行时的学科（[1]，p.3）。这个等式不是这篇论文首创。论文自己把"agent = 模型 + harness"的流行归给 2026 年初 LangChain 系列文章的推广，术语本身在 2026 年 2 月进入流通。

这个定义有用，因为它把"AI 应用做得好不好"从模型能力问题，还原成可以逐项检查的工程结构问题。

### 5.2 七个子系统

| 子系统 | 职责 | 最小形态 | 生产形态 |
|---|---|---|---|
| D1 Agent loop | 交替推理与行动，有停止条件与故障恢复 | 对单一 bash 工具的循环 | 持久事件日志、并发工具批处理、卡死检测 |
| D2 LLM 集成 | 厂商协议、提示词组装、缓存与路由 | 一次 SDK 调用加一个模板 | 多供应商传输、缓存边界、服务端下发的提示词 |
| D3 工具与动作 | agent 能做什么，首先是文件编辑 | 只有 bash | 数十个类型化工具、延迟加载、多种编辑方言 |
| D4 记忆与上下文 | 配给上下文窗口，跨会话持久化 | 无界线性历史 | 阈值触发压缩，多数系统已收敛到此 |
| D5 安全与权限 | 什么能跑、什么要问、什么禁止，隔离执行 | 成本与步数上限 | 分层权限、模型审批审查器、操作系统沙箱 |
| D6 编排 | 生成并协调子 agent | 无 | 递归组合、扇出、跨厂商编排 |
| D7 扩展性 | 配置、hooks、skills、插件、MCP | 结构类型 | 插件市场 |

需要说明一点：D1–D7 是这篇论文提出的规范解剖，同时也是它自己的分析维度。把它当成一份可以对表的清单是合适的，当成行业标准就过了。

### 5.3 四个发现

**第一，约 100 行也能跑出接近的成绩，但那是地板。** Mini-SWE-Agent 用约 100 行代码实现了全部七个子系统，自报的基准成绩与代码量大三个数量级的系统处在同一区间（[1]）。论文特别注明这些数字是自报、模型与日期各不相同、不能直接比较。把地板与生产系统分开的指标是安全、恢复、成本管理、扩展性和平台面。

**第二，11 个生产 harness，没有一个使用 agent 框架。** 研究者在可检视的依赖清单与 import 路径上检索了 LangChain、LangGraph、LlamaIndex、AutoGen、CrewAI 等框架，没有找到任何生产代码路径使用它们，连 Gemini CLI 也跳过了 Google 自家的 Genkit 和 ADK（[1]）。作者也承认，内部 fork、动态 import、转译产物不在检查范围内。原因不难理解：agent 要改动真实源码时，静默的提示词污染、不透明的缓存、版本不兼容的工具 schema 这些故障模式代价太高。可手写、可调试的代码胜过可复用抽象。

**第三，11 个系统里没有为代码建向量检索的。** 代码带有密集的确定性结构信息（路径、LSP、tree-sitter、类型），语义相似度复制不了；代码分钟级变化，预索引很快过期；编程环境本身自带接近最优的检索器（ripgrep、find、glob）（[1]）。

**第四，同一模型换一套 harness，安全水平可以差四倍。** 一项覆盖 6 个模型、3 个 harness、128 个用例的安全基准显示，攻击成功率在 12.6% 到 80.9% 之间；GLM-5.2 在 OpenClaw 上的攻击成功率是 54.7%，换到 Nanobot 上只有 12.6%（[19]）。更值得看的是识别与处置之间的落差：MiniMax M3 在 OpenClaw 上能识别 97.9% 的风险，仍有 31.2% 的攻击成功（[19]）。这项研究的三个 harness 是"按部署原样"比较，不是受控实验，但方向足够清楚：安全属性属于模型与 harness 的组合，单看模型说明不了问题。

这四条的共同点，是把"AI 应用好不好"变成可以逐项检查的工程问题。

## 六、新秩序：四根柱子

分享给出的解法排成五层：SDD、BDD、领域建模、编排、验证机制。层数听着多，落到工程上其实只有四件事：规范写得可执行，领域模型里的不变量挑得出来，验证放在前面，失败可以恢复。

### 6.1 规范（Spec）

2026 年出现了一个正式的方法论提法：SDAD，规范驱动的 agentic 开发。这份 33 页的技术报告认为，当上下文窗口足以容纳整份需求文档与仓库上下文时，规范质量重新成为自主交付的执行燃料（[20]）。GitHub 在 2025 年 9 月发布的 Spec Kit 把这条路做成了工具链（[21]）。技术报告不是同行评审论文，这条先当作方法论主张。

测试侧有更硬的证据，而且是同行评审的。Google 的 Tufano 等人让 agent 先显式写出前置条件、后置条件和未定义行为，再生成测试，在 Google 的真实缺陷上把缺陷检出率提高了 9.8 个百分点（p=0.0352），分支覆盖率提高 2.5 个百分点（p=0.0034）；用模型做评审时，这样生成的测试有 77.8% 优于基线、56.7% 优于人工编写的测试（[22]）。

需要同时写下的是一条反向证据。前述源码研究在讨论提示词与机制的区别时给了一句判断：提示词文本是一种行为上的愿望，不是机制（[1]，p.24）。它的一个消融实验也显示，只改系统提示词会让成绩下降 2.3 个百分点。把这句话和 Tufano 的结果放在一起，结论会具体很多：规范的价值取决于它能否被编译成检查，文本本身不行。

这条思路并不新。行为驱动开发（BDD）在 2006 年就把需求写成了 Given/When/Then 的可执行格式（[23]），测试与需求共用一份描述。SDD 在 2026 年的版本多出来的东西是 agent 这一侧：规范不只给人看，还要作为生成与验收的输入。也正因为如此，复盘里"修 bug 以后就是改规范、让 AI 重新生成"的说法需要限定。规范覆盖到的地方，这个说法成立；覆盖不到的地方，仍然要回到代码、测试和生产日志。

### 6.2 领域模型

模型可以推断语法、模仿模式，业务意图的抽象仍然依赖人的判断：什么是订单、什么是"有效"、退款和撤销的区别在哪里。这一条没有引用可依，属于工程判断。

### 6.3 验证体系

验证现在是准入门槛，不是加分项。契约测试、属性测试、金丝雀发布、回滚预案、可观测性埋点，这些在手工编码时代可以慢慢补，在 AI 生成代码的场景里必须前置，因为要防的是你不会去读的那部分代码里的错误。

评估本身也成了需要专门设施的工作。HarnessRisk 那项基准测试用了 14 个模型与 harness 的组合、384 条轨迹，靠一个模型裁决器加人工标注来打分，裁决器与人工标注在主要指标上的一致率是 84% 到 93%（[19]）。这类设施不便宜，但它是把"感觉还行"换成"可以复核"的最直接办法。

### 6.4 可观测性

源码研究里有一个细节：生产系统在恢复上的投入远超预期，包括事件溯源的会话、上下文压缩、可 fork 的会话树、把失败回滚成可以重放的事件（[1]）。翻译成工程语言：可靠性来自出错时能回到上一个已知良好状态。

这个判断有实验支撑，虽然规模很小。一份 2026 年 10 月的预印本把组合性推到了跨进程：200 个任务里各注入一次进程终止，实际发生 197 次，单进程的参考实现丢掉了全部 197 个会话，跨进程实现一个都没丢；MCP 配置在断链期间空转了 1,212 次调用（[24]）。它只有一个系统、一组作者的自测，不能当成普遍结论，但它把"故障域怎么设计"从架构争论变成了可以量的东西。

把这套关系画出来，就是一条从意图到恢复的回路（图 4）。

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/harness/fig4-loop-light.svg' | relative_url }}" target="_blank" rel="noopener">
      <img class="fig-light" src="{{ '/assets/img/harness/fig4-loop-light.svg' | relative_url }}" alt="从意图到恢复的回路：意图、规范、生成、验证、发布、恢复" width="1000" height="460" loading="lazy">
      <img class="fig-dark" src="{{ '/assets/img/harness/fig4-loop-dark.svg' | relative_url }}" alt="从意图到恢复的回路：意图、规范、生成、验证、发布、恢复" width="1000" height="460" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 4 · 从意图到恢复的回路</strong>　验证是主成本，也是唯一决定"哪些改动能进主干"的环节；失败不是终点，目标是回到上一个可复现的良好状态。</figcaption>
</figure>

### 6.5 关于"新学科"

复盘里提到，卡内基梅隆大学的软件工程研究所（SEI）成立了 AI Division，INCOSE 发布了系统工程指南，标志着这成了国家级、行业级的新学科。

核查之后，这三句话都需要改。

先看 INCOSE。它在 2026 年 4 月的一份公开征集方案里写得很直接：关于 AI 在系统工程流程中何处带来真实价值、如何原生集成，以及 AI 辅助的需求、架构、验证工作适用什么治理与质量标准，目前没有权威的 INCOSE 指南（[25]）。那份被当成"指南"引用的 PDF，本身是一份征集方案的招标文件。INCOSE 能查到的是系统工程手册第 5 版，对应 ISO/IEC/IEEE 15288:2023，属于通用手册（[26]），以及期刊上的研究论文，例如把 LLM 纳入系统工程生命周期的设计模式研究（[27]）。

SEI 这边情况不同。AI Division 确实存在，成立于 2021 年 6 月，不是新设机构；SEI 是国防部门资助、卡内基梅隆大学运营的联邦资助研发中心（[28][29]）。当年的新闻稿里有一句话：SEI 正在牵头一项国家级倡议，联合产业、政府与高校推进 AI 工程这一专业学科。能支撑"国家级"的只有这句自我描述，它说的是倡议，不是学科认定。

准确的说法是：一家联邦资助研发中心把 AI 工程当作学科来建设，并自称牵头一项国家级倡议。学科化靠的是一份份具体文档，一份并不存在的指南说明不了它已经成形。

## 七、人的位置

分享的结论是：工程师从"包工头"变成"总架构师"。这个说法可以保留，但"总架构师"每天到底做什么，得说具体一点，否则它只是个好听的称谓。

三种能力正在变得稀缺：

1. 定义问题的能力。把"我想要一个更好用的后台"翻译成可验证的约束。AI 在欠指定的请求上容易过度交付。
2. 建立验证体系的能力。知道该测什么、在哪儿设闸门、什么情况下必须人工。
3. 抽象领域的能力。在变化的需求里识别稳定的不变量。

这三种能力的共同点是不产生可以展示的代码行数。在以 LOC 和 PR 数量为指标的团队里，它们会被系统性低估，直到出事。

关于中间层被抽掉的说法，目前的证据只到任务级，还不足以支撑组织层面的结论。可以确定的是：入门变便宜，验收变贵。

## 八、结语

这场分享被总结成"旧秩序在崩坏，新秩序在建立"。这个判断我同意，但想把新秩序说得朴素一点。

新秩序的内容是为 AI 写软件所需要的那套工程。它没有发明新原理，做的是把经典软件工程里那些显得啰嗦的东西（权限、约束、恢复、可观测、验收标准、非功能需求）从加分项变成准入条件。执行者从会犯错的工程师换成了不会累但也不会负责的模型，这个变化足够大。

核心资产也随之挪了位置。手写代码的年代，代码本身就是资产；现在更值钱的是规范、领域模型、验证体系，以及"什么不可改变"这类判断。它们都不产生代码行数。

Vibe coding 降低了进入成本。harness 决定这套系统能走多远，也决定出问题的时候，能不能退回昨天。

## 九、事实核查说明

复盘里可验证的说法，逐条查过，有五处需要改口径。改法都写在这里，连同查不到的部分一起。

1. "INCOSE 发布了系统工程指南"不成立。INCOSE 自己在 2026 年 4 月的征集方案里写明没有权威指南，被引用为指南的文件是招标文书。
2. "SEI 成立 AI Division"成立，但时间是 2021 年 6 月；"国家级学科"只能落到 SEI 自称牵头一项国家级倡议。
3. "验证成本大于生成成本"没有直接测量支持。正文改用 DORA 的表述：生成省下的时间常被重新分配到审计与验证。
4. 网上流传的 DORA 2024 系数（AI 采纳率每提高 25%，吞吐量下降 1.5%、稳定性下降 7.2%）本次未能与报告正文核对，正文没有采用。
5. "AI 代码缺陷率是人工 N 倍"不采用。能追到的倍数是安全扫描器的漏洞发现数或每个 PR 的问题数，口径不同。

另有两处证据需要限定范围。METR 的实验用的是 2025 年上半年的工具链，结论适用于"资深开发者在自己熟悉的成熟仓库上工作"这一条件。HarnessRisk 的跨 harness 安全比较是按部署原样做的，不是受控实验。

文中每一条数值都能按参考文献回查；核查中放弃的数字和理由，也都写在这一节里。

## 参考资料

[1] Barbaste, P., Darrigol, T., Vu, G., & Wiltberger, T. (2026). *Harness Engineering: Anatomy, Architecture, and Evolution of Coding Agents — A Source-Code Study of Eleven Systems*（预印本）. arXiv:2609.00006. <https://arxiv.org/abs/2609.00006>
[2] Karpathy, A. (2025-02-02). *"There's a new kind of coding I call 'vibe coding'"*. <https://x.com/karpathy/status/1886192184808149383>
[3] *Vibe coding picked as Collins' Word of the Year 2025*（TASS，2025-11-06）. <https://tass.com/society/2040125> ｜ 官网页面存档：<https://web.archive.org/web/20251209085408/https://www.collinsdictionary.com/woty>
[4] DORA. *State of AI-assisted Software Development*（2025 报告）；*Balancing AI tensions: Moving from AI adoption to effective SDLC use*（洞察文章）. <https://dora.dev/insights/balancing-ai-tensions/>
[5] Stack Overflow. *2025 Developer Survey — AI*. <https://survey.stackoverflow.co/2025/ai>
[6] Sarkar, A., & Drosos, I. (2025). *Vibe coding: programming through conversation with artificial intelligence*. arXiv:2506.23253. <https://arxiv.org/abs/2506.23253>
[7] Chou, Y.-H., Jiang, B., Chen, Y. W., et al. (2025). *Building Software by Rolling the Dice: A Qualitative Study of Vibe Coding*. arXiv:2512.22418. <https://arxiv.org/abs/2512.22418>
[8] Pimenova, V., Fakhoury, S., Bird, C., et al. (2025). *Good Vibrations? A Qualitative Study of Co-Creation, Communication, Flow, and Trust in Vibe Coding*. arXiv:2509.12491. <https://arxiv.org/abs/2509.12491>
[9] Pearce, H., Ahmad, B., Tan, B., Dolan-Gavitt, B., & Karri, R. (2021). *Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions*. arXiv:2108.09293. <https://arxiv.org/abs/2108.09293>
[10] Shukla, S., Joshi, H., & Syed, R. (2025). *Security Degradation in Iterative AI Code Generation — A Systematic Analysis of the Paradox*. IEEE-ISTAS 2025. arXiv:2506.11022. <https://arxiv.org/abs/2506.11022>
[11] Al Mujahid, A., & Imran, M. M. (2026). *"TODO: Fix the Mess Gemini Created": Towards Understanding GenAI-Induced Self-Admitted Technical Debt*. arXiv:2601.07786. <https://arxiv.org/abs/2601.07786>
[12] Khalid, H., Thompson, R. E., Sabater, A., et al. (2026). *(Don't) Trust, but (Don't) Verify: Developers' Attention to Security in AI-Generated Code*. arXiv:2609.21020. <https://arxiv.org/abs/2609.21020>
[13] CodeRabbit. (2025-12-17). *State of AI vs Human Code Generation*. <https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report>
[14] Cunningham, W. (1992). *The WyCash Portfolio Management System*. OOPSLA '92 Experience Report. DOI: 10.1145/157709.157715
[15] GitClear. (2026). *The AI Code Quality Maintainability Gap*. <https://www.gitclear.com/the_ai_code_quality_maintainability_gap>
[16] Mohamed, A., Assi, M., & Guizani, M. (2025). *The Impact of LLM-Assistants on Software Developer Productivity: A Systematic Review and Mapping Study*. arXiv:2507.03156. <https://arxiv.org/abs/2507.03156>
[17] Wright, H. *Hyrum's Law*. <https://www.hyrumslaw.com/>
[18] Becker, J., Rush, N., Barnes, B., & Rein, D. (2025). *Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity*. METR. arXiv:2507.09089. <https://arxiv.org/abs/2507.09089>
[19] Bai, Y., Duan, J., Peng, J., Wu, X., Liu, S., Wang, S., & Chen, T. (2026). *HarnessRisk: A Lifecycle-Oriented Benchmark for Agent Harness Safety*（预印本，审稿中）. arXiv:2608.17597. <https://arxiv.org/abs/2608.17597>
[20] Nguyen, V. H., & Nguyen, T. (2026). *SDAD: Spec-Driven Agentic Development for the AI-Native SDLC*（技术报告，非同行评审）. arXiv:2608.20341. <https://arxiv.org/abs/2608.20341>
[21] GitHub. (2025-09-02). *Spec-driven development with AI: get started with a new open source toolkit*. <https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/>
[22] Tufano, M., McClure, J., Cambronero, J., et al. (2026). *Grounding AI Agents in Contracts: An Empirical Evaluation of Spec-Driven Test Generation*. SpecOps '26. DOI: 10.1145/3842652.3843195. arXiv:2608.17177. <https://arxiv.org/abs/2608.17177>
[23] North, D. (2006). *Introducing BDD*. <https://dannorth.net/blog/introducing-bdd/>
[24] Jia, H., Zeng, L., Cheng, H., Gao, Y., Ma, B., & Xu, G. (2026). *Composition without a Host: Carrying the Spatiotemporal-Composability Guarantee of Plugin-Based Agents across Processes*（预印本）. arXiv:2608.28553. <https://arxiv.org/abs/2608.28553>
[25] INCOSE. (2026-04-08). *AI in SE Practice: Use Cases, Native Integration Patterns, and Quality Governance*（Call for Solutions，CFS-C5-02）. <https://www.incose.org/wp-content/uploads/2026/04/CFS-C5-02.pdf>
[26] INCOSE. *INCOSE Systems Engineering Handbook*, 5th ed.（对应 ISO/IEC/IEEE 15288:2023）. <https://www.incose.org/products-and-publications/se-handbook>
[27] *A Design Pattern Catalog for Applying Large Language Models in the Systems Engineering Lifecycle*. INCOSE, *Systems Engineering*. DOI: 10.1002/sys.70094. <https://doi.org/10.1002/sys.70094>
[28] Carnegie Mellon University, Software Engineering Institute. (2021-06-28). *Software Engineering Institute Announces Establishment of New AI Division, Names Director*. <https://www.sei.cmu.edu/news/software-engineering-institute-announces-establishment-of-new-ai-division-names-director/>
[29] Carnegie Mellon University, Software Engineering Institute. *About the SEI*. <https://www.sei.cmu.edu/about/>

---
*说明：文中标注编号的数值与结论来自上述来源。第九节列出了需要改口径的说法与证据边界。*
