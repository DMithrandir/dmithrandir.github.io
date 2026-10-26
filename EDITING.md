# 编辑指南

> 给你自己改内容用的。改完推上去，约 1 分钟生效。
> 这里只讲"改哪、怎么写"，不解释原理。

## 0. 三条最快路径

| 想做什么 | 改哪里 |
|---|---|
| 改首页文字 | `index.md`（**整页文案都在 front matter 里**） |
| 改关于页 | `about.md`（普通 Markdown） |
| 加/改项目 | `_data/projects.yml` |
| 加文章 | `_posts/` 新建 `YYYY-MM-DD-英文短名.md` |
| 改站名 | `_config.yml` 的 `title` / `tagline` / `description` |
| 改导航文字 | `_includes/header.html` 里的四个 `<a>` |

## 1. 首页文案地图（全部在 `index.md` 顶部）

```yaml
eyebrow:          # 大标题上方的小标
hero_title:       # 大标题
hero_lead:        # 导语（一段）
cta_primary:      # 主按钮文字（跳文章）
cta_secondary:    # 次按钮文字（跳项目）
hero_meta:        # 右侧三行：label / value 列表
posts_title / posts_sub / posts_more     # "最新文章 / LATEST / 全部文章"
projects_title / projects_sub / projects_more
about_title / about_band / about_button  # "关于这个博客" 一段文字 + 按钮
facts:            # 右下三条事实
cta_title / cta_subscribe                # 底部一句 CTA + 订阅按钮
```

首页那三栏 **01 / 02 / 03** 在 `index.md` 的正文 HTML 里（`<section class="pillars">`）——整段删掉首页就自动少一块，不会报错。

其他页面：

| 页面 | 文件 | 说明 |
|---|---|---|
| 关于 | `about.md` | 全篇 Markdown，时间线是 `<ul class="timeline">` |
| 项目 | `_data/projects.yml` | 每块：`title / role / period / summary / tags / link / featured`；`link` 留空则卡片不可点 |
| 文章列表 | `blog.html` | 页头 `description` |
| 项目页 | `projects.html` | 页头 `description` + 底部一句话 |
| 归档 | `archive.html` | 页头 `description` |
| 页脚 | `_includes/footer.html` | 版权一行 + 四个链接 |
| 文章页 | `_posts/*.md` | 正文 + front matter（title / date / description / tags / permalink） |

## 2. 安全编辑三条

1. **`---` 之间是 front matter**，格式是 `键: 值`，**冒号后必须有空格**；英文引号要成对（中文引号不影响）。
2. **不要动 `{{ }}` / `{% %}` 里的东西**（例如 `{{ '/about/' | relative_url }}`），那是自动生成的链接。
3. **改坏了怎么办**：GitHub 上打开那次提交 → `Revert`；或本地 `git revert <sha>` 再 push。构建失败时线上继续显示上一版，不会白屏。

## 3. "AI 味"自检清单

对着这几条扫一遍，命中就改：

| 模式 | 例子（当前站里有的） |
|---|---|
| 三段式排比 / 否定排比 | "不写新闻，不写清单体，只写能复用的判断" |
| "不是 X，而是 Y" | "实践，不是二手转述" |
| 破折号引出道理 | "——不写下来，下次还得重新想一遍" |
| 每个小节都凑三条 | 首页 01/02/03；关于页三条 |
| 抽象名词堆叠 | 机制 / 体系 / 闭环 / 沉淀 |
| 第一人称宣言 | "我真正关心的是……" |
| 对仗/金句标题 | "在模糊地带，写下可复用的判断。" |

**一键搜出来**（PowerShell，在仓库目录跑）：

```powershell
Select-String -Path index.md,about.md,blog.html,projects.html,_data\projects.yml `
  -Pattern "不是|而是|——|三类|原则|真正|只写|不写" -Encoding UTF8
```

改写思路（不用全改，挑你最不喜欢的）：

- 金句 → **具体的事**。例："在模糊地带，写下可复用的判断。" → "最近在写：灰度判定怎么做成流程。"
- 排比 → 删到只剩一句，或换成"这里主要放……"
- 三栏 → 换成"最近在写 / 最近在做"两行，或整段删掉
- "不写 X" → 直接不写这句，没有声明也是一种态度

## 4. 怎么预览

| 方式 | 代价 | 适合 |
|---|---|---|
| 改完 `git push`，1 分钟后看线上 | 1 分钟 | 改文字（最快） |
| Docker Desktop + `jekyll/jekyll` 镜像 | 首次拉镜像 | 常改版式 |
| 本机装 Ruby + `gem install jekyll bundler` | 一次安装 | 长期 |

Docker 命令（在仓库目录）：

```powershell
docker run --rm -p 4000:4000 -v ${PWD}:/srv/jekyll jekyll/jekyll jekyll serve --watch
```

> 注意：本机 `*.github.io` 走了代理/被劫持，**线上预览时先确认浏览器能打开站点**（开系统代理或 TUN）。

## 5. 发布

```powershell
cd "C:\Users\desha\Desktop\找工作\_publish_pages\dmithrandir.github.io"
git add -A
git commit -m "改：xxx"
git push
```

也可以在 GitHub 网页上直接改（文件右上角铅笔）。文章文件名里的日期和 `permalink` **发布后别改**，改了旧链接会 404。

## 6. 想加东西时的位置

| 加什么 | 怎么加 |
|---|---|
| 一篇文章 | `_posts/2026-11-02-xxx.md`，front matter 至少 `layout: post` / `title` / `date` / `description` |
| 一个项目 | `_data/projects.yml` 加一块，`featured: true` 会出现在首页（最多 3 个） |
| 一个页面 | 新建 `xxx.md`，`layout: page`（正文页）或 `layout: list`（列表页）+ `permalink`，再到 `_includes/header.html` 加导航 |
| 首页一个新分节 | `_layouts/home.html` 里复制一段 `<section class="block">…</section>` |
| 文章配图 | 图片放 `assets/img/`，正文用 `<figure class="post-figure">`（模板见 `README.md`） |

## 7. 日期怎么控制

文章的 `date:` 在 front matter 里，**只用于排序，页面上不显示**（2026-10-26 起）。

- 列表行：`_includes/post-row.html`（首页、`/blog/` 共用）—— 已去掉日期
- 文章页顶部：`_layouts/post.html` 的 eyebrow —— 已去掉日期，只留分类和阅读时长
- 归档页：`archive.html` 仍按**年份**分组，但不显示具体到日

想加回来：

1. `post-row.html` 里加 `<span class="row-date">{{ post.date | date: '%Y.%m.%d' }}</span>`（放在 `row-num` 后面）
2. `style.css` 的 `.post-row-link` 列宽改成 `56px 116px minmax(0, 1fr) 24px`
3. `.row-excerpt` 的左 margin 改回 `212px`

> 副作用：RSS 和 sitemap 里仍然带真实日期（订阅器和搜索引擎需要），只是页面上看不到。
