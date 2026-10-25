# 噪声系列的可复现代码

配套博客系列「噪声、不等式与采样器」（<https://dmithrandir.github.io/mcmc/>）。

只依赖 `numpy`、`scipy`、`matplotlib`。所有脚本都可以从本目录直接运行：

```bash
pip install numpy scipy matplotlib
python experiments.py            # 四组对照（E1）+ 噪声扫描（E3），约 20–40 分钟
python matched_step_control.py   # 等步长对照：D 的收益是否只是步长，约 15 分钟
```

`experiments.py` 会把图与 `results.json` 写到 `./output/`（自动创建）。
`results.json` 是当前版本已跑出的结果，可以直接拿来核对博客里的每个数字，不必重跑。

## 文件

| 文件 | 内容 |
|---|---|
| `core.py` | 目标分布、MH、噪声 MH、经验 KL、积分自相关时间、ESS、R-hat |
| `experiments.py` | E1 四组对照（A/B/C/D）、E3 噪声扫描、机制相关性 |
| `matched_step_control.py` | 关键对照：用与约束组等步长的朴素 MH 复跑首达问题 |
| `results.json` | `experiments.py` 的输出（接受率、τ、KL 曲线、扫描结果） |

## 四组是什么

目标是双峰高斯混合 \(0.5\,N(-2, 0.75^2) + 0.5\,N(2, 0.75^2)\)，基础提议 \(N(0,1)\)：

- **A** 朴素随机游走 MH，\(\sigma=1\)
- **B** 盲注噪声：候选 \(x+s+n\)，\(s\sim N(0,1)\)，\(n\sim N(0,\sigma_n^2)\)
- **C** 方差匹配 MH：提议 \(\sigma=\sqrt{1+\sigma_n^2}\)（命题 1 要求的对照）
- **D** 约束噪声：\(n\) 按二次条件 \(n^2 - 2sn \le -2\sigma^2 A(x_t)\) 做拒绝采样，\(A\) 用 48 点 Gauss–Hermite 在真实目标上逐点积分

E3 的度量是"从 \(x_0=-5\) 首次进入 \(x>1.25\) 的步数"（燃烧期语境）；E1 的度量是接受率、积分自相关时间与运行经验 KL（混合语境）。

## 两点阅读提示

1. **C 是命题 1 的对照，不是"更好的采样器"。** E3 里 C 的步长随 \(\sigma_n\) 无界增长，所以它在首达时间上会持续变快；D 的步长被约束封顶，于是被反超。这不是"噪声失效"，是步长比较。
2. **D 与 C 不是配对实验**（种子流不同、200 对 60）。如果要把两组做统计比较，用同一批种子重跑一遍再做配对检验。

## 引用

- Franzke & Kosko, *Phys. Rev. E* 84:041112 (2011); *Phys. Rev. E* 100:053309 (2019).
- Osoba, Mitaim & Kosko, *Fluct. Noise Lett.* 12(3):1350012 (2013); Osoba & Kosko, *Fluct. Noise Lett.* 15(1):1650007 (2016).
