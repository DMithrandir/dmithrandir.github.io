# dmithrandir.github.io

个人站 + 博客。**不使用任何主题 gem**：布局、组件、样式全部在本仓库里，改版不用跟主题打架。
构建由 GitHub Pages 内置的 Jekyll 完成（不需要 Actions 配置、不需要本地环境）。

- 线上：https://dmithrandir.github.io/
- 设计方向：档案 / 编辑部 —— 纸色底、墨色字、印章红点缀，衬线标题 + 等宽元信息

## 目录结构

```
.
├── _config.yml               # 站点配置（标题 / 描述 / 插件 / 排除项）
├── _layouts/
│   ├── default.html          # 全站外壳：head + 页眉 + main + 页脚 + 进度条
│   ├── home.html             # 首页：Hero + 正文 + 文章索引
│   ├── post.html             # 文章页：标题区 + 正文 + 目录 + 上下篇
│   └── page.html             # 普通页（关于 / 归档 / 404）
├── _includes/
│   ├── head.html             # <head>：SEO、字体预加载、样式、深浅色初始化
│   ├── header.html           # 页眉：品牌标记 + 导航 + 深浅色开关
│   └── footer.html           # 页脚
├── assets/
│   ├── css/style.css         # 全部样式（设计变量在文件顶部 :root）
│   ├── js/site.js            # 深浅色、进度条、目录、表格横滚、代码复制
│   └── fonts/                # Instrument Serif（拉丁标题字，21 KB，自托管）
├── _posts/                   # ← 文章都放这里，文件名必须是 日期-英文短名.md
├── index.md                  # 首页内容（Hero 文案在 front matter 里）
├── about.md                  # 关于页
├── archive.html              # 归档页（按年份自动分组）
├── 404.md                    # 自定义 404
├── robots.txt                # 指向 sitemap
└── README.md                 # 本文件（已 exclude，不会渲染成网页）
```

## 发一篇新文章（三步）

1. 在 `_posts/` 新建 `YYYY-MM-DD-英文短名.md`
2. 写 front matter：

   ```yaml
   ---
   layout: post
   title: "文章标题"
   date: 2026-11-02 09:00:00 +0800
   categories: 治理框架
   tags: [内容治理, 人机协同]
   description: "一句话摘要：进搜索、分享卡片和文章页副标题"
   excerpt: "首页索引里显示的摘要（可省略，省略则取 description 效果更好）"
   permalink: /your-slug/        # 可选；写了链接更短，发布后别改
   ---
   ```

3. `git add -A && git commit -m "新增：xxx" && git push`

约 45–75 秒后生效。文章会自动出现在首页索引、归档页、RSS 和 sitemap 里，不需要手动加链接。

## 改版（换颜色 / 字体 / 间距）

所有设计变量都在 `assets/css/style.css` 顶部的 `:root` 与 `[data-theme="dark"]` 里：

| 变量 | 作用 |
|---|---|
| `--paper` / `--paper-2` | 页面底色 / 次级底色（表格、代码块） |
| `--ink` / `--ink-soft` / `--muted` | 标题 / 正文 / 辅助信息 |
| `--accent` | 印章红：强调、链接下划线、目录高亮 |
| `--display` / `--sans` / `--mono` | 标题字 / 正文字 / 等宽字 |

改一处即可全站生效，不要在各处硬编码颜色。

## 注意

- 文章文件名里的日期决定 URL 与排序，**发布后不要改**；
- `permalink` 一旦发出去就别改，旧链接会 404；
- 构建失败时站点继续显示上一版，去 Actions → `pages build and deployment` 看红色那一步；
- 深浅色偏好存在浏览器 `localStorage.theme`，首次访问跟随系统。
