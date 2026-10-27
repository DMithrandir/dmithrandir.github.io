---
layout: post
title: "短视频风险自动审核 Agent 方案"
date: 2026-10-27 10:13:00 +0800
categories: 治理框架
series: governance
series_part: 13
nav_title: "应用 · 短视频审核 Agent 方案"
tags: [内容治理, Agent, 方案设计, 编排]
permalink: /governance/13-agent/
description: "五层结构、与框架的对齐、学术与工业锚点；主干用 Event Flow，ReAct 只作局部判据。"
excerpt: "五层结构、与框架的对齐、学术与工业锚点；主干用 Event Flow，ReAct 只作局部判据。"
---

> 定位：**把一份 Agent 审核方案与已有框架、学术与工业实践做对齐**。原方案的框架完整，本篇做三件事：① 与 M0~M9 逐点对齐；② 补学术与工业依据；③ **标注 7 处需要校准的地方**（这部分最有价值）。
> 关联模块：M2（级联架构）· M3（召回）· M6（对抗）· M1（风险定义）· M9（举报）· M5（申诉）

---

## 〇、原方案的核心判断（保留并强化）

原方案的立论是**两个约束**下的一个架构选择：

| 约束 | 原方案表述 | 框架内的对应 |
|---|---|---|
| **量大**| 必须靠三级漏斗，把 LLM 调用量压到 **5%~10%**| M2 §〇「吞吐是稀缺资源」 |
| **风险碎片化**| 藏在**关键帧 / 片段 / 组合**里，传统分类器只能被动打分 | M0 §2.2「感知半径」 |

**原方案的收尾判断我认为是整个方案最值钱的一句，建议作为全文纲领**：

> **LLM Agent 在这个场景里的核心价值不是"更准的分类器"，而是有能力做推理和主动取证。这个能力的代价是延迟和成本，所以三级漏斗的分流设计是整个方案能真正落地的前提条件，不是锦上添花，是必要条件。**

**⚠️ 而这个"必要条件"有多硬，可以用 M2 的实测数字量化**（原方案没给）：

| 参照 | 数值 | 含义 |
|---|---|---|
| 快手 KuaiMod（视频多帧 VLM 判定） | 48×RTX4090 / **QPS 6.81**→ 单卡约 **7 秒/条**| 视频级 VLM 判定是**秒级到十秒级**|
| 淘天生鲜（单图 VQA） | 双卡 L20 约 **10 QPS**（约 **0.2 秒/条**） | 图片级判定是**亚秒级**|
| 两者差距 | **约 35 倍**| 视频多帧 VLM 比图片审核贵一到两个数量级 |

→ **所以"5%~10% 进 L3"不是保守，而是上限**。如果 L3 是完整的多轮 Agent（多工具调用），实际可承担的比例还要更低。

---

## 一、风险定义层

### 1.1 原方案的最大增量：隐性风险的三种类型

**这是我认为原方案对本系列最有贡献的一点**——它给出了一个**可操作的隐性风险分类**，而这正是 M1 标签体系里最缺的维度：

| 类型 | 定义 | 例子 | 检测含义 |
|---|---|---|---|
| **关键帧型**| 整个视频只有一两帧有问题 | 夹带一帧违禁图、**0.5 秒**的刀片特写 | 需要**定位到帧**，均匀采样必漏 |
| **片段型**| 某几秒连续才构成完整风险语义 | **3 秒内**同时出现诈骗话术音频 + 引流文字 | 需要**时序建模**，单帧看不出 |
| **组合型**| 单模态看都正常，多模态叠加才违规 | 视频无害，但配合**评论区挂联系方式**形成引流 | 需要**跨模态关联推理**|

**⚠️ 这三类与 M1 的标签体系是正交的**，这是本次整合最重要的结构性发现：

```
M1 标签体系回答的是「这是什么风险」（色情/诈骗/侵权…）
隐性风险三分类回答的是「风险藏在哪种结构里」（帧/片段/组合）

→ 两者应当做成交叉矩阵，而不是互相替代
```

| 若只有标签，没有类型 | 若只有类型，没有标签 |
|---|---|
| 知道是"诈骗"，但不知道它藏在 3 秒片段里 → **采样策略会漏**| 知道要逐帧扫，但不知道扫什么 → **没有判定依据**|

**建议的落地形态**：在 M1 的标签体系里为每个标签追加一个 **`detection_shape`（风险形态）**字段，取值 `global / keyframe / segment / crossmodal`。**这个字段直接决定采样策略与判定链路**：

| detection_shape | 采样策略 | 判定链路 |
|---|---|---|
| `global` | 均匀采样即可 | 分类模型足够 |
| `keyframe` | **高熵帧定位 + 逐帧扫描**| 需要帧级定位能力 |
| `segment` | **时序滑窗 + ASR**| 需要时序建模 |
| `crossmodal` | 多模态全取 | **必须上 Agent 做关联推理**|

**一手印证**：快手安全团队明确把"**多维度信息组合违规证据**"列为长链推理的核心场景，并给了一个与"组合型"完全同构的例子——**昏暗夜店场景 + "招聘/工资"封面文字 → 色情招嫖联想**（单看画面正常、单看文字正常）。

### 1.2 风险分级 P0~P3：与框架的对应

| 原方案分级 | 处置要求 | 框架内对应 | 工业参照 |
|---|---|---|---|
| **P0 违法**（儿童性剥削、恐怖主义） | 实时拦截，零容忍 | M1「法律底线」：**不可个性化**| KuaiMod：明确违法的**严格过滤**|
| **P1 高危**（诈骗、赌博、自伤） | **1 分钟内**| 同上 + 时效硬约束 | 快手直播：识别时效**秒级**|
| **P2 违规**（侵权、灰产引流） | **10 分钟内**| M1「生态水位」：可限流可个性化 | KuaiMod:移出推荐池 |
| **P3 边界内容**| 1 小时人工复核 | M1「处置光谱」中的标注/预警 | 快手"剧本炒作"：弹窗/遮罩/断播 |

**原方案对分级意义的表述很准**——"不能用处理 P0 的成本去处理所有视频"。这在框架里对应 M4 §5.2 的**指标三元组**思路：**分级就是对资源分配的显式声明**。

⚠️ **一处建议补充**：原方案的 P0~P3 是**按严重程度**分级，但 M2 §4.1 指出**阈值必须按风险类分别标定**，因为**基础率差异极大**（RADAR 实测线上正例率从 **9.0%**（虚假互动）到 **25.5%**（低质））。
→ **建议分级矩阵是二维的**：`严重程度（P0~P3）× 风险类（基础率）`。同一 P 级下，基础率低的类目要更宽的采样、更低的阈值。

---

## 二、识别层：三级漏斗

### 2.1 与 M2 三级级联的对齐

原方案的 L1/L2/L3 与 M2 §2.2 的分层几乎一一对应，但**侧重点不同**——这一点值得说清：

| | M2 三级级联 | 原方案三级漏斗 | 差异 |
|---|---|---|---|
| L1 | 规则层（词典/正则/图谱） | **轻量快筛**（指纹黑库 + 封面/标题分类 + 概率预估） | 原方案**把"概率预估"也放进 L1**，比 M2 更进一步 |
| L2 | 轻量判定（0.6B~8B 多标签头） | **智能采样打分**（高熵帧 + 多模态特征 + 传统分类模型） | 原方案**在 L2 显式引入采样策略**，M2 未展开 |
| L3 | 精判（大模型/VLM/判例 RAG） | **深度理解 Agent**（证据采集 + 局部判据推理） | **原方案的 L3 是 Agent 而非单次推理**—— 但编排应为 Event Flow，见 §2.4 |

**工业对标**：
- **TikTok Filter-And-Refine**（ACL 2025 Industry）：router–ranker 级联，**F1 +66.5%**（仅 2% 微调数据）、自动审核量 **+41%**、**算力压到全量直推的 1.5%**
- **Joom**：一级用调优的小档模型批量筛掉"确定干净"，二级**仅在置信不足时**唤醒大模型；日处理 **2 万 → 200 万件（100×）**且**成本持平**
- **RADAR**（ACL 2026 Industry）：**旁路 >80% 流量**

→ 原方案的"**L1 过滤 60% → L2 后剩 5%~10%**"与这些工业数据**量级一致**，是可信的目标。

### 2.2 ⚠️ 校准点 1：L1 的 50ms 是"架构红线"，不是优化目标

原方案设定 L1 在 **50 毫秒**内完成。这个数字**在架构上意味着 L1 不能用生成式模型**，建议把这条推论显式写出来：

| 方案 | 延迟量级 | 能否满足 50ms |
|---|---|---|
| 纯判别式 / 双向模型 + ONNX Runtime **INT8 + CPU**| 约 **10~50 ms**（工程经验值，需自测） |  可以 |
| 322M 双向判定模型（COGNIT-Guard，单 NPU） | **21.77 ms / 45.90 QPS**|  可以 |
| 0.5B~4B 生成式小 LLM（vLLM + FP8） | 数十~数百 ms | ❌ 很难 |
| 完整 VLM 多帧判定 | 秒级（KuaiMod 单卡约 7 秒） | ❌ 不可能 |

**建议表述**：
> **50ms 约束实际上把 L1 锁定为"判别式模型 + CPU/INT8"路线**（M2 §6.3 的引擎分工）。这也解释了为什么 L1 的三件事——指纹比对、封面/标题分类、概率预估——**都是判别式任务**，没有一件需要生成。

**⚠️ 并建议对"50ms"补充限定**：这个数字应明确是 **P50 还是 P99**。按 M4 §3.4 的口径要求，**审核链路的延迟指标必须报 P99**——因为流量是海量的，P50 达标但 P99 失控会导致队列堆积。

### 2.3 L2 的智能采样：这是有学术支撑的成熟方向

原方案提出的"**聚焦高信息熵帧（画面突变、人脸出现、字幕出现）**"不是工程直觉，而是一个**有专门研究线的方向**：

| 工作 | 做法 |
|---|---|
| [Adaptive Keyframe Sampling for Long Video Understanding（CVPR 2025）](https://ar5iv.labs.arxiv.org/html/2502.21271) | 自适应关键帧采样，用覆盖率函数指导选帧 |
| [STEC: Spatio-Temporal Entropy Coverage（WACV 2026 Workshop）](https://www.openaccess.thecvf.com/content/WACV2026W/WVAQ/papers/Lin_STEC_A_Spatio-Temporal_Entropy_Coverage_Metric_for_Evaluating_Sampled_Video_WACVW_2026_paper.pdf) | **提出"时空熵覆盖率"指标**，专门用于**评估采样帧质量**|
| [FOCUS: Efficient Keyframe Selection for Long Video Understanding](https://browse-export.arxiv.org/pdf/2510.27280) | 长视频关键帧选择 |
| [CUEKFS: Agentic Cue-Driven Keyframe Selection](https://browse-export.arxiv.org/pdf/2609.31873) | **用 Agent 做 cue 驱动的选帧**|
| [AdaptToken: Entropy-based Adaptive Token Selection](https://www.semanticscholar.org/paper/AdaptToken%3A-Entropy-based-Adaptive-Token-Selection-Qi-Qu/d71a87fc2f652bf5f03fbf9d986836531234883e) | MLLM 长视频理解的熵基 token 选择 |

⚠️ **两点可直接用上的收获**：

1. **"STEC 时空熵覆盖率"给了 L2 一个可监控的质量指标**。原方案只说了"智能采样"，但**没定义怎么评估采样好不好**。建议把 STEC 类指标纳入 L2 的过程指标——**采样质量直接决定 L3 的输入质量**，而 L3 是成本最高的一环
2. **采样策略本身可以用 Agent 做**（CUEKFS 的思路），这与原方案 L3 的"Agent 主动取证"形成呼应——**Agent 不只是判定者，也可以是采样决策者**

**补充一条原方案没写但重要的采样原则**：

| 视频长度的处理 | 建议 |
|---|---|
| 短视频（<60s） | 全帧率高采样，成本可接受 |
| 中长视频（1~10min） | 高熵帧定位 + 分段覆盖 |
| 长视频（>10min） | **两级：先粗扫定位候选区间，再对候选区间逐帧**（原方案的"视觉突变检测定位高熵区间再逐帧扫描"正是这个思路） |

**快手 KuaiMod 的对照**：其状态转移工作流是"描述/标题/OCR/ASR **依次**排查"（M2 §6.4 的降维路径）——**把多模态压成"文本 + 少量关键帧"，让文本小模型承担主要判定负载**。这是 L2 成本控制的另一条路，可作为备选。

### 2.4 架构选型：Event Flow 为主干，ReAct 只作局部判据

> **本节 2026-10-25 重写**。原版把 L3 直接写成"ReAct Agent"，经调研后修正为：**控制流应放在编排层（Event Flow），而非 LLM 内部（ReAct）**。这是本方案最大的架构改动。

#### 2.4.1 先把概念对齐：差别在"控制流放在哪"

| | **ReAct**| **Event Flow**|
|---|---|---|
| 控制流位置 | **在 LLM 内部**——模型自己决定下一步 | **在外部**——状态机 / 事件流决定路径 |
| 机制 | Think → Act → Observe → 循环 | 事件触发 → 状态转移 |
| 终止条件 | **由模型决定**（可能不收敛） | **由流程定义**（必然终止） |
| 谁负责"下一步" | 模型 | 编排层 |

**这个区分不是我的发明**。Anthropic 在《Building effective agents》里用 **workflows vs agents**命名了同一条边界：

> "**Workflows are systems where LLMs and tools are orchestrated through predefined code paths. Agents, on the other hand, are systems where LLMs dynamically direct their own processes and tool usage.**"
> —— [Anthropic Engineering, 2024-12](https://www.anthropic.com/engineering/building-effective-agents)

**换句话说**：ReAct 是"让模型决定下一步"，Event Flow 是"让流程决定下一步"。

#### 2.4.2 六条理由，为什么治理场景必须选 Event Flow

**前两条关于成本与时效，后四条更硬——它们关乎「能不能被审计」。**

| # | 理由 | 依据 |
|---|---|---|
| **1**| **延迟不可预测 → SLA 无法承诺**| ReAct 轮数不定；本方案 P1 要求 1 分钟处置，ReAct 给不出保证。Event Flow 路径长度已知，**延迟可预先算出**|
| **2**| **成本不可预算 → 单件成本模型失效**| ReAct 的 token 消耗逐例变动；本方案要求 L3 只吃 5%~10%，必须能算单件成本 |
| **3**| **不可审计 → 申诉复核做不出来**| 治理判定会被申诉（M5）、被监管问询。ReAct 的推理路径是运行时生成的，事后难复盘"它为什么这么判"；Event Flow 每步是**有名字的状态转移，天然留痕**|
| **4**| **不可回归 → 每周迭代无法验证**| 本方案要求"每周一版 + A/B 灰度 + 不能劣化"。ReAct 行为随 prompt 微调漂移，回归测试覆盖不了；Event Flow 每条路径**可独立测试**|
| **5**| **不可局部修复 → 维护成本失控**| 发现某类规避手法，ReAct 只能改 prompt 祈祷；Event Flow 可以**只修那一条转移**|
| **6**| **无界探索 → 本身就是攻击面**| 见 §2.4.6：ReAct 的开放性正是「容量型 DoS」（校准点 C8）的成因 |

**第 3、4 条是关键**。金融与监管领域的实践说得最直白：

> "When a regulator questions what happened with a particular business process, the business must be able to answer exactly what happened, when, and why, and **reproduce the results**. Anyone who has tried to demo an agent being given complete control over a task will be able to tell you that understanding the reasons for its outputs is often challenging, and **reproducing exact results is next to impossible.**"
> —— [Auditable Agentic Orchestration, Scott Logic, 2026-07](https://blog.scottlogic.com/2026/07/08/auditable-agentic-orchestration.html)

而这正是治理场景的处境：**每一次处置都可能在几周后被申诉**，那时你需要重放证据链，而不是重跑一次不确定的推理。

#### 2.4.3 工业界已经做出这个选择

**① Anthropic 的默认建议：能用流程就不用 Agent**

> "**We recommend finding the simplest solution possible, and only increasing complexity when needed. This might mean not building agentic systems at all.**"

它还给出了**自主动 Agent 成立的强条件**——而这条恰好把审核排除在外：

> "**Code solutions are verifiable through automated tests**; agents can iterate on solutions using test results as feedback."
> 即：**有客观、快速反馈闭环的任务，才是自主动 Agent 收益最大的地方。**

⚠️ **治理不是这种任务**：审核的反馈是**延迟的、稀疏的、有偏的**（申诉要等用户反应过来，且只有部分人会申诉——M5 §1.1 的选择偏差）。**所以 ReAct 在治理场景缺少它赖以成立的那块地基。**

**② 状态机是信任与安全领域的既有选型**

NVIDIA NeMo Guardrails 的护栏语言 Colang 官方定义就是 **event-driven**：

> "Colang is an **event-driven interaction modeling language**."
> "the guardrails layer responsible for **recognizing and enforcing patterns within the stream**of events"
> —— [Colang Architecture Guide](https://docs.nvidia.com/nemo/guardrails/configure-guardrails/colang.md)

AWS 官方的 Trust & Safety 参考实现也直接选了状态机：

> "combines **event-driven processing**, **parallel evidence gathering**, confidence-scored decision making, and automated enforcement... with human-in-the-loop escalation"
> 技术栈：Lambda（事件）+ **Step Functions（状态机编排）**+ Bedrock + DynamoDB
> —— [aws-samples/sample-trust-safety-orchestration-agent](https://github.com/aws-samples/sample-trust-safety-orchestration-agent)

⚠️ **一个值得注意的工程细节**：那份样例的**成本模型是按状态转移计费**（$0.025 / 1,000 transitions），**不是按 token**。整个成本因此可预测、可预算——这正好匹配本方案"L3 只能吃 5%~10%"的硬约束。

**③ 生产环境的失败数据：纯 ReAct 是"烧钱三件套"之一**

一份基于数千条生产 trace 的工程复盘，把三种模式列为"我们劝团队停用"：

> - **Pure ReAct loops with no step budget.**"The classic ReAct pattern is fine. **ReAct with no max-step parameter is not. It will loop forever on edge cases.**"
> - **Fully autonomous "the agent decides what to do."**"Almost never the right shape in production. You sacrifice every debugging affordance for a system that is **hard to constrain, hard to evaluate, and produces wildly inconsistent results on similar inputs.**Use this pattern only when **the problem space genuinely cannot be decomposed.**"
> - **Recursive subagent spawning.**"a session in production that spawned 47 subagents and cost $89 to answer one user question."
> —— [Agent Workflow: 5 Production Patterns and the Failure Modes Behind Them, 2026](https://www.respan.ai/articles/agent-workflow)

**两个可直接引用的量化经验**：

| 指标 | 经验值 |
|---|---|
| **步骤数**| "For most production workflows, **p50 should be under 5 steps and p99 under 15**. Anything above 15 routinely is a sign your decomposition is wrong." |
| **必须设四重上限**| token cap / step cap / tool-call cap / wall-clock cap —— "The first one that trips returns a graceful failure." |

⚠️ 它还点了一个我们容易踩的坑：**"Step budget set in tokens only"是反模式**——token 上限抓不住"便宜但高频"的循环（比如把下游 API 打 200 次）。**所以本方案的预算必须同时卡工具调用次数。**

**④ 结论性判断**

> "**Agents decide how, workflows decide when, where and under what constraints.**"
> "If 2025 was the year of the enterprise agent, **2026 will be the year of the workflow.**"
> —— [Scott Logic](https://blog.scottlogic.com/2026/07/08/auditable-agentic-orchestration.html)

#### 2.4.4 ⚠️ 反面：ReAct 什么时候仍然是对的

**不做单边论证。ReAct 在三种情况下仍然是更优解**：

| 场景 | 为什么 ReAct 更优 | 对治理的启示 |
|---|---|---|
| **问题空间确实无法预先分解**| 没人知道要查什么，只能边查边定 | **新型风险的第一批样本**属于此类 |
| **反馈快且可验证**| 有自动测试/客观信号，能快速试错收敛 | 治理**没有**这个条件（反馈延迟且有偏） |
| **证据采集清单无法枚举**| 步骤本身取决于前一步结果 | 取证**大多能枚举**（见 §2.4.5） |

**所以正确的结论不是"ReAct 错了"，而是**：
> **ReAct 的能力是"主动取证"，但这个能力不依赖"用 ReAct 来编排"。**
> **工具调用能力与 ReAct 范式是正交的两件事。**

#### 2.4.5 本方案的建议形态：确定性骨架 + 局部智能

**先把原方案那个五步执行过程拿出来看**：

> 看标题封面 → 发现"挣钱秘诀"+现金 → 产生怀疑 → **然后**调 ASR → 发现第 23 秒"加我微信每天稳定500" → 确认有引流音频后，**再**调 OCR → 扫 22~24 秒 → 发现二维码 → 输出报告

注意那几个"**然后**""**确认…后，再**"——**这些条件转移是确定性的，不需要 LLM 裁决**。它们本来就是状态机。

**而证据采集的搜索空间是"可枚举"的**：

| 条件 | 必然动作（不需要模型决定） |
|---|---|
| 有音频轨 | 必须 ASR |
| 有画面文字 | 必须 OCR |
| 疑引流水印 | 必须扫二维码 / 短链 |
| 疑单帧违规 | 必须高熵定位 + 逐帧 |

**真正需要判断的只有一处**：**"我攒到的证据够不够定级？"**← 这才是该让 LLM 做的事。

**建议架构**：

```
Event Flow 骨架（确定性，路径可枚举）
  │
  ├─ [事件] 上传 → [状态] L1 快筛 ──确定安全──→ 放行
  │                      │
  │                      └─存疑→ [状态] L2 采样打分
  │                                  │
  │                                  └─存疑→ [状态] 证据采集（并行扇出）
  │                                            ├─ ASR
  │                                            ├─ OCR
  │                                            ├─ 帧级扫描
  │                                            └─ 语义检索 / 判例
  │                                                  │
  │                                                  ↓
  │                            ★ [判据节点] 证据充分性判断
  │                               ← 这里才叫 ReAct 式局部推理
  │                                                  │
  │                            ┌─────────────────────┴─────────────┐
  │                          充分                                不足
  │                            ↓                                  ↓
  │                    [状态] 定级 → 处置              定向补证（≤2 轮，超限转人工）
```

**三条约束，缺一不可**：

| 约束 | 内容 | 依据 |
|---|---|---|
| **① 工具过滤（Tool Filtering）**| 每个状态**只暴露该状态允许的工具**，而不是把全部工具丢给模型 | "A workflow can control which tools an agent has access to at each step. This prevents the failures that occur when agents receive too many options at once and **enforces least privilege at the architectural level**."（[Ken Priore](https://kenpriore.com/the-power-vs-control-tradeoff-in-workflow-design-now-with-agents/)） |
| **② 边界外不可触发**| **处置动作（删除/封号）必须在 Agent 子流程边界之外**，Agent 只能提"建议定级" | "The Agentic Subprocess draws a clear boundary which defines exactly which activities any given agent is allowed to carry out. Tasks outside of the boundary are not available to the agent."（Scott Logic）—— 其贷款例子中，**批准/拒绝贷款就在边界外**|
| **③ 四重预算 + 降级**| token / step / tool-call / wall-clock 四个上限，任一触发即**优雅降级为"存疑转人审"**| respan 的四重上限 + 本方案的 SLA 硬约束（校准点 C6） |

⚠️ **约束 ② 是这次改动里最重要的一条**：它把"Agent 会不会误删内容"这类风险**从设计上消掉**，而不是靠 prompt 约束。**Agent 没有处置权，只有建议权。**

#### 2.4.6 这个改动顺带消掉了 C8 攻击面

上一版把「Agent 护栏的容量型 DoS」列为校准点 C8：攻击者批量制造"存疑但不违规"的内容，把流量挤进 L3 打满容量。

**用 Event Flow 后，这个问题从"需要额外防守"变成"架构自带"**：

| 原来（ReAct） | 现在（Event Flow） |
|---|---|
| 无界探索 → 需要额外加预算补丁 | **路径长度固定，预算约束是架构自带的**|
| L2→L3 转化率可能被攻击推高 | 状态机可**按状态限流**（每个状态的并发独立计） |
| 降级要做成异常处理 | 降级是**正常状态转移**（超预算 → 转人审） |

**结论**：ReAct 的自由度在审核场景里是**负债而非资产**——它把一个可以靠架构消除的风险，变成了必须靠运维监控的风险。

#### 2.4.7 决策表：什么时候用哪个

| 判据 | 选 Event Flow | 选 ReAct |
|---|---|---|
| 步骤能否枚举 | 能（多数审核场景） | 不能（全新风险） |
| 反馈是否快且可验证 | 否（审核：延迟+有偏） | 是（代码/数学：自动测试） |
| 是否需要事后重放 | **必须**（申诉/监管） | 可选 |
| SLA | 硬（P1 1 分钟） | 软 |
| 单件成本是否要预算 | 必须 | 可容忍波动 |
| 工具集是否可预知 | 能预知 | 无法预知 |

**实践规则（可直接用）**：
> **从最受限的形态出发，只在测量证明"约束就是瓶颈"时才放松。**
> "start with the most constrained pattern that solves your problem, then loosen the constraints only when measurement says the constraint is the bottleneck."（respan）

### 2.5 学术与工业锚点汇总
| 方向 | 工作 | 对本方案的意义 |
|---|---|---|
| **架构边界**| [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | **workflows vs agents**的正式命名；"能用流程就不用 Agent"；自主动 Agent 需"快且可验证的反馈"（审核不具备） |
| **可审计编排**| [Scott Logic: Auditable Agentic Orchestration](https://blog.scottlogic.com/2026/07/08/auditable-agentic-orchestration.html) | "Agents decide how, workflows decide when/where/under what constraints"；**Agentic Subprocess 边界**；"governed autonomy" |
| **生产失败模式**| [respan: 5 Production Patterns](https://www.respan.ai/articles/agent-workflow) | 纯 ReAct 是"烧钱三件套"；**p50<5 步 / p99<15 步**；四重上限；token-only 预算反模式 |
| **权力 vs 控制**| [Ken Priore: power vs control](https://kenpriore.com/the-power-vs-control-tradeoff-in-workflow-design-now-with-agents/) | **Tool Filtering**（每步只暴露允许的工具）；"代码即证据" |
| **护栏语言**| [NVIDIA Colang](https://docs.nvidia.com/nemo/guardrails/configure-guardrails/colang.md) | 护栏厂商的正式选型是 **event-driven flow language**|
| **T&S 参考实现**| [AWS sample](https://github.com/aws-samples/sample-trust-safety-orchestration-agent) | Step Functions 状态机 + 并行取证；**按状态转移计费**|
| **Agent 范式原始论文**| ReAct（Reason + Act） | 仍是"局部判据"节点的理论基础，但不是编排范式 |
| **级联成本**| [FrugalGPT](https://arxiv.org/abs/2305.05176)：降本最高 98% | 支撑三级漏斗的经济性 |
| **路由**| [RouteLLM](https://arxiv.org/abs/2406.18665)：降本 2 倍以上 | 支撑 L1→L2→L3 路由 |
| **审核专用路由指标**| [RADAR](https://aclanthology.org/2026.acl-industry.139/)：**APR@R90/R95**、**R@P60**| 原方案缺一套"漏斗效率"评测指标，可直接采用 |
| **校准**| [CAUC](https://arxiv.org/abs/2609.11446)：跨模型置信度必须先校准；精度 +1.9% 且省 47% 强模型调用 | "低置信走 Agent"依赖置信度可比（校准点 C3） |

---

## 三、准入层

### 3.1 "限流发布"：原方案最漂亮的设计，且有一手数字支撑

原方案的核心创新是：**不是非 0 即 1 的拦截/放行，中间有一档"限流发布"作为缓冲。**

**这个设计在框架里对应 M1 §1.5 的「处置光谱」**，而且有**直接的收益数字**：

> **快手 KuaiMod 把判定结果嵌入推荐特征（即"不删除但区别化分发"），线上 A/B 得到 DAU +0.028%、人均 AUT +0.033%、总 AUT +0.063%。**

⚠️ **KuaiMod 原文的边界必须一起写**：
> **只有部分违规类型可以保留用于个性化推荐；明确违法或造成严重危害的视频被严格过滤。**

→ **所以"限流缓冲"的适用范围应该与 P 级绑定**：

| 分级 | 能否用限流缓冲 |
|---|---|
| **P0 违法**| ❌ **不能**——严格过滤，不可个性化 |
| **P1 高危**| ⚠️ 谨慎——可短时限流但需快速转处置 |
| **P2 违规**|  适用 |
| **P3 边界**|  最适用——限流 + 人工复核 |

**这个映射是原方案应该补上的**——它能让"限流缓冲"从"一个巧妙设计"变成"**有边界的可执行策略**"。

**跨模块收益**：M9 §2.1 指出**被举报内容待审期间不可推荐，停推有损创作者体验**。所以"限流发布"同时降低了：① 误伤率 ② 申诉压力（M5）③ 创作者体验损害。**这三者在框架里本来是对立的，限流缓冲让它们对齐了**。

### 3.2 账号差异化策略：与"创作者信用"的对应

原方案的四种账号策略（冷/新号全量过 Agent、高信誉快审抽检、历史违规强制过 Agent、高潜力提权）在框架里对应：

| 原方案策略 | 框架内对应 |
|---|---|
| 冷/新账号全量过 Agent | M3 §2.5 召回来源②④⑤（成本高→精度优先） |
| 高信誉账号快审抽检 | M9 §2.2「**用户身份权重**」的镜像——把身份权重用到**生产者侧**|
| 历史违规强制过 Agent | M6 §一「② 规避型内容生产者」——惯犯与初犯应区别 |
| **高潜力视频提权**| M3 §1.2「**高热审核**」的前置化——**发布前就预判热度**（原方案比 M3 更进一步） |

⚠️ **"高潜力视频提权"是两个模块的交叉创新**：
- M3 的高热审核是**发布后**复审（KuaiMod 的 High-Engagement Videos 队列）
- 原方案是**发布前预判热度**并提权审核

**后者的风险杠杆更高**（一条爆款违规的传播面是长尾的数万倍），但依赖**热度预测模型的准确性**——建议明确：**热度预判误判的代价不对称**（预判高但实际不高=浪费算力；预判低但实际爆款=风险外溢），所以**阈值应偏保守**（宁可多提权）。

---

## 四、治理层

### 4.1 存量巡检的三个触发条件

| 原方案触发条件 | 框架内对应 |
|---|---|
| 用户举报量超阈值 | M9 举报召回（"兜底召回"的或逻辑） |
| 传播突然加速（可能被灰产引流） | M3 §2.2 来源⑥「消费/行为信号」**成本最低、最被低估**|
| 模型版本更新后回扫历史视频 | M2 §5.2「回扫」，淘宝技术复盘明确"规则变更会反向阻塞已发布商品，需全生命周期回扫" |

### 4.2 对抗闭环：与 M6 的对应

原方案的"**收集新规避手法入库 → 每周驱动模型/Prompt 迭代 → A/B 灰度验证 → 全量上线 → 监控**"就是 M6 的核心循环，且给出了节奏（**每周一个版本**）。

**M6 可以补强原方案的两点**：

| M6 的内容 | 补进原方案的价值 |
|---|---|
| **Δ（迭代速度差）**= 平台迭代周期 − 对手变异周期 | 原方案定"每周迭代"，但**没有判断这个节奏够不够**。用 Δ 可以量化：闲鱼的词库迭代**数周~数月**vs 暗语**日抛**→ Δ 极大。**每周一版对 P0/P1 类风险可能仍不够**|
| **防御纵深四层（L1 提高规避成本优先）**| 原方案的对抗手段集中在"模型/Prompt 迭代"（对应 M6 的 L3/L4），**缺少 L1**——而 M6 指出 **L1 是唯一能改变攻防成本结构的一层**|

⚠️ **一个必须补的攻击面（原方案未覆盖）**：

> **Agent 护栏本身会遭受拒绝服务攻击。**
> 参见 [From Shield to Target: Denial-of-Service Attacks on LLM-Based Agent Guardrails](https://ar5iv.labs.arxiv.org/html/2606.14517)。

**为什么这对本方案特别危险**：原方案的架构是"**少量存疑视频进 Agent**"。攻击者只要**批量制造"存疑但不违规"的内容**（例如大量边缘内容），就能：
1. 把大量流量**从 L1/L2 挤进 L3**
2. **打满 Agent 的工具调用预算与并发**
3. 导致真实风险**排不上队**——这是**容量型攻击**，不是准确率问题

→ **对策（建议写进方案）**：
| 对策 | 说明 |
|---|---|
| **队列隔离**| Agent 容量按来源分区，**举报/巡检触发的分析不与常规准入抢配额**|
| **存疑比例监控**| 监控"L2→L3 的转化率"，**突升即为攻击信号**（正常应稳定在 5%~10%） |
| **降级预案**| 容量打满时，**降级为"先限流 + 排队"**，而不是无限等待 |
| **前端输入规范化**| 去 emoji / 零宽字符 / 结构化模板（M6 §3.1） |

**另外 M6 的"攻击判定器"一类也适用**：[AdvJudge-Zero（Unit 42）](https://unit42.paloaltonetworks.com/fuzzing-ai-judges-security-bypass/) 证明用**低困惑度无害 token**（markdown 符号、列表标记）就能操纵判定模型的 allow/block 边界，**完全黑盒**。原方案的 Agent 也是判定器，同样在这个攻击面内。

**多智能体场景的额外风险**：[HARP: Measuring Harm Amplification in Multi-Agent LLM Systems](https://ar5iv.labs.arxiv.org/html/2605.27489) 研究多智能体的危害放大——如果 L3 采用多 Agent 分工（如原方案生态层提到的 Multi-Agent），需评估这一风险。

### 4.3 ⚠️ 校准点 2：核心指标体系有三处需要修

原方案的指标是**整个方案最需要校准的部分**：

| 原方案 | 问题 | 建议修改 |
|---|---|---|
| **P0/P1 召回率 > 99.5%**|  合理，但**必须写明分母与抽样方式**| 见下 |
| **误伤率 < 0.1%**| ⚠️ **量级可能不现实，且口径未定义**| 见校准点 5 |
| **P1 审核时延 < 1 分钟**|  合理，但**与 L3 Agent 的成本有张力**| 见校准点 6 |
| **Agent 平均工具调用次数**|  好指标 | 建议加**分布**（P50/P95）而非只看均值 |
| **人工复核转化率趋势下降**|  好指标 | 建议同时看**绝对量**——比例下降但总量上升是掩盖问题 |

**"召回率 > 99.5%"的分母问题（必须写清）**：

```
P0/P1 召回率 = 被正确识别的 P0/P1 内容数 / 全部实际存在的 P0/P1 内容数
                                    ↑
                        这个分母「无法直接观测」——你只能看到你发现的
```

**所以必须用 M5 §3.3 的三池思路**：

| 估计来源 | 性质 |
|---|---|
| 申诉成功池抽样 | 可得**上界**（有选择偏差，偏高） |
| 未申诉池 / 申诉失败池抽样 | 补下界 |
| **外部锚点**（监管通报、媒体报道、竞品治理动作） | **独立于平台自身的口径**|

⚠️ **一个更根本的问题**：**P0 类内容如果漏放，通常不会有用户申诉**（用户可能不敢、不知、或内容已被快速传播）。所以 **P0 的召回率不能靠申诉池估计**——**只能靠外部锚点 + 主动抽样审计**。

**这一条建议在方案里单列成"P0 召回率的度量方法"一小节**，因为它决定了"99.5%"这个红线是否可验证。

### 4.4 对抗闭环的 A/B 验证：一个方法学提醒

原方案说"新版本先 A/B 灰度验证，重点看误伤率和召回率的变化"。

⚠️ **方法学提醒（M4 §6.1）**：治理实验有**两个特殊困难**——
1. **不能随机分流**：内容一旦违规就不该"随机放给一半用户"
2. **大盘波动干扰归因**：生态指标受内容供给、季节、热点影响

**建议**：
- 用**影子模式**（只判定不处置）替代部分 A/B
- 用**双重差分（DID）**：处理组 vs 对照组的前后变化之差
- **误伤率是低频事件**，A/B 的统计功效可能不够 → 需要**先算样本量**，或改用 A/A 先验证指标稳定性

---

## 五、生态建设层

### 5.1 样本生态：五个来源的评价

| 原方案来源 | 框架内对应 | 评价 |
|---|---|---|
| 用户举报（最大众包来源） | M9 举报产品 |  唯一能持续、规模化获取"用户认为是问题"的通道 |
| **蜜罐诱饵账号**| M6 §五 红队机制的**主动版**| **最有价值的来源**——能捕获**完整攻击链路**，而不只是单个样本 |
| **暗网 / TG 群情报监控**| M0 §4.1 主动发现的**前置化**| **把风险感知前置到黑产部署之前**——这是 M0 §六"发现时延"能做到的最优状态 |
| Agent 高置信样本自动入库 | M0 §4b.4 抖音谣言库 / KuaiMod 判例库 |  **让样本自增长**——结论复用让能力随治理量增长 |
| 行业共享黑库 | — | ⚠️ 需注意**合规与数据边界**|

⚠️ **关于"行业共享黑库"建议补一句限定**：跨平台共享涉及**用户数据与内容数据的合规边界**（尤其跨境）。公开材料里未见国内平台共享原始内容样本的一手案例；**可行的是共享"手法特征"而非"原始内容"**。

### 5.2 知识沉淀：与 M1 §7 的对应

原方案的三个沉淀物在框架里都有明确位置：

| 原方案沉淀物 | 框架内对应 |
|---|---|
| **风险 Playbook 作为 Agent system prompt 的知识库**| M1 §7.1「规则住在 Prompt」——**这正是"Prompt"这一档的实现**|
| **攻防案例库**（模型微调 + 新人培训双用） | M5 §2.7 判例库 + M6 §六 对抗样本库 |
| **高频确定性规则从 Agent 卸载到规则引擎**| M2 §6.1 **成本杠杆排序的第一条**——这是**最直接的降本手段**|

**"高频确定性规则卸载到规则引擎"值得单独强调**——它是整份方案里**性价比最高的一条优化**：
> 把确定性规则从 Agent 卸载到规则引擎，等于把一部分 L3 流量**回落**到 L1。而 L1 与 L3 的成本差是**一到两个数量级**。
> **这个动作应当做成例行机制**（例如每季度复盘：哪些工具调用是重复的、哪些推理可固化为规则）。

### 5.3 人机协作闭环

原方案："Agent 不确定 → 人工复核 → 人工标注反哺 Agent（RLHF / Prompt 优化）→ 不确定率下降 → 人工工作量减少"。

**这个闭环与框架的对齐**：

| 原方案 | 框架内对应 | 补充 |
|---|---|---|
| 人工复核 Agent 存疑部分 | M3 §2.2 L3 人审准入（高不确定 + 高影响 + 格式异常） | 建议**显式加入"格式异常"**——被投毒的输入不该让模型硬判 |
| 人工标注反哺 Agent | M5 §2.7 回流闭环 | ⚠️ 注意**M5 §四的三类归因**：人工推翻 Agent 时，要区分"Agent 判错"还是"规则本身有问题" |
| 不确定率下降 = 系统在变好 |  方向对 | **但要看绝对量**（见校准点 7） |

⚠️ **一个容易被忽略的陷阱**：如果"人工复核转化率"下降只是因为**判定被放宽了**（更多内容被判为"确定"而不是转人工），那这个指标会**虚假改善**。
→ **必须配对看**：`人工转化率 ↓` + `误伤率 ↓` + `召回率 →` 三者同时成立才算真改善（M4 §5.2 指标三元组）。

---

## 六、八处需要校准的地方（汇总）

**这是本篇最有价值的部分**——原方案框架完整，但以下八处若直接落地会有问题：

| # | 校准点 | 原方案 | 问题 | 建议 |
|---|---|---|---|---|
| **1**| **L1 的 50ms**| 设 50ms 目标 | 未说明这意味着 L1 **不能用生成式模型**| 显式声明为"架构红线"，锁定**判别式 + CPU/INT8**路线；并注明是 **P50 还是 P99**|
| **2**| **误伤率 < 0.1%**| 设 0.1% 上限 | ① **口径未定义**（分母是什么？）② 量级可能不现实 | 用 **M5 §3.3 三池上下界**定义口径；先测基线再定目标 |
| **3**| **"低置信走 Agent"**| 用置信度分流 | **跨模型置信度不可比**（CAUC 已证明） | **先做置信度校准**，再设统一阈值；校准本身还带来精度 +1.9%、省 47% 强模型调用 |
| **4**| **风险分级只有一维**| P0~P3 按严重程度 | 阈值还需**按风险类**标定（基础率差 9.0%~25.5%） | 改成二维矩阵：`严重程度 × 风险类` |
| **5**| **限流缓冲的边界**| 作为通用缓冲 | KuaiMod 原文：**只有部分违规类型可个性化，明确违法的严格过滤**| 与 P 级绑定：**P0 不用、P2/P3 最适用**|
| **6**| **P1 < 1 分钟 vs Agent 成本**| 两个要求并列 | L3 多轮工具调用**可能吃掉整个预算**|  **已由架构解决**：改 Event Flow 后路径长度固定，预算约束是架构自带的；仍建议设**四重上限**（token / step / tool-call / wall-clock），超限降级转人审（见 §2.4.5） |
| **7**| **人工转化率趋势下降**| 作为健康指标 | 可能因"判定放宽"而**虚假改善**| 必须与**误伤率、召回率配对**验证（指标三元组） |

**以及一处"补强的攻击面"**（不算校准，算遗漏）——**该项已由 §2.4 的架构改动从设计上消除**：

| # | 遗漏 | 风险 | 对策 |
|---|---|---|---|
| **8**| **Agent 护栏的拒绝服务攻击**| 攻击者批量制造"存疑但不违规"内容 → **打满 Agent 容量**→ 真实风险排不上队 |  **Event Flow 架构自带缓解**：路径固定 + 可按状态限流 + 降级是正常状态转移。仍建议保留：状态级队列隔离、L2→L3 转化率监控、输入规范化 |

---

## 七、整合后的完整架构图

```
┌──────────────────────────────────────────────────────────────────┐
│ 风险定义层（M1）                                                  │
│  显性风险（global）│ 隐性风险：keyframe / segment / crossmodal     │
│  建议：标签 × detection_shape 交叉矩阵                         │
│  分级：P0~P3 × 风险类（二维，非一维）                             │
├──────────────────────────────────────────────────────────────────┤
│ 识别层（M2 三级级联 + 采样）                                       │
│  L1 判别式快筛  ── 50ms(C1) ── 指纹/封面标题/概率预估 ──→ 过 60%   │
│  L2 智能采样    ── 高熵帧定位（STEC 类指标可测采样质量）──→ 剩 5~10%│
│  L3 Event Flow  ── 状态机骨架（§2.4）── 并行取证 → 局部判据     │
│        ⚠️ 置信度须先校准(C3)；四重上限(C6)；状态限流(C8)          │
├──────────────────────────────────────────────────────────────────┤
│ 准入层                                                            │
│  高置信→拦截 / 存疑→Agent / Agent存疑→限流发布(P0除外)(C5) → 人审   │
│  账号差异化：冷新号全量 / 高信誉快审 / 历史违规强制 / 高潜力提权     │
├──────────────────────────────────────────────────────────────────┤
│ 治理层（M6）                                                      │
│  巡检触发：举报 / 传播加速 / 模型更新回扫                          │
│  对抗闭环：每周迭代 → A/B 灰度（建议用影子模式 + DID）→ 监控       │
│  指标：召回/误伤(C2) + 时延 + 工具调用 + 人工转化率(C7)             │
├──────────────────────────────────────────────────────────────────┤
│ 生态建设层                                                        │
│  样本：举报 / 蜜罐 / 暗网情报 / Agent 自动入库 / 行业共享          │
│  知识：Playbook → Prompt；案例库；确定性规则卸载回规则引擎       │
│  人机：转人工 → 反哺 → 不确定率下降                               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 八、如果只保留三句话

1. **三级漏斗是必要条件，不是优化项**——因为视频级 Agent 判定的成本比图片审核高一到两个数量级，把 LLM 调用压在 5%~10% 是落地的门槛。
2. **控制流要放在编排层，不是模型里**——用 Event Flow 状态机做主干，只在"证据够不够定级"这一处嵌 ReAct 式判断。因为审核的反馈延迟且有偏，缺了自主动 Agent 赖以成立的那块地基（§2.4）。
3. **Agent 只能有建议权，不能有处置权**——把"删除/封号"放在 Agent 子流程边界之外，误删类风险就从设计上消失了，而不是靠 prompt 约束（§2.4.5）。

---

## 附：本篇引用的学术与工业锚点

**编排架构（§2.4 核心）**
- [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) — workflows vs agents 的正式命名
- [Scott Logic: Auditable Agentic Orchestration](https://blog.scottlogic.com/2026/07/08/auditable-agentic-orchestration.html) — Agentic Subprocess 边界 / governed autonomy
- [respan: 5 Production Patterns](https://www.respan.ai/articles/agent-workflow) — 纯 ReAct 是烧钱三件套
- [Ken Priore: power vs control](https://kenpriore.com/the-power-vs-control-tradeoff-in-workflow-design-now-with-agents/) — Tool Filtering
- [NVIDIA Colang](https://docs.nvidia.com/nemo/guardrails/configure-guardrails/colang.md) · [AWS T&S 参考实现](https://github.com/aws-samples/sample-trust-safety-orchestration-agent)

**Agent 范式与级联**
- ReAct（Reason + Act）—— 局部判据节点的理论基础，**不是编排范式**
- [FrugalGPT](https://arxiv.org/abs/2305.05176) · [RouteLLM](https://arxiv.org/abs/2406.18665)
- [RADAR（ACL 2026 Industry）](https://aclanthology.org/2026.acl-industry.139/) — APR@R90/R95、R@P60
- [CAUC](https://arxiv.org/abs/2609.11446) — 置信度校准

**采样与关键帧**
- [Adaptive Keyframe Sampling（CVPR 2025）](https://ar5iv.labs.arxiv.org/html/2502.21271)
- [STEC 时空熵覆盖率（WACV 2026 Workshop）](https://www.openaccess.thecvf.com/content/WACV2026W/WVAQ/papers/Lin_STEC_A_Spatio-Temporal_Entropy_Coverage_Metric_for_Evaluating_Sampled_Video_Frames_WACVW_2026_paper.pdf)
- [FOCUS](https://browse-export.arxiv.org/pdf/2510.27280) · [CUEKFS](https://browse-export.arxiv.org/pdf/2609.31873) · [AdaptToken](https://www.semanticscholar.org/paper/AdaptToken%3A-Entropy-based-Adaptive-Token-Selection-Qi-Qu/d71a87fc2f652bf5f03fbf9d986836531234883e)

**对抗与攻击面**
- [From Shield to Target: DoS Attacks on LLM-Based Agent Guardrails](https://ar5iv.labs.arxiv.org/html/2606.14517) —— 原遗漏的攻击面，已由 Event Flow 架构缓解（§2.4.6）
- [HARP: Harm Amplification in Multi-Agent LLM Systems](https://ar5iv.labs.arxiv.org/html/2605.27489)
- [AdvJudge-Zero（Unit 42）](https://unit42.paloaltonetworks.com/fuzzing-ai-judges-security-bypass/)
- [Emoji Attack（ICML 2025）](https://icml.cc/virtual/2025/poster/45356)

**工业实践**
- [TikTok Filter-And-Refine（ACL 2025 Industry）](https://aclanthology.org/2025.acl-industry.62/)
- [UNIVID（ACL 2026）](https://arxiv.org/html/2606.05748v1) · [SIRF（EMNLP 2026 Industry）](https://arxiv.org/abs/2609.11752)
- [Joom 官方复盘](https://about.joom.com/blog/3cea9966b0b28081b4c6df776b6d3435)
- [COGNIT-Guard](https://arxiv.org/abs/2609.33671) — 322M 判定模型 21.77ms/45.90 QPS
- 快手安全大模型审核智能体（[AICon 深圳 2025 实录](https://www.infoq.cn/article/6r251b2u2bdaqmgbisfa)）
- [闲鱼暗语治理（羊城晚报）](https://www.sina.cn/news/detail/5346303754110434.html) — Δ 概念来源
