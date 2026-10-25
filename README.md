# dmithrandir.github.io

个人站 + 博客，用 **GitHub Pages 原生 Jekyll** 构建（不需要 Actions、不需要本地环境）。

- 线上地址：https://dmithrandir.github.io/
- 主题：`minima`（GitHub Pages 内置，自带文章列表、文章页、页眉导航）

## 目录结构

```
.
├── _config.yml                 # 站点配置（标题、主题、插件、导航）
├── index.md                    # 首页：个人定位 + 文章列表（layout: home 自动列出 _posts）
├── about.md                    # 「关于」页（页眉导航）
├── _posts/                     # ← 所有文章放这里，文件名必须是「日期-标题.md」
│   └── 2026-10-25-edgecase-framework.md
├── LICENSE
└── README.md                   # 本文件（已在 _config.yml exclude，不会渲染成网页）
```

## 发一篇新文章（三步）

1. 在 `_posts/` 新建文件：`YYYY-MM-DD-英文短标题.md`（**日期和文件名都不能省**，否则不会被识别成文章）
2. 文件开头写 front matter：

   ```yaml
   ---
   layout: post
   title: "文章标题"
   date: 2026-10-25 09:00:00 +0800
   categories: 治理框架
   tags: [内容治理, 人机协同]
   description: "一句话摘要，会进搜索结果和分享卡片"
   ---
   ```

3. 正文写 Markdown，提交到 `main` 分支。GitHub 会在 1–2 分钟内自动重建，文章地址默认是
   `https://dmithrandir.github.io/2026/10/25/文件名.html`；如果 front matter 里写了 `permalink: /xxx/`，就用那个地址。

## 注意

- 文章文件名里的日期决定 URL 和排序，改日期等于改链接，**发布后不要再改**。
- `_` 开头的目录和文件 Jekyll 默认不会渲染（`_posts` 是特例，它就是要被渲染的）。
- 构建失败时站点会继续显示上一次成功的结果，去 **Actions → pages build and deployment** 看红色那一步的日志。
