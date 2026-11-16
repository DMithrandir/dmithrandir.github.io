---
layout: page
title: "X2CAD：几何内核与白盒验证台"
permalink: /x2cad/
eyebrow: "PROJECT · GEOMETRY KERNEL"
description: "一个个人维护的 CAD 几何内核与算子级白盒验证台：预言机先行、变异自审、指针式实体引用。"
---

2026 年 AI-CAD 的公开工作大多集中在生成侧：Pointer-CAD 把 B-Rep 与命令序列统一成指针表示，CAD-MLLM 做多模态条件生成，CADTests、CADBench 一类的基准则在系统层面打分。这些工作回答的是「生成得像不像」，很少回答「哪个算子在哪种输入下违反了哪条容差承诺」。OCCT 功能完整，但容差行为缺一份公开的算子级证据链。

X2CAD 把这件事拆成两半：一个尽量小但可证明的内核切片，一套与具体内核解耦的算子级 conformance 验证台。几何代码的准入标准是 oracle：解析真值、有限差分、不变量、独立参考实现，再加对验证台自身的变异自审。

## 当前内容

- **曲线算子**：B 样条 / NURBS 求值、各阶导数、全局插值（参数化 + 节点平均 + 残差检查）。
- **节点操作**：Boehm 节点插入（单次 / 重复，含 NURBS）、按参数分割、Bézier 升阶。
- **微分几何与 2D**：自适应 Gauss 弧长、单位切矢、曲率；两线段夹角处的相切圆弧。
- **验证台**：SC001–SC008 静态检查、39 条 conformance 用例、9 个变异注入（捕获率 9/9）、Tier 4 扰动平面。
- **退化语料**：五族 15 条，每条绑定一个可执行用例。
- **EntityRef v0.2**：确定性 id、tombstone 拒绝，以及 1-to-N / N-to-1 谱系（split / merge，序号或参数寻址）。

| 项 | 现状 |
|---|---|
| oracle 测试 | 232 例 |
| conformance | 39 cases / 39 checks |
| 变异自审 | 9/9 = 100% |
| 静态检查 | 0 findings |

证据文件（`verify/evidence/report.json`、`verify/audit/mutation_report.json`）随代码一起提交，记录每一批代码当时通过的内容。

## 怎么跑

纯 Python，无第三方运行时依赖：

```text
git clone https://github.com/DMithrandir/x2CAD.git
cd x2CAD

python -m pytest          # 232 例 oracle 测试
python -m verify          # 静态检查 + 覆盖率 + conformance
python -m verify.mutation # 变异注入与捕获率
```

新增算子要同时交四件套：`impl.py`、`spec.json`、oracle 测试、`verify/cases/<slug>.json`。缺一件，`python -m verify` 就会失败。

## 边界与下一步

Tier 3 的外部对拍（Shapely / OCCT）还没有接入，本机缺依赖；规范里已经写死接入口径：Shapely 只对折线，曲线层用解析构造加区间算术。Tier 5 的过程化重放要等 P1 的 sketch/extrude 链。B-Rep 拓扑变异按 ADR-0001 走规格先行与人工审查，不交给模型直接写。

下一步是 P1：2D 约束求解加 2D 曲线布尔，用 Boehm 分割与曲线求交拼出最小闭环。三维曲线/曲面求交（CCI / SSI）排在后面。

## 链接

- 仓库：[github.com/DMithrandir/x2CAD](https://github.com/DMithrandir/x2CAD)
- 设计文档与决策记录：[docs/plans](https://github.com/DMithrandir/x2CAD/blob/main/docs/plans/2026-08-20-x2cad-kernel-design.md) 与 [docs/adr](https://github.com/DMithrandir/x2CAD/tree/main/docs/adr)
