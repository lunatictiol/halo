# M4: corrective loop vs M3

Sources: `results/m3_hybrid_rerank_*.json`, `results/m4_graph_*.json`. Generator and judge `qwen3:8b`, M4 commit `8b61496`. Context metrics are on the hits the answer was generated from (M4: the final attempt).

| Metric | M3 `m3_hybrid_rerank` | M4 `m4_graph` |
|---|---|---|
| Correct | 0.908 | 0.858 |
| Correct|ans | 0.926 | 0.939 |
| Faithful | 0.987 | 0.986 |
| False-abstention | 0.020 | 0.086 |
| MRR (context used) | 0.830 | 0.814 |
| R@5 (context used) | 0.944 | 0.937 |
| Correct, text modality | 0.951 | 0.912 |
| **Abstention rate on `abstention_set`** | 0.809 | **0.934** |
| Avg retries / query (`dev_sample`) | 0 | 0.234 |
| Avg retries / query (`abstention_set`) | 0 | 1.862 |
| Median end-to-end ms (`dev_sample`) | 14551 | 17791 |

## By slice (`dev_sample`)

| Slice | n | Correct M3 | Correct M4 | False-abst M3 | False-abst M4 |
|---|---|---|---|---|---|
| abstractive | 179 | 0.911 | 0.844 | 0.011 | 0.106 |
| extractive | 124 | 0.903 | 0.879 | 0.032 | 0.057 |
| text | 204 | 0.951 | 0.912 | 0.010 | 0.049 |
| text-image | 72 | 0.806 | 0.736 | 0.056 | 0.181 |
| text-table | 13 | 0.769 | 0.846 | 0.000 | 0.000 |
| text-table-image | 14 | 0.929 | 0.714 | 0.000 | 0.214 |

## Loop behaviour

- `dev_sample`: retries histogram {'0': 259, '1': 17, '2': 27}, queries over the retry limit: **0**, abstained by grader 26, by generator 0.
- `abstention_set`: retries histogram {'0': 9, '1': 3, '2': 140}, queries over the retry limit: **0**, abstained by grader 139, by generator 3.

## Paired per-query changes (`dev_sample`, correctness)

- Wrong/refused in M3, correct in M4: **8**
- Correct in M3, wrong/refused in M4: **23**

## Rescued first retrievals (14 answerable questions graded insufficient first, then answered correctly; 5 shown)

### `02e11dcd-d7d5-44a7-9116-6db96345ca6a` (abstractive, text-image)

- **Question:** How does the piecewise polynomial approximation contribute to function smoothing?
- **Attempt 1 grade:** insufficient: The passages mention that piecewise polynomials are used for trajectory generation and smoothing, but they do not explicitly explain how piecewise polynomial approximation contributes to function smoothing.
- **Rewrite 1:** `How does piecewise polynomial approximation enable smooth function interpolation through local polynomial fitting?`
- **Gold in top-5:** first attempt no, final yes (MRR 0.00 → 0.20)
- **Answer:** The piecewise polynomial approximation contributes to function smoothing by allowing the construction of a smooth global approximation through local polynomial approximations that are "glued together" using a smooth partition of unity, ensuring continuity and differentiability across subdomains.
- **Reference:** Piecewise polynomial approximation contributes by matching target functions at specific points, allowing for smooth transitions across subdomains when combined with a partition of unity, ensuring continuity and uniform error bounds.

### `c1bcf690-85d6-478c-9593-13fb1d57c277` (abstractive, text-table)

- **Question:** How do different predictors influence the dependent variable in a 4D Ridge Regression model for TM polarization?
- **Attempt 1 grade:** insufficient: The passages discuss how adding predictors affects the MSE and precision in a Ridge Regression model for TM polarization, but they do not explicitly mention the influence of different predictors on the dependent variable in a 4D Ridge Regression model.
- **Rewrite 1:** `How do varying predictor variables impact the dependent variable in a four-dimensional Ridge Regression framework applied to TM polarization analysis?`
- **Gold in top-5:** first attempt no, final yes (MRR 0.11 → 0.20)
- **Answer:** In the 4D Ridge Regression model for TM polarization, the predictors influence the dependent variable as follows: y1 has a slight negative relationship, y2 also has a slight negative relationship, y3 has a small positive relationship, and y4 has a strong positive relationship. The coefficients are -0.1681, -0.0515, 0.0690, and 0.9514, respectively.
- **Reference:** In the 4D Ridge Regression model for TM polarization, the intercept is -0.0162, indicating the expected value of the dependent variable x when all predictors are zero. The predictor y1 has a coefficient of -0.1681, showing a slight negative relationship with x. Similarly, y2 has a coefficient of -0.0515, also suggesting a minor negative impact on x. On the other hand, y3 has a positive coefficient of 0.0690, and y4 exhibits a strong positive relationship with x with its coefficient being 0.9514.

### `3738d2b7-fe0b-412a-bdf7-c88a0f0e4aee` (abstractive, text-image)

- **Question:** How are filamentary coils approximated in discrete optimization?
- **Attempt 1 grade:** insufficient: The passages discuss the approximation of filamentary coils using wireframes and mention that space curves are approximated as polygons, but they do not explicitly explain how filamentary coils are approximated in discrete optimization.
- **Rewrite 1:** `How are filamentary coils modeled as polygonal chains in discrete optimization algorithms?`
- **Gold in top-5:** first attempt yes, final no (MRR 1.00 → 0.12)
- **Answer:** Filamentary coils are approximated in discrete optimization by using wireframe current paths that consist of interconnected wire segments. These paths, while containing sharp, angular turns, serve as a starting point for more realistic coil designs and can be refined using optimization techniques such as FOCUS, DESC, GOSPEL, or SIMSOPT.
- **Reference:** Filamentary coils are often approximated as polygons, where space curves are represented by straight wire segments. This simplification allows for easier calculation of magnetic fields using methods like the Biot-Savart law.

### `3bf50a20-f201-4cf0-ae09-84ba1fdc7304` (abstractive, text)

- **Question:** How can likelihood-based approaches be used in parameter estimation for differential equation models?
- **Attempt 1 grade:** insufficient: The passages discuss likelihood-based approaches in parameter estimation for differential equation models but do not explicitly explain how likelihood-based approaches are used in parameter estimation for differential equation models.
- **Rewrite 1:** `What are the specific likelihood functions and optimization techniques used in parameter estimation for differential equation models?`
- **Gold in top-5:** first attempt yes, final yes (MRR 1.00 → 0.50)
- **Answer:** Likelihood-based approaches can be used in parameter estimation for differential equation models by constructing profile likelihood functions through numerical optimization. These functions help assess parameter identifiability and estimate parameters by maximizing the likelihood, allowing for both point estimates and uncertainty quantification.
- **Reference:** Likelihood-based approaches involve using statistical methods to estimate parameters by maximizing the likelihood function, which measures how well the model with certain parameters explains the observed data. This approach helps in accurately estimating parameters within differential equation models.

### `5c6a0b72-e091-4f4e-939d-9a9d7f385962` (abstractive, text)

- **Question:** In what domains has the GAN architecture demonstrated superior performance?
- **Attempt 1 grade:** insufficient: The passages mention that GAN architecture has demonstrated superior performance in multiple domains, but they do not specify which domains.
- **Rewrite 1:** `What specific domains and applications have shown superior performance when using GAN architectures compared to other generative models?`
- **Gold in top-5:** first attempt yes, final yes (MRR 1.00 → 1.00)
- **Answer:** The GAN architecture has demonstrated superior performance in image generation, super-resolution, and 3D object generation.
- **Reference:** The GAN architecture has demonstrated superior performance in image generation, super-resolution, and 3D object generation.

## Correct abstentions (5 shown)

### `02ec0c1e-a71b-4536-abaa-73fbd56a541f` (grader abstained after 2 retries)

- **Question:** What happens when all consumers are allowed to migrate with respect to inter-regional trade integration?
- **Query 1:** `What happens when all consumers are allowed to migrate with respect to inter-regional trade integration?`
- **Query 2:** `What are the economic implications of unrestricted consumer migration on inter-regional trade integration and market convergence?`
- **Query 3:** `What are the effects of full consumer mobility on inter-regional trade integration and convergence in multi-region economic models?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages discuss market integration, price contagion, and the impact of shocks on economic systems, but they do not directly address what happens when all consumers are allowed to migrate with respect to inter-regional trade integration.

### `08a19e39-f793-4b59-9656-8621dd1ad72e` (grader abstained after 2 retries)

- **Question:** What is the main challenge in training energy-based models?
- **Query 1:** `What is the main challenge in training energy-based models?`
- **Query 2:** `What are the primary difficulties in optimizing energy-based models during training?`
- **Query 3:** `What are the key challenges in training deep energy-based models and how do they affect convergence?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages discuss challenges in federated learning (FL) training on mobile devices, such as system dynamics, communication constraints, and static subnetwork assignments, but they do not specifically address the main challenge in training energy-based models.

### `08c9a683-df57-4491-8056-5399b34a304d` (grader abstained after 2 retries)

- **Question:** Is the function for estimating causal effects dependent on both alpha and beta transposed with X?
- **Query 1:** `Is the function for estimating causal effects dependent on both alpha and beta transposed with X?`
- **Query 2:** `Is the function for estimating causal effects in linear regression dependent on the transposition of alpha and beta with the covariate matrix X?`
- **Query 3:** `Is the function for estimating causal effects in linear regression dependent on the transposition of the coefficient vectors alpha and beta with the covariate matrix X?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages do not mention anything about the function for estimating causal effects depending on alpha and beta transposed with X.

### `0949e078-a396-4840-801b-b0bc8ef905d1` (grader abstained after 2 retries)

- **Question:** How do consumer preferences affect regional utility in economic models?
- **Query 1:** `How do consumer preferences affect regional utility in economic models?`
- **Query 2:** `How do consumer preference parameters influence regional utility functions in spatial economic models?`
- **Query 3:** `How do consumer preference heterogeneity and spatial utility functions interact in regional economic equilibrium models?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages discuss consumer preferences and their impact on CSA participation in Japan, but they do not directly address how consumer preferences affect regional utility in economic models.

### `09a82aff-63f2-4955-99b2-5e0255226bba` (grader abstained after 2 retries)

- **Question:** At what collision energy does the cross-section stabilize around 100 Å² for all transitions?
- **Query 1:** `At what collision energy does the cross-section stabilize around 100 Å² for all transitions?`
- **Query 2:** `What collision energy corresponds to the stabilization of the cross-section at approximately 100 Å² for all transition processes?`
- **Query 3:** `What is the collision energy at which the cross-section stabilizes to approximately 100 Å² across all transition channels?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages do not mention anything about collision energy or cross-section stabilization.
