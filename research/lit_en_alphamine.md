# English-language literature sweep: automated alpha mining

## Scope and count

This sweep contains **147 sources with 147 unique URLs**. The machine-readable
catalog is [`lit_en_alphamine.csv`](lit_en_alphamine.csv); its IDs (`EN001` to
`EN147`) are used throughout this note.

The search covers genetic programming (GP) for trading and factor discovery,
WorldQuant-style formulaic alphas, AutoAlpha, AlphaGen, CogAlpha, QuantaAlpha,
FactorEngine, RD-Agent, EvoQuant, LLM-based factor mining, adjacent symbolic
regression, evaluation controls, and agentic trading infrastructure. It includes
papers, surveys, code, benchmarks, platforms, a dataset, and a book. A paper and
its implementation are separate sources because they serve different
replication needs; no URL is counted twice.

| Source type | Count |
| --- | ---: |
| Paper | 91 |
| Survey | 16 |
| Code | 32 |
| Benchmark | 3 |
| Platform | 2 |
| Book | 1 |
| Dataset | 1 |
| Tool | 1 |
| **Total** | **147** |

## Coverage map

| Theme | CSV IDs | Count | What it contributes |
| --- | --- | ---: | --- |
| WorldQuant and automated formulaic alpha systems | EN001–EN030 | 30 | Formula languages, evolutionary search, RL, MCTS, GFlowNets, grammar guidance, and set-level alpha objectives |
| LLM and agentic alpha mining | EN031–EN063 | 33 | Code generation, memory, retrieval, evolutionary trajectories, safe execution, benchmarks, and verifier loops |
| GP and evolutionary trading rules | EN064–EN085 | 22 | Long-run evidence on rule evolution, typing, robustness, market frictions, and out-of-sample testing |
| General symbolic regression and program search | EN086–EN110 | 25 | GP engines, neural symbolic regression, transformer decoding, and LLM-guided evolution |
| Quant infrastructure and factor-validation controls | EN111–EN132 | 22 | Qlib, FinRL, Alphalens, asset-pricing baselines, multiple testing, replication, and factor decay |
| Adjacent financial LLM agents | EN133–EN147 | 15 | Memory, multimodal tools, multi-agent organization, trading evaluation, and deployment surveys |

## Named systems requested

| System or topic | Principal sources | Short assessment |
| --- | --- | --- |
| WorldQuant formulaic alpha | [101 Formulaic Alphas](https://arxiv.org/abs/1601.00991) (EN001), [Finding Alphas](https://onlinelibrary.wiley.com/doi/book/10.1002/9781119571278) (EN003), [WorldQuant BRAIN](https://www.worldquant.com/brain/) (EN004), implementations EN005–EN006 | Establishes the price/volume expression vocabulary, practical workflow, and crowdsourced simulation setting used by later miners. |
| Genetic programming alpha | [Genetic-Alpha](https://github.com/Morgansy/Genetic-Alpha) (EN007), AutoAlpha (EN008), warm-start GP (EN015), finance-GP studies EN064–EN085 | GP remains the clearest baseline for transparent tree expressions, but requires strict complexity, turnover, and holdout controls. |
| AutoAlpha | [AutoAlpha](https://doi.org/10.48550/arxiv.2002.08245) (EN008) | Hierarchical evolutionary search and quality-diversity mechanisms target efficient exploration and less redundant formulas. |
| AlphaGen | [KDD paper](https://doi.org/10.1145/3580305.3599831) (EN010), [official code](https://github.com/ICT-FinD-Lab/alphagen) (EN011), extended study (EN012) | Changes the objective from finding individually strong formulas to finding a synergistic collection for a downstream combiner. |
| CogAlpha | [Cognitive Alpha Mining via LLM-Driven Code-Based Evolution](https://aclanthology.org/2026.acl-long.538/) (EN041) | Evolves executable alpha code through staged reasoning, mutation, recombination, and empirical feedback. |
| QuantaAlpha | [paper](https://arxiv.org/abs/2602.07085) (EN042), [code](https://github.com/QuantaAlpha/QuantaAlpha) (EN043) | Evolves complete mining trajectories rather than isolated formulas or prompts. |
| FactorEngine | [FactorEngine](https://doi.org/10.48550/arxiv.2603.16365) (EN054) | Moves beyond a narrow expression grammar to program-level factors, combining LLM logic with parameter optimization. |
| RD-Agent | [R&D-Agent-Quant](https://arxiv.org/abs/2505.15155) (EN055), [RD-Agent code](https://github.com/microsoft/RD-Agent) (EN056), Qlib (EN111–EN113) | Automates hypothesis, implementation, backtesting, and joint factor/model iteration in a reproducible quant stack. |
| EvoQuant | [EVOQUANT](https://arxiv.org/abs/2607.12455) (EN057), [code artifact](https://anonymous.4open.science/r/EVOQUANT) (EN058) | A verifier-guided full-strategy optimizer rather than a pure formula-factor miner; useful for controlled edits and validation gates. |
| LLM factor mining | AlphaAgent (EN031–EN032), FAMA (EN033), Alpha-GPT (EN034), Alpha Jungle (EN037), Chain-of-Alpha (EN038), AlphaBench (EN044–EN047), Hubble through QuantEvolver (EN048–EN053), and EN059–EN063 | The field is converging on constrained generation, executable feedback, memory/retrieval, diversity control, and trajectory-level optimization. |

## EvoQuant affiliation and HKU check

The affiliation needs to be stated precisely: arXiv
[`2607.12455`](https://arxiv.org/abs/2607.12455) lists **The Hong Kong
University of Science and Technology (Guangzhou), abbreviated HKUST(GZ), and
Paradoox AI Research**. It does **not** list the University of Hong Kong (HKU).
HKUST(GZ) and HKU are different institutions.

Exact-name domain searches were run against HKU's
[School of Computing and Data Science](https://cds.hku.hk/),
[Business School](https://www.hkubs.hku.hk/), and relevant official surfaces
including the [Lab for AI-Agents in Business and
Economics](https://camo.hku.hk/research-labs/research-labs-lab-for-ai-agents-in-business-and-economics/)
and [HKU Quantitative Research
Society](https://ug.hkubs.hku.hk/student-enrichment/student-run-organizations/hku-quantitative-research-society).
As of **2026-08-22**, no official HKU lab, paper, or project named “EvoQuant”
was found. This is a bounded negative search result, not proof that no
unindexed or future HKU work can use the name.

## Main findings

### 1. The optimization target has moved from a factor to a factor set

Early formula-mining systems often maximize the information coefficient or a
backtest score for one expression. AlphaGen (EN010–EN012), AlphaForge
(EN013–EN014), RiskMiner (EN016), and AlphaSAGE (EN021–EN022) instead emphasize
complementarity, diversity, or a portfolio of expressions. This is materially
closer to production, where a high standalone score can add little after
existing exposures are controlled.

### 2. Search methods are becoming hybrid

The literature progresses from classical GP and genetic algorithms (EN064–
EN085), through neural-guided symbolic regression (EN090–EN107), to RL, MCTS,
GFlowNets, grammar-guided search, and LLM evolution (EN010–EN063). The strongest
design pattern is not “LLM replaces search”; it is an LLM proposing semantic
changes inside a typed or grammar-constrained search space, with deterministic
execution and empirical selection.

### 3. Representation is a risk-control decision

Tree expressions are easy to type-check and simplify. A DSL or AST sandbox, as
used by AlphaAgent, Hubble, FactorMiner, and AlphaBench (EN031–EN032,
EN044–EN049), limits look-ahead operators and invalid formulas. Program-level
systems such as FactorEngine (EN054) are more expressive but enlarge the
leakage, runtime, and reproducibility surface. The representation therefore
needs an explicit operator whitelist, lag semantics, units, and complexity
budget.

### 4. LLM systems increasingly evolve the research process itself

QuantaAlpha, FactorMiner, AlphaPROBE, QuantEvolver, and EvoQuant (EN042–EN058)
store experience, retrieve prior candidates, track genealogy, update policies,
or distill verifier feedback. Their unit of optimization is a trajectory,
factor family, or strategy revision rather than one prompt response. That can
reduce repeated failed experiments, but it also makes provenance and immutable
experiment logs essential.

### 5. Evaluation is the binding constraint

The factor-zoo and replication literature (EN117–EN132) warns that a large
automated search can manufacture apparently significant alphas. Relevant
failure modes include multiple testing, correlated candidates, post-selection
bias, publication decay, unstable universes, survivorship bias, ignored
turnover, and silent look-ahead. AlphaEval and AlphaBench (EN025, EN044–EN047)
are useful additions, but they do not remove the need for a chronological
holdout and realistic implementation costs.

## Practical reading path

1. Start with the formula language and evaluation problem: EN001, EN002,
   EN003, EN120–EN124.
2. Compare search objectives: AutoAlpha (EN008), AlphaGen (EN010–EN012),
   AlphaForge (EN013–EN014), and AlphaSAGE (EN021–EN022).
3. Add symbolic-search foundations: EN087–EN093 and EN102–EN107.
4. Study LLM controls rather than generation alone: AlphaAgent (EN031–EN032),
   AlphaBench (EN044–EN047), Hubble (EN048), FactorMiner (EN049–EN050), and
   AlphaPROBE (EN051–EN052).
5. Compare end-to-end research agents: RD-Agent (EN055–EN056), FactorEngine
   (EN054), QuantaAlpha (EN042–EN043), and EvoQuant (EN057–EN058).
6. Use Qlib, Alphalens, and Open Source Asset Pricing (EN111–EN116,
   EN128–EN129) to reproduce and challenge results.

## Minimum validation standard suggested by the sweep

- Freeze the operator grammar, raw fields, lags, universe, and preprocessing
  before opening the final holdout.
- Separate train, validation, and untouched chronological test periods; report
  every search run, not only the selected formula.
- Deduplicate expressions structurally and by return correlation; benchmark
  incremental value after known factors and the current production library.
- Include costs, turnover, capacity, delayed execution, missing data,
  delistings, and survivorship treatment.
- Track formula/program lineage, prompts, model versions, seeds, code, data
  versions, and all verifier outcomes.
- Prefer simple, stable candidates across subperiods and universes over the
  highest in-sample score.

## Collection and link validation

The catalog was assembled from publisher pages, arXiv, proceedings,
institutional/project pages, and official or clearly identified repositories.
Automated URL validation on **2026-08-22** found no duplicate URLs, no HTTP 404
responses, and no network-resolution failures: 119 links returned HTTP 200/202;
28 publisher or repository links resolved but returned HTTP 403 to the
automated client. A reachable URL is not, by itself, an endorsement of a
paper's empirical claims; the relevance field records why the source belongs
in this sweep.
