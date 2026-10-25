# dmithrandir.github.io

个人网站 + 博客。**不使用任何主题 gem**：布局、组件、样式全部在本仓库，改版不用跟主题打架。
构建由 GitHub Pages 内置的 Jekyll 完成（不需要 Actions 配置、不需要本地环境）。

- 线上：https://dmithrandir.github.io/
- 设计方向：档案 / 编辑部 —— 纸色底、墨色字、印章红，衬线标题 + 等宽元信息

## 页面

| 路径 | 文件 | 说明 |
|---|---|---|
| `/` | `index.md` + `_layouts/home.html` | 首页：Hero + 三条能力线 + 精选作品 + 最新文章 + 关于条 + 联系 |
| `/projects/` | `projects.html` | 作品集（读 `_data/projects.yml`） |
| `/blog/` | `blog.html` | 全部文章 |
| `/archive/` | `archive.html` | 按年份归档 |
| `/about/` | `about.md` | 关于（含经历时间线） |
| `/edgecase-framework/` | `_posts/…` | 文章页（带右侧目录、阅读进度） |

## 目录结构

```
.
├── _config.yml               # 站点配置（标题 / 描述 / 插件 / 排除项）
├── _data/projects.yml        # ← 作品集数据：加项目只改这一个文件
├── _layouts/
│   ├── default.html          # 全站外壳：head + 页眉 + main + 页脚 + 进度条
│   ├── home.html             # 首页（Hero + 各分节）
│   ├── post.html             # 文章页（目录 / 上下篇 / 阅读时长）
│   └── page.html             # 普通页（关于 / 作品 / 文章列表 / 404）
├── _includes/
│   ├── head.html             # <head>：SEO、字体预加载、样式（带缓存戳）、深浅色初始化
│   ├── header.html           # 页眉：印章标记 + 导航 + 深浅色开关
│   ├── footer.html           # 页脚
│   ├── section-head.html     # 分节标题（标题 + 小标 + 右侧链接）
│   ├── project-card.html     # 作品卡片
│   └── post-row.html         # 文章索引行
├── assets/
│   ├── css/style.css         # 全部样式（设计变量在顶部 :root 与 [data-theme="dark"]）
│   ├── js/site.js            # 深浅色、进度条、目录、表格横滚、代码复制
│   ├── img/                  # 文章配图（SVG 优先，另附 PNG）
│   └── fonts/                # Instrument Serif（拉丁标题字，21 KB，自托管）
├── index.md · about.md · projects.html · blog.html · archive.html · 404.md
├── _posts/                   # 文章
└── README.md                 # 本文件（已 exclude，不会被渲染成网页）
```

## 加一个作品

只改 `_data/projects.yml`，加一块：

```yaml
- title: 项目名
  role: 你的角色
  period: "2025"
  summary: 一两句话说清做了什么、解决了什么。
  tags: [标签1, 标签2]
  link: /your-article/      # 留空则卡片不可点
  featured: true            # 首页是否露出（首页最多 3 个）
```

## 发一篇新文章

1. 在 `_posts/` 新建 `YYYY-MM-DD-英文短名.md`
2. front matter 至少写 `layout: post` / `title` / `date` / `description`
3. `git add -A && git commit -m "新增：xxx" && git push`

约 45–75 秒后生效。文章会自动进 `/blog/`、`/archive/`、RSS 与 sitemap。

## 加一个页面

新建 `xxx.md`（或 `xxx.html`），front matter 写：

```yaml
layout: page
title: 页面标题
permalink: /xxx/
eyebrow: "SECTION"      # 标题上方的小标（可选）
description: "一句话说明"  # 会作为导语（可选）
wide: true              # 内容区是否放宽（可选）
```

再把导航项加到 `_includes/header.html` 的 `<nav>` 里。

## 改视觉

设计变量在 `assets/css/style.css` 顶部：

| 变量 | 作用 |
|---|---|
| `--paper` / `--paper-2` | 页面底色 / 次级底色（卡片 hover、表格、代码块） |
| `--ink` / `--ink-soft` / `--muted` | 标题 / 正文 / 辅助信息 |
| `--accent` | 印章红：强调、下划线、目录高亮 |
| `--display` / `--sans` / `--mono` | 标题字 / 正文字 / 等宽字 |

## 注意

- 文章文件名里的日期决定 URL 与排序，**发布后不要改**；`permalink` 同理。
- CSS / JS 的 URL 带 `?v={{ site.time }}` 缓存戳，每次构建都会变，**改版后不用手动清缓存**。
- 构建失败时站点继续显示上一版，去 Actions → `pages build and deployment` 看红色那一步。
