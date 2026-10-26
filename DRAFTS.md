# 草稿区（`_drafts/`）

这里的东西**不会发布**。GitHub Pages 构建时不带 `--drafts`，所以这些文件只存在于仓库里，方便你慢慢改。

## 现在有什么

### 系列「治理的机制」`/governance/`

| 篇 | 文件 | 状态 | 要补什么 |
|---|---|---|---|
| 01 | `_posts/2026-10-25-edgecase-framework.md` | **已发布** | 已挂进系列（series: governance, part 1） |
| 02 | `_drafts/governance-02-policy-cascading.md` | 骨架 | 补齐实验口径（样本量/显著性）、人力折算口径；删组织名 |
| 03 | `_drafts/governance-03-knowledge-system.md` | 骨架 | 补齐废弃窗口、仲裁机制；删内部系统名 |
| 04 | `_drafts/governance-04-evaluation.md` | 骨架（需重写 70%） | 去掉求职语境，只留「内容理解 → 评测维度」的方法部分 |

### 系列「AI Harness」`/series/ai-harness/`

> 注意：你写的长文占用了 `/harness/`，所以系列目录页放在 `/series/ai-harness/`，避免两个页面撞同一个 URL。

| 篇 | 文件 | 状态 | 要补什么 |
|---|---|---|---|
| 01 | `_posts/2026-10-25-harness-from-using-ai-to-harnessing-ai.md` | **已发布** | 你写的 Harness 复盘长文，已挂进系列（part 1） |
| 02 | `_drafts/ai-harness-02-evaluating-harness.md` | 骨架 | 任务集规模、一组前后对照数据、失败类型分布 |
| 03 | `_drafts/ai-harness-03-harness-in-governance.md` | 骨架 | 判定流程在 harness 里的实际实现（代码/截图） |
| 04 | `_drafts/ai-harness-04-failure-patterns.md` | 骨架 | 每种失败模式一个真实例子 + 最后怎么处置的 |

## 怎么把草稿变成文章

1. 改内容（骨架里的「待补 / 待确认」是清单）
2. 把文件从 `_drafts/` 移到 `_posts/`，文件名加日期：`2026-11-02-xxx.md`
3. front matter 补 `date`（发布日），`permalink` 保持 `/governance/xxx/` 或 `/harness/xxx/`（不要和 `/harness/` 本身重合）
4. `git add -A && git commit -m "新增：xxx" && git push`

发布后会自动出现在系列目录里（系列页用 `where: series` 动态生成，不用手动维护列表）。

## 两个约定

- **一篇文章只讲一件事**。骨架里如果出现「顺便说一下」，那通常是下一篇。
- **数字要么有出处，要么标「待确认」**。发布前把「待确认」清零；清不了的删掉，不要留模糊表述。
