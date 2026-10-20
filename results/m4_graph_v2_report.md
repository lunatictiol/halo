# M4: corrective loop vs M3

Sources: `results/m3_hybrid_rerank_*.json`, `results/m4_graph_v2_*.json`. Generator and judge `qwen3:8b`, M4 commit `1ac9b45`. Context metrics are on the hits the answer was generated from (M4: the final attempt).

| Metric | M3 `m3_hybrid_rerank` | M4 `m4_graph_v2` |
|---|---|---|
| Correct | 0.908 | 0.908 |
| Correct|ans | 0.926 | 0.939 |
| Faithful | 0.987 | 0.986 |
| False-abstention | 0.020 | 0.033 |
| MRR (context used) | 0.830 | 0.820 |
| R@5 (context used) | 0.944 | 0.937 |
| Correct, text modality | 0.951 | 0.946 |
| **Abstention rate on `abstention_set`** | 0.809 | **0.882** |
| Avg retries / query (`dev_sample`) | 0 | 0.086 |
| Avg retries / query (`abstention_set`) | 0 | 1.737 |
| Median end-to-end ms (`dev_sample`) | 14551 | 16214 |

## By slice (`dev_sample`)

| Slice | n | Correct M3 | Correct M4 | False-abst M3 | False-abst M4 |
|---|---|---|---|---|---|
| abstractive | 179 | 0.911 | 0.922 | 0.011 | 0.022 |
| extractive | 124 | 0.903 | 0.887 | 0.032 | 0.048 |
| text | 204 | 0.951 | 0.946 | 0.010 | 0.015 |
| text-image | 72 | 0.806 | 0.833 | 0.056 | 0.083 |
| text-table | 13 | 0.769 | 0.769 | 0.000 | 0.000 |
| text-table-image | 14 | 0.929 | 0.857 | 0.000 | 0.071 |

## Loop behaviour

- `dev_sample`: retries histogram {'0': 287, '1': 6, '2': 10}, queries over the retry limit: **0**, abstained by grader 9, by generator 1.
- `abstention_set`: retries histogram {'0': 17, '1': 6, '2': 129}, queries over the retry limit: **0**, abstained by grader 124, by generator 10.

## Paired per-query changes (`dev_sample`, correctness)

- Wrong/refused in M3, correct in M4: **8**
- Correct in M3, wrong/refused in M4: **8**

## Rescued first retrievals (7 answerable questions graded insufficient first, then answered correctly; 5 shown)

### `3738d2b7-fe0b-412a-bdf7-c88a0f0e4aee` (abstractive, text-image)

- **Question:** How are filamentary coils approximated in discrete optimization?
- **Attempt 1 grade:** insufficient: The passages discuss the approximation of filamentary coils using wireframe segments and mention that space curves are approximated as polygons, but they do not explicitly explain how filamentary coils are approximated in discrete optimization.
- **Rewrite 1:** `How are filamentary coils modeled as polygonal chains in discrete optimization algorithms?`
- **Gold in top-5:** first attempt yes, final no (MRR 1.00 → 0.12)
- **Answer:** Filamentary coils are approximated in discrete optimization by using wireframe current paths that consist of interconnected wire segments. These paths, while containing sharp, angular turns, serve as a starting point for more realistic coil designs and can be refined using optimization techniques such as FOCUS, DESC, GOSPEL, or SIMSOPT.
- **Reference:** Filamentary coils are often approximated as polygons, where space curves are represented by straight wire segments. This simplification allows for easier calculation of magnetic fields using methods like the Biot-Savart law.

### `6a149c18-c83d-4faa-8210-bbd6e598216b` (abstractive, text-image)

- **Question:** How does graph Laplacian coupling contribute to understanding pattern formations?
- **Attempt 1 grade:** insufficient: The passages discuss graph Laplacian coupling in the context of pattern formation and its role in modeling spatial dynamics, but they do not explicitly explain how graph Laplacian coupling contributes to understanding pattern formations.
- **Rewrite 1:** `What is the mechanism by which graph Laplacian coupling facilitates the analysis of pattern formation in spatially extended systems?`
- **Gold in top-5:** first attempt yes, final yes (MRR 1.00 → 1.00)
- **Answer:** Graph Laplacian coupling contributes to understanding pattern formation by enabling the study of spatial dynamics in discrete models, where it replaces diffusion and allows for the emergence of spatially periodic patterns, similar to those observed in continuous reaction-diffusion systems. This coupling facilitates the analysis of stability and bifurcations, providing insights into the conditions under which patterns can form.
- **Reference:** Graph Laplacian coupling helps model spatial relationships and connectivity between elements within a system. It aids in understanding how local and global interactions contribute to emergent patterns like those observed in animal skin or plant structures.

### `83dda238-c421-4f22-aec5-7c6c83875eb3` (abstractive, text)

- **Question:** What does it mean for an element to be in the lidentity of itself?
- **Attempt 1 grade:** insufficient: The passages discuss the concept of left identity and related sets in semigroup theory, but they do not directly address the meaning of an element being in the 'lidentity of itself'.
- **Rewrite 1:** `What is the definition of an element being in the left identity of itself in semigroup theory?`
- **Gold in top-5:** first attempt yes, final yes (MRR 0.33 → 0.50)
- **Answer:** For an element to be in the lidentity of itself, it means that the element is an idempotent. This is because an element $ e $ is in $ lidentity(e) $ if and only if $ e $ is an idempotent, i.e., $ ee = e $.
- **Reference:** An element \(e\) is in the lidentity of itself if and only if it is an idempotent.

### `86997f53-2801-4007-a0e4-de847455b000` (abstractive, text-table-image)

- **Question:** How does inheritance affect access to member variables in object-oriented programming?
- **Attempt 1 grade:** insufficient: The passages discuss inheritance and nested classes in object-oriented programming but do not directly explain how inheritance affects access to member variables.
- **Rewrite 1:** `How does inheritance influence access control and visibility of member variables in object-oriented programming languages?`
- **Gold in top-5:** first attempt yes, final yes (MRR 1.00 → 1.00)
- **Answer:** In object-oriented programming, inheritance allows derived classes to access members of the base class. Protected members of the base class are accessible to derived classes, while private members are not. Public members are accessible to all.
- **Reference:** Inheritance allows a derived class to inherit properties and behaviors from a base class. Member variables with protected access in the base class can be accessed directly by derived classes but remain inaccessible outside these classes unless accessed through public methods or functions provided by those classes.

### `c78b0dd7-2e8e-4f61-a9fb-4e49af5c9d80` (abstractive, text-image)

- **Question:** What role does wind direction play in sailboat maneuvering strategies?
- **Attempt 1 grade:** insufficient: The passages discuss how wind direction affects sailboat maneuvering by influencing tacking strategies and the boat's motion, but they do not explicitly state the role of wind direction in maneuvering strategies.
- **Rewrite 1:** `What is the impact of wind direction on tacking strategies and sailboat maneuvering efficiency?`
- **Gold in top-5:** first attempt yes, final yes (MRR 1.00 → 1.00)
- **Answer:** Wind direction plays a critical role in sailboat maneuvering strategies as it influences the boat's ability to tack or jibe, affecting the time required to reach the target. The paper assumes wind direction follows a Brownian motion, and the boat's reference frame is aligned with the wind direction to simplify the equations of motion and derive optimal strategies. Fluctuations in wind direction necessitate changes in the boat's heading, leading to tacking or jibing maneuvers that impact the overall travel time.
- **Reference:** Wind direction affects yacht velocity and dictates maneuvers like tacking and jibing, which are used to switch between starboard and port tack efficiently.

## Correct abstentions (5 shown)

### `02ec0c1e-a71b-4536-abaa-73fbd56a541f` (grader abstained after 2 retries)

- **Question:** What happens when all consumers are allowed to migrate with respect to inter-regional trade integration?
- **Query 1:** `What happens when all consumers are allowed to migrate with respect to inter-regional trade integration?`
- **Query 2:** `What are the economic implications of free consumer migration on inter-regional trade integration and labor market dynamics?`
- **Query 3:** `What are the effects of full consumer migration freedom on inter-regional trade integration and labor market equilibrium?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages discuss market integration, price contagion, and trade networks but do not specifically address the scenario where all consumers are allowed to migrate and its impact on inter-regional trade integration.

### `08c9a683-df57-4491-8056-5399b34a304d` (grader abstained after 2 retries)

- **Question:** Is the function for estimating causal effects dependent on both alpha and beta transposed with X?
- **Query 1:** `Is the function for estimating causal effects dependent on both alpha and beta transposed with X?`
- **Query 2:** `Is the function for estimating causal effects in linear regression dependent on the transposition of alpha and beta with the covariate matrix X?`
- **Query 3:** `Is the function for estimating causal effects in linear regression dependent on the transposition of the coefficient vectors alpha and beta with the covariate matrix X?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages do not mention anything about the function for estimating causal effects depending on alpha and beta transposed with X.

### `0949e078-a396-4840-801b-b0bc8ef905d1` (grader abstained after 2 retries)

- **Question:** How do consumer preferences affect regional utility in economic models?
- **Query 1:** `How do consumer preferences affect regional utility in economic models?`
- **Query 2:** `How do consumer preference parameters influence regional utility functions in discrete choice economic models?`
- **Query 3:** `How do consumer preference heterogeneity and utility maximization principles influence regional utility aggregation in spatial economic models?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages discuss consumer preferences and their influence on CSA participation in Japan, but they do not directly address how consumer preferences affect regional utility in economic models.

### `09a82aff-63f2-4955-99b2-5e0255226bba` (grader abstained after 2 retries)

- **Question:** At what collision energy does the cross-section stabilize around 100 Å² for all transitions?
- **Query 1:** `At what collision energy does the cross-section stabilize around 100 Å² for all transitions?`
- **Query 2:** `What collision energy corresponds to the stabilization of the cross-section at approximately 100 Å² across all transition channels?`
- **Query 3:** `What is the collision energy at which the cross-section stabilizes to approximately 100 Å² across all transition channels in ion-molecule reactions?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages do not mention anything about collision energy or cross-section stabilization around 100 Å².

### `0aa05517-ed7e-432f-b97c-162f97e7b803` (grader abstained after 2 retries)

- **Question:** What are typical latent dimensions used for different components in numerical experiments involving PDEs?
- **Query 1:** `What are typical latent dimensions used for different components in numerical experiments involving PDEs?`
- **Query 2:** `What are common latent space dimensions employed in different components of numerical methods for solving partial differential equations?`
- **Query 3:** `What are typical latent dimension sizes utilized in different components of neural operators for numerical solutions of partial differential equations?`
- **Response:** INSUFFICIENT_EVIDENCE: The passages discuss neural operators and their applications in solving PDEs and structural dynamics, but they do not mention latent dimensions used in numerical experiments involving PDEs.
