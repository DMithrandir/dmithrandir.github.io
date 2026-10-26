# 噪声系列的可复现代码

配套博客系列「噪声、不等式与采样器」（<https://dmithrandir.github.io/mcmc/>）。

只依赖 `numpy`、`scipy`、`matplotlib`。所有脚本都可以从本目录直接运行：

```bash
pip install numpy scipy matplotlib

python experiments.py                # 四组对照（E1）+ 噪声扫描（E3），约 20–40 分钟
python matched_step_control.py       # 等步长对照：D 的收益是否只是步长，约 15 分钟
python experiments_llm_scaling.py    # 第 8 篇：多采样的尾部竞争与覆盖率分解，约 3 分钟
cd rnsafety && python experiments_reverse.py   # 第 7 篇：反向噪声的定理与反例，约 2 分钟
```

`experiments.py` 把图与 JSON 写到 `./output/`，`experiments_llm_scaling.py` 写到 `./figures/`（均自动创建），
`rnsafety/experiments_reverse.py` 写到 `rnsafety/figures/`。仓库里已有的 `results.json`、
`llm_scaling_results.json`、`rnsafety/reverse_results.json` 是当前版本跑出的结果，可以直接拿去核对
博客里的每个数字，不必重跑。

`rnsafety` 的测试：`cd rnsafety && python -m pytest -q`（38 项）。

## 文件

| 文件 | 内容 | 对应文章 |
|---|---|---|
| `core.py` | 目标分布、MH、噪声 MH、经验 KL、积分自相关时间、ESS、R-hat | 02–05 |
| `experiments.py` | E1 四组对照（A/B/C/D）、E3 噪声扫描、机制相关性 | 05 |
| `matched_step_control.py` | 关键对照：用与约束组等步长的朴素 MH 复跑首达问题 | 04–06 |
| `results.json` | `experiments.py` 的输出（接受率、τ、KL 曲线、扫描结果） | 05 |
| `experiments_llm_scaling.py` | 盲选择对照、尾部指数三区域、覆盖率/选择分解 | 08 |
| `llm_scaling_results.json` | 上面这个脚本的输出 | 08 |
| `rnsafety/` | 反向噪声审计工具（四路监控 + 证书 + 命令行）与其定理验证 | 07 |
| `rnsafety/reverse_results.json` | `experiments_reverse.py` 的输出（36 项检查 + 七族基准） | 07 |

## 四组是什么

目标是双峰高斯混合 \(0.5\,N(-2, 0.75^2) + 0.5\,N(2, 0.75^2)\)，基础提议 \(N(0,1)\)：

- **A** 朴素随机游走 MH，\(\sigma=1\)
- **B** 盲注噪声：候选 \(x+s+n\)，\(s\sim N(0,1)\)，\(n\sim N(0,\sigma_n^2)\)
- **C** 方差匹配 MH：提议 \(\sigma=\sqrt{1+\sigma_n^2}\)（命题 1 要求的对照）
- **D** 约束噪声：\(n\) 按二次条件 \(n^2 - 2sn \le -2\sigma^2 A(x_t)\) 做拒绝采样，\(A\) 用 48 点 Gauss–Hermite 在真实目标上逐点积分

E3 的度量是「从 \(x_0=-5\) 首次进入 \(x>1.25\) 的步数」（燃烧期语境）；E1 的度量是接受率、积分自相关时间与运行经验 KL（混合语境）。

## `rnsafety` 里那几条定理

| 定理 | 内容 | 对应检查 |
|---|---|---|
| R1 | 单步损失增量的精确恒等式 | E-R1（相对误差 \(1.7\times10^{-16}\)） |
| R2 | 条件 (2) 的可行集是以 \(n=s\) 为球心的球，半径 \(\sqrt{\|s\|^2-2\sigma^2A}\) | E-R3（含独立暴力扫描） |
| R3 | 方向条件数的代价 \(\kappa_g\ge\frac{\delta^2}{1-\delta^2}\frac{d\,\mathbb{E}\|w\|^2}{\mathbb{E}\|\epsilon\|^2}\) | E-R4（拟合指数 1.511） |
| R4 | 余弦证书的非渐近误差界与最小可检测偏置 | E-R5（误报率在名义水平内） |
| R4b | 谱不可见与反向偏置不可兼得，\(\|\rho\|\le1/\sqrt{dn}\) | E-R6、E-R7、E-R8 |

两个反例（各向同性注入下条件数恒为 1、余弦密度解析无极点）由 E-R2 验证。

### 两点实现提示

1. **余弦必须对干净梯度取。** 用 \(\hat g\) 当参考算 \(\cos(\hat g,\epsilon)\) 会得到恒正的量，把每个反向攻击都藏起来。
2. **谱监控要用未中心化二阶矩。** 固定偏移的签名在 \(\mathbb{E}[E]\) 里，均值中心化会把它整个删掉。

## 阅读提示

**C 是命题 1 的对照，不是「更好的采样器」。** E3 里 C 的步长随 \(\sigma_n\) 无界增长，所以它在首达时间上会持续变快；D 的步长被约束封顶，于是被反超。这不是「噪声失效」，是步长比较。

**D 与 C 不是配对实验**（种子流不同、200 对 60）。如果要把两组做统计比较，用同一批种子重跑一遍再做配对检验。

## 引用

- Franzke & Kosko, *Phys. Rev. E* 84:041112 (2011); *Phys. Rev. E* 100:053309 (2019).
- Osoba, Mitaim & Kosko, *Fluct. Noise Lett.* 12(3):1350012 (2013); Osoba & Kosko, *Fluct. Noise Lett.* 15(1):1650007 (2016).
- Yano, Ishibashi & Oyamada, *arXiv:2610.19362* (2026)；Gao, Schulman & Hilton, *arXiv:2210.10760* (2022)；Dorner et al., *arXiv:2507.12399* (2025).
