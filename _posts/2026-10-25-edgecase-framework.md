---
layout: post
title: "把模糊地带变成可复制的判定机制 · EdgeCase Framework"
date: 2026-10-25 09:00:00 +0800
categories: 治理框架
tags: [内容治理, 人机协同, LLM, 评测, 标注质量]
permalink: /edgecase-framework/
description: "把「判不了的案例」从感觉变成统计：三段决策流程、9 类归因编码、四条常识判断原则，以及三票多数决的人机投票规则。"
excerpt: "一套把「判不了的案例」从感觉变成统计的人机协同判定机制：双层判定 → 三段决策流程 → 9 类归因编码 → 四条常识判断原则 → 结构化推理输出，最后由两个模型 + 一位人工三票多数决定案。"
---

> **作品集版 · Portfolio Edition**
> 一份把「判不了的案例」从**感觉**变成**统计**的人机协同决策机制设计。
> A human–LLM decision mechanism that turns "we can't judge this" from a *feeling* into a *statistic*.

**关于本稿 / About this version**
出于保密义务，本稿隐去公司名称、内部政策代码、工具名与团队缩写，业务指标以机制价值表述替代；框架逻辑、流程结构与设计取舍完整保留。
Out of confidentiality obligations, this version omits the company name, internal policy codes, tool names and team abbreviations, and replaces business metrics with qualitative statements of mechanism value. The framework logic, process structure and design trade-offs are preserved in full.

---

## 项目速览｜At a glance

| 项 / Item | 内容 / Detail |
|---|---|
| 项目 / Project | 灰度案例决策框架——人机协同的模糊案例判定机制 / A human–LLM decision framework for ambiguous cases |
| 我的角色 / Role | 机制设计者：框架、流程、归因编码体系、常识原则结构化、人机投票规则 / Mechanism designer |
| 场景 / Context | 某头部短视频与直播平台的直播治理，2025 / LIVE governance at a leading short-video platform, 2025 |
| 状态 / Status | 设计完成并跑通，纳入日常抽检流程 / Shipped and folded into the daily sampling workflow |
| 核心产出 / Deliverables | 三段决策流程 · 9 类归因编码 · 4 条常识判断原则 · CoT 四要素输出模板 · 人机投票规则 v1 |
| 可迁移方向 / Transferability | 模型评测与标注质量体系、HITL 决策流程、低置信升级机制 |

---

## 0. 一句话定义｜One-liner

**中文**：在某头部短视频与直播平台的直播治理中，我设计了一套标准化机制，把「片段信号模糊、按规则无法直接判定」的灰度案例，通过 **双层判定（片段 + 直播间）→ 三段决策流程 → 归因编码 → 常识判断四原则 → 结构化推理输出** 裁决为 **Label / Pass / Edge** 三态；其中**需要常识判断的案例触发人机混合判定**——两个不同的大模型加一位人工，三票多数决、同时判定、互不可见，模型分歧时人票决胜——让模糊场景的判定第一次**可追溯、可统计、可沉淀**。

**EN**: A standardized mechanism I designed for grey-area cases in live-streaming governance at a leading short-video and live-streaming platform. Cases whose clip signals are ambiguous and cannot be decided by the rules alone go through **dual-level judgment (clip + room) → a three-step decision process → attribution coding → four common-sense principles → structured reasoning output**, ending in one of three states — Label / Pass / Edge. Cases that require common-sense judgment trigger a human–LLM hybrid review: two different LLMs plus one human, three votes, majority wins — judged simultaneously and blind to each other, with the human vote breaking any model deadlock. For the first time, decisions on ambiguous cases became **traceable, countable and reusable**.

---

## 1. 问题｜The problem

这套机制建在一个既有的治理专项之上：团队会抽取「已有初判结论 + 已有质量校验结论」的直播切片做**第三轮复核**，用来源归因（初判错 / 校验错 / 双方都错 / 规则空白）来量化误伤水平。这套抽检是**团队项目**，不是我个人的战果——我的工作是在它之上解决一个它暴露出来的、更棘手的问题。

**第三轮复核里，总有一批案例判不了。** 直播形态的变化速度快于规则迭代速度，规则覆盖不到的争议内容会持续产生；「对 / 错」的二元判定在这里直接失效。三个根因：

This mechanism builds on an existing governance program: the team drew live clips that already carried both a first-round judgment and a quality-assurance conclusion for a **third-round review**, attributing each case by source (first-pass error / QA error / both / rule gap) to quantify over-action. That sampling program is a **team program**, not my personal win — my job was to solve the harder problem it exposed.

**In third-round review, a batch of cases simply could not be judged.** Content forms evolve faster than the rule set, so disputed content keeps landing outside policy coverage; binary right/wrong judgment breaks down. Three root causes:

| # | 问题 / Problem | 说明 / Description |
|---|---|---|
| 1 | **高度主观性** / High subjectivity | 同类模糊案例，人与人之间、项目与项目之间的判断差异大，缺少统一标尺。/ Judgments on the same ambiguous case diverge between reviewers and between programs — there is no shared yardstick. |
| 2 | **视野过窄** / Narrow vision | 过去只盯政策字面，忽略直播间整体语境，导致「片段里看不出违规、直播间里其实有」的误判。/ Reviewers read policy wording only and missed room-level context, producing "nothing in the clip, everything in the room" misses. |
| 3 | **不可统计** / No codifiability | 只有给每个案例打上归因编码，才知道这批案例的**精确分布**——把「感觉」变成「统计」。/ Only by coding every case can you see their **exact distribution** — turning a feeling into a statistic. |

**因此这个机制要回答的不是「这一案判什么」，而是「判不了的那一类，怎么进入一个可运营的流程」。**
**So the design question was not "what is the verdict for this case", but "how does the un-judgeable class enter an operable process".**

---

## 2. 四条设计主张｜Four design principles

| # | 主张 / Principle | 含义 / What it means |
|---|---|---|
| 1 | **三态而非二态** / Three states, not two | 增加 `Edge` 作为**悬置升级**出口，而不是逼审核员「凑一个结论」——把「判不了」本身做成一个可追踪的流程节点。/ Add `Edge` as an **escalation** exit instead of forcing a verdict; "cannot judge" becomes a trackable process node. |
| 2 | **双层而非单层** / Two levels, not one | 片段级（clip）与直播间级（room / account）分别取证，解决「片段缺语境」这一类系统性误判。/ Gather evidence at clip level and at room level separately, fixing the systemic "clip lacks context" misjudgment. |
| 3 | **归因先于优化** / Attribution before optimization | 每个案例落**唯一编码**，先做到可统计，才谈得上定位根因、分配改进动作。/ Every case lands exactly one code. Make it countable first, then you can locate root causes and assign follow-ups. |
| 4 | **反锚定 + 多数决** / Anti-anchoring + majority vote | 人与模型**同时判定、互不可见**；模型分歧时人票决胜——既用上模型的不同视角，又不让任何一方被另一方带偏。/ Human and models judge **simultaneously and blind to each other**; the human vote breaks model deadlocks — gaining model perspectives without letting either side anchor the other. |

---

## 3. 机制总览｜Overview

- **双层判定 / Dual-level judgment**：Task level（片段，clip）＋ Room level（直播间及账号，room / account level）
- **三态输出 / Three outputs**：**Label**（判定违规）· **Pass**（判定通过）· **Edge**（悬置升级）
- **人机协同 / Human–LLM collaboration**：需常识判断的 `Edge` 案例触发模型审查——两个不同的大模型 + 一位人工，三票多数决；人与模型同时判定、互不可见；模型意见相反时人票决胜；模型必须输出结构化信号 + 推理链
- **归因闭环 / Attribution loop**：每个案例落唯一归因编码 → 按编码聚合 → 决策差异可统计、可量化 → 编码映射改进动作（规则补丁 / 产品方案 / 队列补全 / 质量培训）
- **适用范围 / Applicability**：语境校准（Context Calibration）**仅用于人审**；灰度判断（Edge-case Decision）**人审与 LLM 通用**——这正是这套机制能延伸到 AI 审核与模型评测场景的关键
- **使用者 / Users**：运营策略 + 质量校验；上报链路为 一线 → 质量校验 → 策略运营

---

## 4. 三段决策流程｜Three-step decision process

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/edgecase-flow.svg' | relative_url }}" target="_blank" rel="noopener">
      <img src="{{ '/assets/img/edgecase-flow.svg' | relative_url }}" alt="三段决策流程图：Step 1 片段审查按片段信号强弱分成三路——清晰违规进入 Step 2 语境校准（仅人审），疑似或隐晦进入 Step 3 灰度判断（人审加 LLM），完全无信号直接判 Pass 并记 Quality Issue；最终输出 Label / Pass / Edge 三态。" width="800" height="838" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 1 · 三段决策流程</strong>：Step 1 只决定「去哪」；Step 2 校准语境（只有人能看整个房间）；Step 3 处理没有硬信号的灰度案例，其中「行为 / 视觉 + 常识判断」这一支才送模型三票。点图可看原尺寸。</figcaption>
</figure>

### Step 1 — 严格按政策原文审片段｜Clip review against the policy text

| 片段信号 / Clip signal | 任务级结果 / Task level | 去向 / Next |
|---|---|---|
| 清晰违规 / Clear violation | — | → Step 2（语境校准） |
| 疑似、隐晦 / Implicit or suspected | **Edge** | → Step 3（灰度判断） |
| 完全无信号 / No signal at all | **Pass**（最终结果同为 Pass） | 记 `Quality Issue` 编码 → 流程结束 |

### Step 2 — 语境校准｜Context calibration（仅人审 / human review only）

> 解决的问题：片段级违规信号清晰，但个别政策条目需要结合直播间整体画风做 room-level 意图判断。
> The clip-level signal is clear, but specific policy items require a room-level intention judgment against the overall context.

| 直播间发现 / Findings in room | 任务级 → 最终 / Task → Final | 归因编码 / Code |
|---|---|---|
| 互动信号全场高频 / Frequent throughout the session | Label → **Label** | — |
| 互动信号偶发 / Occasional | Label → **Pass** | Clip lacks context |
| 连麦 / 嘉宾违规、主播本身无信号 / Co-host or guest violation, host signal absent | Pass → **Label** | Co-host violation |
| 主播违反其他政策 / Host violation under other policy items | Label → **Label** | Quality Issue |

> 政策清单对此设有例外条款（部分连麦互动类场景不适用），此处不展开。
> Certain co-host interaction scenarios are carved out of this rule per the policy set; details omitted here.

### Step 3 — 灰度判断｜Edge-case decision（人审 + LLM 通用 / human and LLM）

> 解决的问题：片段里疑似文字或语言隐晦违规但缺硬信号；或疑似行为 / 视觉问题但无法直接判断。
> Suspected implicit textual or verbal violations without hard signals; or suspected behavior / visual issues that cannot be judged directly.

| 直播间发现 / Findings in room | 分支 / Branch | 最终结果 / Final | 归因编码 / Code |
|---|---|---|---|
| **能找到违规或负向意图** / Violation or negative intention established | Textual / Verbal（文字、语音、字幕类政策族） | **Label** | Edge · clip lacks signal · room violation |
| | Behavior / Visual（贬损、身体展示、安全行为等视觉类政策族） | **Label** | Edge · clip lacks signal · room violation |
| **找不到违规或负向意图** / Not found | Textual / Verbal | **Pass** | Edge · clip lacks signal · room normal |
| | Behavior / Visual → 常识判断（见 §6） | **Label**（Problematic） | Edge · borderline · room violation |
| | | **Pass**（Not problematic） | Edge · borderline · room normal |
| | | **Edge**（Cannot judge） | Edge · borderline · room edge |

**关键设计 / Key design**：`Edge` 不是「凑一个结论」，而是**悬置升级**——进入人工复审 / 规则补充 / 队列补全，把「判不了」本身变成一个可追踪的流程节点。这正是模型评测语境里「低置信不硬判、升级复审」的同一思路。
`Edge` is not a guessed verdict but an **escalation** into human re-review, rule supplementation or queue completion. It is the same idea as "do not force a decision at low confidence — escalate for review" in model evaluation.

**LLM 触发点 / LLM trigger**：本步中**需要常识判断的案例**（Behavior / Visual 的常识分支）送模型考察，三票投票结果作为最终判定的输入。Textual / Verbal 分支房间信号明确，直接判定、不送模型。
Within this step, **cases requiring common-sense judgment** (the behavior / visual branch) go to model review, whose votes feed the final verdict. The textual / verbal branch has unambiguous room signals and is decided directly, without model review.

---

## 5. 归因编码体系｜Attribution coding（9 类 / 9 codes）

**命名结构 / Naming scheme**：
`【判断路径 - 信号类型 - 片段与房间信号的关系 - 最终结论】`
`[decision path - signal type - clip-to-room relation - conclusion]`

每个案例落**唯一编码** → 按编码聚合即得到灰度案例的精确分布 → 决策差异可统计、可量化。
Every case lands exactly one code; aggregating by code yields the exact distribution, making decision variance countable.

| 大类 / Category | 含义 / Meaning | 编码示例 / Examples | 映射的改进动作 / Follow-up |
|---|---|---|---|
| **语境校准**（3 类）/ Context calibration (3) | 片段结论与房间语境不符导致的判定修正 / Verdict corrections caused by clip-level conclusions contradicting room context | `Clip lacks context`（片段缺语境）<br>`Co-host violation`（连麦嘉宾违规） | 产品策略方案 / 规则精修 |
| **灰度判断**（6 类）/ Edge (6) | 片段信号模糊，需结合房间信号与常识判断 / Ambiguous clip signals requiring room signals and common-sense judgment | `Edge · text/verbal · room violation / normal`<br>`Edge · visual/behavior · borderline · room violation / normal / edge` | 违规 → 规则精修；切片问题 → 排队补全；实为误判 → 质量改进 |
| **质量问题**（非灰度类）/ Quality issue (not grey) | 审核执行层面的问题（Step 1 无信号、Step 2 主播违规等）/ Execution-level issues | `Quality Issue` | 仅当判定确为错误时 → 质量改进 |

**两层归因 / Two attribution layers**：
- **来源层 / Source layer**——第三轮复核按案例来源归因：初判错 / 校验错 / 双方都错 / 规则空白，供误伤率统计；
- **编码层 / Coding layer**——上述 9 类编码，供决策差异量化。

两层衔接点：**规则空白类，正是 `Edge` 类编码覆盖的对象**——规则覆盖不到的争议内容，就是灰度判断的目标。
The bridge between the layers: **the rule-gap class is exactly what the `Edge` codes cover** — disputed content outside policy coverage is the target of grey-area judgment.

> 对外说明 / Note：本版编码名称按同一命名结构重述，未使用内部原始命名。
> Code labels here are restated under the same naming scheme; internal original naming is not used.

---

## 6. 常识判断四原则｜Four common-sense principles

> **常识的定义 / What common sense means**：决策中的「常识」不是直觉，而是**语境化、政策对齐的推理**——从平台直播生态治理的视角出发。
> In this framework, "common sense" is not intuition but **contextual and policy-aligned reasoning** from a live-ecosystem governance standpoint.
>
> **政策锚定是前提 / Policy anchoring is required**：即便信号模糊、不完整，决策也必须锚定政策框架，以确保与整体治理框架一致。
> Even with incomplete signals, the decision must stay anchored to the policy framework so it remains consistent with the wider governance stance.

1. **政策框架锚定 / Policy-framework anchoring** — 先回到平台政策立场，不凭直觉判断。/ Start from the platform's policy stance rather than personal intuition.
2. **文化与社会意识 / Cultural and social awareness** — 地区、文化、宗教规范不同；对表达、幽默、着装、引用的判断要先代入当地语境，避免文化偏见。/ Norms differ by region, culture and religion; apply local context before judging expression, humor, attire or references, and avoid cultural bias.
3. **风险预判 / Risk anticipation** — 预判风险升级、被利用或滥用的可能，结合区域直播内容生态与趋势。/ Anticipate escalation, exploitation or misuse within regional live-content ecosystems and trends.
4. **意图与行为并合原则 / The concurrence principle** — 客观行为（actus reus）与推断意图（mens rea）**并合**才判违规：既看「做了什么」，也看「为什么做」。/ A case is problematic only when the observable action and the inferred intent concur — judge both what was done and why.
   > 例 / Example：行为层面——整场直播着装暴露且反复调整道具制造暴露；意图层面——刻意、反复的隐含动作 → 并合成立，可判定违规。/ Behavior: repeated, deliberate exposure throughout the session; intent: a patterned implicit act. The two concur, so the case is violative.

---

## 7. 结构化推理输出｜Structured reasoning output（CoT 四要素）

模型与人工的判定都必须按固定字段交代推理链，而不是只给一个结论。
Both models and humans must express their reasoning through fixed fields rather than returning a bare verdict.

| 要素 / Element | 要求 / Requirement | 示例 / Example |
|---|---|---|
| 1. 信号类型 / Signal type（Implicit / Explicit · Textual / Verbal / Behaviour / Visual） | **必填** / Required | Textual：一句带表情符号的隐晦财务求助 → implicit financial plea |
| 2. 直播间整体 / Room overview | **必填** / Required | 某语区直播间反复请求打赏：手势与祝福语常为索赠信号，意图清晰；背景陈设简陋、祝福语密集 |
| 3. 常识推理 / Common-sense reasoning | **仅边界案例适用** / borderline only | 按 §6 四原则展开 |
| 4. 一句话结论 / Judgment summary | **必填，一句话** / Required, one sentence | 「基于用语判断，属房间级明显违规。」→ Final judgment: **Label** |

> 设计意图 / Why this matters：字段即约束。模型不能自由发挥，它必须把「看到了什么信号、房间整体如何、按哪条常识原则推理、最后结论是什么」逐项写出来——这让 AI 参与决策的同时**保持可解释、可复核、可追责**。
> Fields are the constraint. The model cannot free-associate: it must state the signals observed, the room context, the common-sense principle applied and the final conclusion — keeping AI in the decision while remaining **explainable, auditable and accountable**.

---

## 8. 人机投票规则（v1）｜Human–LLM voting rules (v1)

2025 年 Q4 的初版设计刻意朴素——不引入模型编排、不做置信度阈值，先用最小机制验证「流程是否成立」。
The Q4-2025 v1 was deliberately simple: no model orchestration, no confidence thresholding — validate the process with the smallest viable mechanism first.

| 规则 / Rule | 内容 / Detail |
|---|---|
| 组成 / Composition | 两个**不同**的大模型 + 一位人工 = 3 票 / Two **different** LLMs + one human = 3 votes |
| 判定方式 / Judgment | 同时判定、互不可见（防锚定）/ Simultaneous and mutually blind (anti-anchoring) |
| 收敛 / Aggregation | 多数决 / Majority wins |
| 僵局 / Deadlock | 两个模型意见相反时，人工票决胜 / When the two models split, the human vote decides |
| 触发范围 / Scope | 仅「需要常识判断」的 `Edge` 分支 / Only the `Edge` branch requiring common-sense judgment |
| 输出要求 / Output | 按 CoT 四要素结构化的判定 / Verdict structured per the four-element CoT |

<figure class="post-figure">
  <div class="post-figure-scroll">
    <a href="{{ '/assets/img/edgecase-voting.svg' | relative_url }}" target="_blank" rel="noopener">
      <img src="{{ '/assets/img/edgecase-voting.svg' | relative_url }}" alt="人机三票示意图：需要常识判断的案例同时交给两个不同的大模型和一位人工，三方独立判定、互不可见，多数决；两个模型意见相反时由人工票决胜，最终输出 Label / Pass / Edge。" width="800" height="470" loading="lazy">
    </a>
  </div>
  <figcaption><strong>图 2 · 人机三票</strong>：三个投票者同时判定、互不可见；两个模型意见相反时人票决胜。这条「互不可见」是整套设计里最容易被省略、也最关键的一条。</figcaption>
</figure>

**为什么是「三个投票者 + 人票决胜」而不是让模型直接终审**：两个模型提供不同视角、覆盖单模型盲区；人工保留终审权，确保机制在政策立场上不失锚；而「互不可见 + 同时判定」是这套设计里最关键的一条——先看模型结论再自己判，人就已经被锚定了。
**Why three voters with a human tie-breaker instead of letting a model decide**: two models bring different perspectives and cover each other's blind spots, while the human retains final authority so the mechanism stays anchored to policy. "Mutually blind and simultaneous" is the most important rule — once a reviewer sees the model's verdict first, anchoring has already happened.

---

## 9. 翻译到评测与标注语境｜Translation into evaluation & annotation terms

这套机制最直接的复用价值，在于它和模型评测、标注质量体系共用同一套骨架。
Its clearest reuse value is that it shares a skeleton with model evaluation and annotation-quality systems.

| 灰度机制语言 / Grey-area language | 评测与标注语言 / Evaluation & annotation language |
|---|---|
| 灰度案例（灰区） | Low-confidence / ambiguous cases |
| 双层判定（片段 + 直播间） | Multi-granularity context judgment（clip-level + context-level） |
| 归因编码体系 | Structured error taxonomy |
| 决策差异量化 | Inter-rater reliability / agreement metrics |
| 三票多数决（2 模型 + 1 人，互不可见，人票决胜） | HITL majority voting（two LLMs + one human, blind, human breaks ties） |
| `Edge` 悬置升级 | Low-confidence escalation（不硬判） |
| 共识判例 | Golden set |

---

## 10. 落地状态与可迁移能力｜Status & transferable capability

**状态 / Status**：机制设计完成并**正式跑通，纳入日常抽检流程**。
Designed, shipped and **folded into the daily sampling workflow**.

**结果层面的价值 / What it changed**
- 判不了的案例第一次有了**明确出口与归因**——从「悬着」变成「有入口、有流程、有归因、有结果」；
- 灰度案例第一次有了**可统计的分布**——从「感觉」走向「统计」；
- 沉淀 9 类归因编码，每类**映射到明确的责任动作**（规则补丁 / 产品方案 / 队列补全 / 质量培训），使「一次判定失误」升级为「一类可修的系统问题」；
- 人机同时投票的设计**把锚定挡在流程之外**，成为团队从「人审能力」向「模型能力」过渡的通道。

Un-judgeable cases gained an explicit exit and attribution for the first time; grey cases gained a countable distribution; nine codes each map to a named follow-up action, upgrading "one bad call" into "one fixable systemic class"; and simultaneous blind voting keeps anchoring out of the loop, making this the team's bridge from human review capacity to model capacity.

**可迁移能力 / Transferable capability**
1. **让 AI 参与决策同时保持可解释**——不是让模型自由发挥，而是用字段强制它交代推理链；
2. **让错误可归因、可统计**——唯一编码 + 聚合分布 + 映射责任人；
3. **让模型与人的分歧有规则**——多数决 + 互不可见 + 人票决胜，而不是临时讨论；
4. **一套框架多处复用**——同一套归因骨架同时用于灰度判定与漏放治理，机制设计一次、迁移两次。

1. Keeping AI in the decision while staying explainable — fields force the reasoning out into the open.
2. Making errors attributable and countable — one unique code, aggregate distribution, assigned owner.
3. Giving human–model disagreement a rule — majority vote, mutual blindness, human tie-break, instead of ad-hoc debate.
4. Designing once, reusing twice — the same attribution skeleton serves both grey-area judgment and leak-fix governance.

---

## 11. 已知局限与下一步｜Known limits & next steps

| # | 局限 / Limit | 下一步 / Next step |
|---|---|---|
| 1 | **触发范围是刻意的取舍**：只有「需要常识判断」的分支送模型，文字 / 语言分支房间信号明确即直接判定——覆盖度让位于成本与时效。/ Trigger scope is a deliberate trade-off: only the common-sense branch goes to models, because cost and latency matter. | 量化「送审占比 × 命中收益」，再决定是否扩大触发面。/ Quantify coverage against lift before widening the trigger. |
| 2 | 三票制是**效率与稳健的折中**，未引入置信度加权或分级复核。/ Three votes balance speed and robustness; no confidence weighting or tiered review yet. | 引入置信度分层：低置信自动升级二级人审。/ Add confidence tiers with automatic escalation to second-tier review. |
| 3 | 「决策一致性」**尚缺正式的人机 / 人人一致性指标**，机制自身的验收口径未形式化。/ No formal inter-rater agreement metric yet for the mechanism itself. | 把一致性指标（如 agreement rate / kappa）列为机制验收指标，做上线前后对照。/ Make agreement metrics the mechanism's own acceptance criteria, measured before and after. |
| 4 | 编码体系**依赖标注纪律**，尚未做标注者间一致性抽检。/ The coding scheme depends on annotation discipline; no inter-annotator spot checks yet. | 定期抽检编码一致性，把分歧本身作为机制迭代输入。/ Periodically sample coding consistency and feed disagreement back into the design. |
| 5 | v1 **刻意不做模型编排与阈值**。/ v1 deliberately avoids model orchestration and thresholds. | 等流程被证明成立后，再迭代编排与成本优化。/ Iterate on orchestration and cost only after the process itself is proven. |

---

## 12. 我的角色与边界｜My role and the boundary

- **我负责的 / What I owned**：框架与流程设计、归因编码体系、常识判断四原则的结构化、人机投票规则（v1）设计，以及机制进入日常抽检流程的落地推动。
  Framework and process design; the attribution coding scheme; structuring the four common-sense principles; the v1 human–LLM voting rules; and driving adoption into the daily sampling workflow.
- **不属于我的 / What was not mine**：上游的误伤抽检专项是团队项目，其指标改善不由本机制单独归因。
  The upstream over-action sampling program is a team program; its metric movement is not attributed to this mechanism.
- **不在此呈现的 / Deliberately omitted here**：具体模型选型、送审占比与量级、上线前后一致性数据等内部经营与实验数据。
  Model selection specifics, review volumes and before/after consistency data are internal operational and experimental data, and are intentionally left out.

---

## 附录 A · 直播间调查工具箱（泛化）｜Appendix A · Room investigation toolkit (generalised)

| 工具类型 / Tool type | 用途 / Purpose | 局限 / Downside |
|---|---|---|
| 全屏历史取证类 / Full-screen history forensics | 完整违规历史，便于理解语言与文化鸿沟类内容 / Full violation history; helps read language- and culture-dependent content | AI 摘要加载较慢 / AI summaries load slowly |
| 快速扫描类 / Rapid scanning | AI 摘要加载快，可批量扫房间，内置帧概览 / Fast AI summaries, batch room scanning, built-in frame overview | 缺少完整直播间与观众评论视图 / No full room-and-comment view |
| 结构化推理辅助（LLM）/ Structured reasoning assistant (LLM) | 按 CoT 字段输出推理链，支撑人机混合判定 / Outputs reasoning along CoT fields to support hybrid judgment | 需要人工保留终审权 / Human final authority still required |

---

*— 作品集版结束 · End of portfolio edition —*