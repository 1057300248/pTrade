# EvoQuant 深读：论文、代码可达性、相关工作与本仓库映射

研究时点：2026-08-22。本文是论文深读笔记，不改动任何策略代码。引用规范受 `docs/anti_overfit.md` 规则 17–19 约束。

## 0. 机构归属更正（先说结论）

- **EvoQuant 不是港大的**。EVOQUANT: Self-Evolving Verifier-Guided Strategy Optimization for Robust Quantitative Trading（[arXiv:2607.12455](https://arxiv.org/abs/2607.12455)，v1 2026-07-14）作者为毛杰、李昌伦、李想、段琦琦、袁金辉、刘翔、罗玉宇、唐静、褚晓文、唐南，机构是 **HKUST(GZ) 香港科技大学（广州）+ Paradoox AI Research**，通讯作者 nantang@hkust-gz.edu.cn。
- 两个方向都检索过（"HKU quantitative / evoquant / alpha mining" 与 "HKUST EvoQuant"）：**不存在港大（HKU）版的 EvoQuant**。用户口中的「港大 EvoQuant」映射到的就是这篇港科大（广州）论文。
- 但「港大」并非完全空穴来风：**CogAlpha（[arXiv:2511.18850](https://arxiv.org/abs/2511.18850)）确实出自 The University of Hong Kong**（School of Computing and Data Science，合作方 Grace Investment Machine、中国移动九天研究院）。它做的是 **alpha 因子挖掘**，不是已部署策略的优化。若要说"港大的量化进化框架"，最接近的实物是 CogAlpha；若说"EvoQuant"，归属必须写 HKUST(GZ)（`docs/anti_overfit.md` 规则 19 已固化此更正）。

## 1. 论文要解决的问题

与"从零生成策略/挖因子"的主流不同，EvoQuant 的输入是**一个用户已有的、已部署的量化策略**，目标是把人工的"诊断—改—回测—再改"循环自动化，同时防住 LLM 直接改写代码带来的三个病：幻觉编辑、策略漂移、回测过拟合。方法定位为**验证器引导的受约束程序进化**（verifier-guided constrained program evolution）。

## 2. 闭环八步（论文 Fig 2 四模块展开）

1. **摄取与表示**：把策略代码/规则解析为 AST，标注交易语义，分解为类型化策略基因组 g = (g_sig, g_risk, g_pos, g_entry, g_exit, ξ)，ξ 记录出处、策略家族、父代与变异史；基因组必须能重新编译回可执行策略。
2. **基线证据包**：在时间顺序的 train/val/test 切分上回测现任基因组，产出 EvidencePack：标量指标（收益/Sharpe/MDD/交易数/胜率）、交易行为画像（稀疏度、持有期分布、收益集中度）、市场状态敏感度、val→OOS 衰减 δ_oos、异常风险现象（止损过频、上行截断等）。
3. **瓶颈诊断与搜索计划**：LLM + 规则把证据包转成失败模式诊断 z_t（如风险规则截断 alpha、状态错配、验证集衰减），并产出搜索计划 p_t =（本轮目标、搜索层级、允许算子、禁止捷径、候选预算 K）。诊断约束生成器的动作空间——若瓶颈是 val→OOS 衰减，计划偏向简化与参数平滑，而非增加状态特判。
4. **分层候选生成**：从保守到激进四级——参数修复（回看期/阈值/止损宽度/仓位上限）→ 桥接编辑（入场过滤、出场规则、信号组合）→ 结构重设计 → 策略家族迁移。每个候选是**显式编辑计划**（目标层、操作、补丁、机制理由、预期指标变动、安全约束），必须满足类型化编辑契约：语义漂移 d_G(g,c) ≤ ε 且通过可执行/金融不变量检查 I(c)=1。
5. **编译、去重、多样化**：候选先编译，按基因组哈希去重，并做多样化，避免一轮预算全花在近似重复的编辑上。
6. **硬闸（hard gates）**：val 与 OOS 交易数 ≥ n_min、OOS 最大回撤 ≤ 上限、漂移 ≤ ε、不变量通过——先删掉不可执行、零交易、过度漂移、高回撤的候选，再谈打分。
7. **软分与自适应晋升**：Q(c) = w_v·ΔSharpe_val + w_o·ΔSharpe_oos + w_r·ΔReturn_oos − λ_d·P_回撤扩张 − λ_g·P_val−OOS落差 − λ_s·P_压力探针（费率/滑点扰动、延迟一根 K、参数抖动）。晋升引擎三态：adopt（超过自适应阈值才替换现任）/ incubate（机制可信但证据不足，暂存）/ reject（记录拒绝原因：零交易、OOS 崩塌、漂移过度、回撤异常）。
8. **记忆蒸馏与收敛**：把诊断、计划、编辑、证据、决定、失败原因蒸馏进策略知识库，供后续轮次检索成功范式、拉黑复发性失败；局部修复反复失败则升级搜索层级；结束时输出最优已验证基因组 + 前后对比报告 + 完整优化轨迹（含被拒候选）。

## 3. 实验数字与消融（只作论文事实陈述，不作本账簿预期）

- 设置：AKShare 日线 2020-01-01 至 2025-12-31；DeepSeek-R1；每次优化 20 轮。A 股 4 个策略族（EMA-RSI 趋势、布林-RSI 反转、放量突破、低波质量）× 随机抽 30 只股票逐一优化后等权成组合；BTC 3 个策略。
- 主结果：7 个策略平均测试集 Sharpe 从 **−0.298 提到 0.538**，最好的一个相对提升 **199%**；120 个 A 股任务中 115 个不劣化。
- 消融（放量突破任务，满配 Sharpe 提升 0.982）：去掉晋升引擎 → 0.128；固定阈值晋升 → 0.053；只调参数 → 0.274；随机变异 → 0.645；去掉规则诊断 → 0.693；去掉记忆 → 0.782。**验证/晋升引擎是承重墙，生成器只是配角**——与本仓库"验证器比生成器重要"的先验一致。
- 压力：费用滑点加倍后提升仍有 0.700；换切分点 → 0.368；滚动前推 → 0.370 / 0.545。减弱但不崩溃。
- 论文自报局限：随机 30 只股票、无退市重建、简化执行假设、逐股优化自由度大。**这些数字不可移植到本 ETF 账簿**（规则 18：严禁把 +199% 或 Sharpe 提升写成本仓库的预期或验收目标）。

## 4. 代码仓库可达性

论文脚注给出 https://anonymous.4open.science/r/EVOQUANT 。从本 VM 访问返回 **Cloudflare 403 challenge（首次尝试超时）**，无法通过挑战页取到仓库内容——不是确认的 404，但实际不可达，**模块清单无法核对**。本文对模块的描述全部以论文正文（Fig 2 四模块 + 3.1–3.4 节公式）为准；若日后代码可达，应回来核对 genome schema 与晋升阈值的实现细节。

## 5. 相关工作速览

| 工作 | 机构 | 做什么 | 与 EvoQuant 的区别 |
| --- | --- | --- | --- |
| CogAlpha（[2511.18850](https://arxiv.org/abs/2511.18850)） | **HKU** + Grace Investment Machine 等 | 代码级 alpha 因子进化：LLM 作认知代理，七级 agent 层级 + 多 agent 质检器 + 思维进化；CSI300 上 IC 0.0591 / RankIC 0.0814，报告超 21 个基线 | 挖新因子，不改已有策略 |
| QuantaAlpha（[2602.07085](https://arxiv.org/abs/2602.07085)） | 上财 AIFin Lab 牵头（团队含清华/北大/中科院/CMU/HKUST，**无 HKU**） | 轨迹级自进化因子挖掘：多样化规划初始化 + 轨迹变异（定位失败步、只重写该段）/交叉（重组高分父代片段）+ 生成约束防漂移防拥挤；CSI300 训练、CSI500/S&P500 迁移；[GitHub 开源](https://github.com/QuantaAlpha/QuantaAlpha) | 进化对象是挖掘轨迹，不是策略程序 |
| FactorEngine（[2603.16365](https://arxiv.org/abs/2603.16365)） | 北邮 + 北京值简科技 | 程序级（图灵完备）因子挖掘：三重分离——逻辑进化 vs 参数优化、LLM 方向搜索 vs 贝叶斯调参、LLM vs 本地算力；研报知识注入自举 + 经验库 | "LLM 管逻辑、本地管调参"的分工值得借鉴；仍是挖因子 |
| 经典 | — | WorldQuant《101 Formulaic Alphas》（Kakushadze 2016）：公式 alpha 模板库；AutoAlpha（2020）：分层遗传规划挖公式因子；AlphaEvolve（2021）：进化算子图；AlphaGen（2023）：RL 挖因子 | 共同教训：**候选生成便宜、验证贵**；搜索自由度越大，数据窥探越致命 |

## 6. 映射到本仓库

| EvoQuant 模块 | 本仓库对应物 |
| --- | --- |
| 类型化基因组 g_sig/g_risk/g_pos/g_entry/g_exit | 实盘文件已天然分层：`ptrade_adm_etf.py` 的 sig（`ts_momentum`、`month_gate`）、risk（`crowding_points`、`crash_triggered`）、pos（`build_targets`、波动目标、`lot_shares`）、entry/exit（`weekly_rebalance`、`rebalance_buy`、`crash_overlay`）；`ptrade_rmdc_etf.py` 的 sig（`residual_momentum`、`trend_quality`）、risk（拥挤四分、崩盘、`trailing_stop_hit`）、pos（`inverse_vol_weights`、`scale_to_vol_target`）、entry/exit（`apply_hysteresis`、周频调仓）。类型化实例已落地：`research/evoquant_genome_adm.json`（冻结层 mutable=false，仅少数维度开放候选值） |
| 证据包 EvidencePack | `research/` 回测群：`backtest_adm_etf.py`、`backtest_rmdc_etf.py`、`compare_strategies.py`、`ablate_*_knobs.py`；因子证据：`factor_mine_highdim.py/.md`、`factor_walkforward.py` 与报告；**人工版瓶颈诊断** = `rmdc_return_drag.md`（逐规则关闭实测 CAGR 拖累——与论文的 bottleneck diagnosis 同构，但证据是本仓库引擎的实际打印，不是 LLM 叙述） |
| 验证器 + 晋升引擎 | `docs/anti_overfit.md` 规则 1–19 + 评审附注十点。**与论文冲突之处以本仓库为准（更严）**，见下 |
| 记忆/拒绝台账 | `research/evoquant_candidates.md`（候选、诊断、决定、拒绝原因） |

**核心冲突及本仓库的更严改法**：论文的晋升分数 Q(c) 直接含 ΔSharpe_oos，证据包含 δ_oos——**优化循环每一轮都看 OOS**。反复以 OOS 为选择依据会把 OOS 变成样本内（规则 2/10 禁止）。本仓库的改法：循环只允许看 **2018–2021 IS** 证据做选择；**2022–2026 OOS 只在候选集冻结后一次性读数**；2024-02 / 2026-07 压力窗口只做 pass/fail、永不参与生成或选择。`research/evoquant_loop.py` 已按此实现（8 个受控候选、维度白名单、无回看期网格、不碰实盘文件）。

## 7. 不需要 LLM 重写实盘文件就能落地的三件事（现状与缺口）

1. **类型化基因组 JSON** —— 已落地：`research/evoquant_genome_adm.json`。缺口：RMDC 版尚未导出；层的 a-priori 取值边界应注明文献出处（规则 10）。
2. **候选编辑计划** —— 已落地：`research/evoquant_candidates.md`（显式候选集 + 诊断 + 决定；人审后手工改实盘文件，LLM 永不直接写 `ptrade_*.py`，符合规则 17 与实盘约束：无 sklearn、因子 ≤ 4）。
3. **IS/OOS 验证器脚本** —— 已落地：`research/evoquant_loop.py`（IS 2018–2021 选择、OOS 一次性读数、压力窗口 pass/fail、拒绝原因记录）。缺口：**N_trials 台账 + Deflated Sharpe 自动计算**（规则 6/17：每个生成过的候选都要入账，包括被循环自杀的）；论文的三个压力探针（费率加倍、延迟一根 K 成交、参数抖动）纯数值即可实现，可补进验证器。

## 8. 我们抄什么 / 不抄什么

**抄**（多数已在仓库落地）：

- 类型化基因组 + 显式编辑计划（改哪层、为什么、预期动哪个指标）——漂移约束与事后审计。
- "硬闸在先、软分在后"的验证顺序：交易数下限、回撤上限、不变量检查先杀掉垃圾候选。
- 拒绝台账与 incubate 中间态：失败原因入库、拉黑复发失败，而不是只记幸存者。
- 压力探针三件套（费率加倍、one-bar delay、参数抖动）——无 LLM 依赖，直接进验证器。
- "晋升引擎 > 生成器"的消融结论，作为资源分配依据：本仓库继续把工程预算花在验证器上。

**不抄**：

- 晋升分数里的 OOS 项与循环内反复读 OOS——改为冻结 IS 选择 + 单次 OOS 读数（规则 2/10）。
- 策略家族迁移（family migration）层级——对已部署账簿漂移过大，本仓库的编辑上限是桥接级。
- LLM 直接改写实盘文件——只允许产出研究端编辑计划，人审后手工落地（规则 17）。
- 论文的 +199% / Sharpe −0.298→0.538 作为预期或验收目标（规则 18）。
- 其 A 股实验设计（随机 30 股、无退市重建、逐股优化）——自由度过大，不作为本仓库证据标准。

## 参考

1. EVOQUANT（HKUST(GZ) + Paradoox AI Research，2026-07-14）— https://arxiv.org/abs/2607.12455 （HTML：https://arxiv.org/html/2607.12455v1 ；代码：https://anonymous.4open.science/r/EVOQUANT ，本 VM 不可达，Cloudflare 403）
2. CogAlpha（HKU，2025-11）— https://arxiv.org/abs/2511.18850
3. QuantaAlpha（上财 AIFin Lab 等，2026-02）— https://arxiv.org/abs/2602.07085 ；https://github.com/QuantaAlpha/QuantaAlpha
4. FactorEngine（北邮 + 值简科技，2026-03）— https://arxiv.org/abs/2603.16365
5. Kakushadze, 101 Formulaic Alphas（WorldQuant, 2016）— https://arxiv.org/abs/1601.00991
6. Zhang et al., AutoAlpha（2020）— https://arxiv.org/abs/2002.08245
7. Cui et al., AlphaEvolve（SIGMOD 2021）；Yu et al., AlphaGen（KDD 2023）— 经典 GP/RL 因子挖掘线
8. 本仓库：`docs/anti_overfit.md`（规则 17–19）、`research/evoquant_loop.py`、`research/evoquant_genome_adm.json`、`research/evoquant_candidates.md`、`research/rmdc_return_drag.md`
