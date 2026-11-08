# REI Scientist research report: rastrigin-global-search-pilot

## Integrity and disclosure

**Research status: PASS**. This is an automated exploratory engineering experiment, **not a peer-reviewed scientific publication**.
Any model-assisted configurations must be disclosed; LLM proposals used: **NO**.

## Research question

Does simulated annealing yield a lower objective than random search on a multimodal Rastrigin benchmark under an identical evaluation budget?

**Predeclared hypothesis:** On independent holdout seeds, one registered local search method provides at least a 5 percent improvement over uniform random search without crossing the evaluation budget.

## Protocol

- Benchmark: `rastrigin`, dimension: 2, bounds: (-5.12, 5.12)
- Objective: **minimize** analytic benchmark; independently recomputed at the reported solution
- Baseline: `random_search`; development seeds: [11, 23, 37]
- Holdout seeds, never used for configuration selection: [101, 103, 107, 109, 113]
- Evaluation budget: **180 per method per seed**, candidates explored: 10 / 10
- Predeclared target: **5.00%** relative improvement, positive bootstrap lower bound
- Source note: Controlled multimodal synthetic benchmark; external validity not assessed

## Development search (not confirmatory evidence)

| Configuration | Development mean objective | Parent |
|---|---:|---|
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.12, 'temperature': 8.0} | 1.1595432 | `2ab2dc49a312` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.12, 'temperature': 4.0} | 1.3042315 | `d4f2cba8318f` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.12, 'temperature': 2.0} | 1.3474276 | `root` |
| `simulated_annealing` {'cooling': 0.9409, 'step_fraction': 0.12, 'temperature': 4.0} | 1.4088101 | `2ab2dc49a312` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.12, 'temperature': 1.0} | 1.5928858 | `d4f2cba8318f` |
| `simulated_annealing` {'cooling': 0.9409, 'step_fraction': 0.12, 'temperature': 2.0} | 1.5928858 | `d4f2cba8318f` |
| `simulated_annealing` {'cooling': 0.9894, 'step_fraction': 0.12, 'temperature': 4.0} | 1.9383685 | `2ab2dc49a312` |
| `hill_climb` {'step_fraction': 0.12} | 2.4589296 | `root` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.06, 'temperature': 2.0} | 2.6160532 | `d4f2cba8318f` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.18, 'temperature': 2.0} | 4.7355239 | `d4f2cba8318f` |
| `random_search` {} | 5.44809 | `root` |

**Selected configuration:** `simulated_annealing` `{'cooling': 0.97, 'step_fraction': 0.12, 'temperature': 8.0}`.
Selection uses only development seeds. Holdout results are evaluated once after selection.

## Independent holdout evaluation

- Baseline mean: **4.835259**
- Candidate mean: **1.6623625**
- Absolute mean improvement: **3.1728965**
- Relative mean improvement: **65.620%**
- Paired wins: **3/5**
- Exploratory paired bootstrap 95% CI of mean improvement: **[0.2240510133439379, 6.3550280905802]**

**Decision: PASS**. Reasons: Target met and paired-bootstrap lower bound > 0; exploratory result only.

## Independent verification

- Feasibility bounds and dimensionality checked for every recorded solution.
- Objective values recomputed using a separate reference implementation.
- Every recorded run checked against the prescribed evaluation count.
- Exact stochastic traces are fingerprinted with SHA-256 for reproducibility investigation.

## Provenance and reproducibility

- Study SHA-256: `0ab4bf6e43757d08345c3dcd9f7a2b91ce88cc7cfc1f8976c41e5d3702ca5453`
- Results SHA-256: `86739b69f9177294c56f4980927a1505a52b17d630a6d9784c3bb9eaacb19388`
- Source snapshot SHA-256: `5dcb1362e3174e3eba0bb6cab3c9d700d669c03efa6caf08fde8fcfc538d43da`
- Python: `3.13.5`
- Total objective evaluations: 7740
- Data: Analytic, deterministic synthetic benchmarks; no customer data
- Re-run the source study JSON and compare results, ignoring elapsed time and generated timestamps.

## Related work

- No literature retrieval was executed. Related-work coverage: NOT VERIFIED.

## Limitations, risks and release gate

- Synthetic analytic benchmarks do not establish performance on real machinery, GNSS, medical, or industrial data.
- The percentile bootstrap is exploratory and cannot establish a formal generalization guarantee with a small holdout set.
- The hyperparameter search can overfit development seeds; holdout seeds are isolated but benchmark selection was not blinded.
- Some algorithms and benchmarks have different landscapes; results cannot be generalized to other objective functions.
- Literature metadata alone does not verify scientific claims. References must be checked against original papers before publication.
- Manuscript submission requires independent human review, full methods disclosure and external replication.

## Next experiment

Add a separately versioned real or synthetic domain-specific benchmark through a reviewed, approved adapter. Do not grant model-written code access to the host environment.
