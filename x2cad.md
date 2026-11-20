---
layout: page
title: "X2CAD：几何内核与白盒验证台"
permalink: /x2cad/
eyebrow: "专题 02 · 几何内核 · 2026 →"
description: "一个个人维护的 CAD 几何内核与算子级白盒验证台：预言机先行、变异自审、指针式实体引用。"
---

AI 与 CAD 交叉领域的瓶颈，已经从“能不能生成几何”转到“什么算生成对了、算子在容差边界下稳不稳”。生成侧（Pointer-CAD、CAD-MLLM、MIRAGE-CAD、DualBrep）已经很拥挤；评测侧仍停留在系统级黑盒：输入模型或脚本，运行时导出网格，算体积 IoU 或视觉打分。内核一旦在布尔或相切处失败，这种分数既暴露不了非流形微裂缝，也定位不到具体算子与退化配置。

工业界长期被 Parasolid、ACIS 与西门子 D-Cubed 垄断；开源侧 OCCT 功能完整，但容差行为（Fuzzy Tolerance）缺少公开的算子级证据链。X2CAD 做的是这一层判据：一个尽量小但可证明的内核切片，一套与内核解耦的 conformance 验证台，外加一条保证确定性重放与单步派生寻址的 EntityRef 契约（参数化 TNP 不在本层承诺）。

## 当前内容

- **曲线算子**：B 样条 / NURBS 求值、各阶导数、全局插值（参数化 + 节点平均 + 残差检查）。
- **节点操作**：Boehm 节点插入（单次 / 重复，含 NURBS）、按参数分割、Bézier 升阶。
- **微分几何与 2D**：自适应 Gauss 弧长、单位切矢、曲率；两线段夹角处的相切圆弧。
- **2D 求交**：解析闭式通道（线段×线段、线段×圆弧、圆×圆）+ 多项式通道开启（线段×Bézier：Sturm 根隔离、重数判相切、认证区间），判定全部精确、坐标浮点可认证。
- **验证台**：SC001–SC008 静态检查、74 条 conformance 用例、24 个变异注入（捕获率 24/24）、Tier 4 扰动平面。
- **退化语料**：五族 17 条，每条绑定一个可执行用例。
- **EntityRef v0.2**：确定性 id、tombstone 拒绝，以及 1-to-N / N-to-1 谱系（split / merge，序号或参数寻址）。

| 项 | 现状 |
|---|---|
| oracle 测试 | 311 例 |
| conformance | 74 cases / 74 checks |
| 变异自审 | 24/24 = 100% |
| 静态检查 | 0 findings |

证据文件（`verify/evidence/report.json`、`verify/audit/mutation_report.json`）随代码一起提交，记录每一批代码当时通过的内容。

<p><a class="btn" href="{{ '/x2cad/roadmap/' | relative_url }}">查看可视化路线图 →</a></p>

## 怎么跑

纯 Python，无第三方运行时依赖：

```text
git clone https://github.com/DMithrandir/x2CAD.git
cd x2CAD

python -m pytest          # 311 例 oracle 测试
python -m verify          # 静态检查 + 覆盖率 + conformance
python -m verify.mutation # 变异注入与捕获率
```

新增算子要同时交四件套：`impl.py`、`spec.json`、oracle 测试、`verify/cases/<slug>.json`。缺一件，`python -m verify` 就会失败。

## 边界与下一步

Tier 3 的外部对拍（Shapely / OCCT）还没有接入，本机缺依赖；规范里已经写死接入口径：Shapely 只对折线，曲线层用解析构造加区间算术。Tier 5 的过程化重放要等 P1 的 sketch/extrude 链。B-Rep 拓扑变异按 ADR-0001 走规格先行与人工审查，不交给模型直接写。

P1 已经开工：解析闭式求交通道完成（线段×线段、线段×圆弧、圆×圆），全部精确判号，并补上跨算子链的精确坐标契约。变异审计还抓到一个有价值的发现：原写的防御性守卫是不可达死代码，静态检查器也在真实开发中拦下了跨算子私有 import。下一步是直线-Bézier 与 Bézier-Bézier 求交，再拼 2D 约束求解与布尔装配。三维曲线/曲面求交（CCI / SSI）排在后面。

P1 已经开工：解析闭式求交三通道完成，线段×Bézier（Sturm 根隔离 + 重数判相切）也已落地。变异审计连出两个有价值的发现：不可达死代码守卫（数学上不可能触发，删除）与不可观察的 gcd 快路径（行为完全等价，删除）——「看起来更精确的代码」若不改变可观察行为就是噪声；静态检查器也在真实开发中拦下了跨算子私有 import。下一步是 Bézier×Bézier 求交收官多项式通道，再拼 2D 约束求解与布尔装配。三维曲线/曲面求交（CCI / SSI）排在后面。

- 仓库：[github.com/DMithrandir/x2CAD](https://github.com/DMithrandir/x2CAD)
- 阶段 review：[2026-11-20-stage-review.md](https://github.com/DMithrandir/x2CAD/blob/main/docs/reviews/2026-11-20-stage-review.md)
- 可视化路线图：[/x2cad/roadmap/]({{ '/x2cad/roadmap/' | relative_url }})（[源码](https://github.com/DMithrandir/x2CAD/blob/main/docs/roadmap.html)）
- 设计文档与决策记录：[docs/plans](https://github.com/DMithrandir/x2CAD/blob/main/docs/plans/2026-08-20-x2cad-kernel-design.md) 与 [docs/adr](https://github.com/DMithrandir/x2CAD/tree/main/docs/adr)

---

<p><a class="back-link" href="{{ '/research/' | relative_url }}"><span aria-hidden="true">←</span> 回研究笔记</a></p>

