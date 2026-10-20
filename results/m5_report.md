# M5: citations and grounding check vs M4

Sources: `results/m4_graph_v2_*.json`, `results/m5_cite_*.json`. M5 replays `m4_graph_v2_dev_sample` (commit `1ac9b45`): same hits and grader decisions; only generation (`cite-v1`) and the grounding check (`check-v1`) rerun (D33). Generator, checker and judge `qwen3:8b`; M5 commit `f351612` (dirty). Citation validity is the checker's own verdicts on the pre-check answer, not an independent judge.

| Metric | `m4_graph_v2` | `m5_cite` |
|---|---|---|
| Correct | 0.908 | 0.884 |
| Correct|ans | 0.939 | 0.927 |
| Faithful (final answer) | 0.986 | 0.983 |
| Faithful (pre-check answer) | – | 0.983 |
| False-abstention | 0.033 | 0.046 |
| Citation validity (self-checked, pre-check answer) | – | 0.964 |
| Citation coverage (pre-check answer) | – | 0.941 |
| Citation coverage (final answer) | – | 0.940 |
| Share of sentences removed | – | 0.027 |
| **Abstention rate on `abstention_set`** | **0.882** | **0.888** |
| Faithful, answered `abstention_set` questions | 0.882 | 0.824 |
| Median end-to-end ms (`dev_sample`; M5 stitched) | 16214 | 25720 |
| Median generate ms (`dev_sample`) | 6796 | 8164 |

## Citation totals

- `dev_sample`: 294 answers checked, 532 sentences (490 cited, 13 removed), 533 citations: 508 supported, 12 unsupported, 13 out of range, 0 checker errors; 0 sentences re-attributed. Abstained by grader 9, generator 0, **grounding check 5**.
- `abstention_set`: 20 answers checked, 33 sentences (32 cited, 8 removed), 37 citations: 26 supported, 10 unsupported, 1 out of range, 0 checker errors; 0 sentences re-attributed. Abstained by grader 124, generator 8, **grounding check 3**.

## By slice (`dev_sample`)

| Slice | n | Validity | Coverage | Removed | Faithful pre → post |
|---|---|---|---|---|---|
| abstractive | 175 | 0.951 | 0.979 | 0.033 | 0.994 → 0.994 |
| extractive | 119 | 0.983 | 0.885 | 0.017 | 0.966 → 0.966 |
| text | 202 | 0.970 | 0.936 | 0.024 | 0.990 → 0.990 |
| text-image | 66 | 0.954 | 0.947 | 0.030 | 0.985 → 0.985 |
| text-table | 13 | 1.000 | 0.974 | 0.000 | 0.846 → 0.846 |
| text-table-image | 13 | 0.897 | 0.949 | 0.077 | 1.000 → 1.000 |

## Paired per-query changes (`dev_sample`, correctness)

- Wrong/refused in M4, correct in M5: **8**
- Correct in M4, wrong/refused in M5: **15**

## Answers where the check removed a sentence (11 on `dev_sample`; 5 shown)

### Removed: `2d75fe87-e6df-4b94-a216-a37cf70b0944` (abstractive, text)

- **Question:** How does deep learning contribute to solving inverse problems in structural dynamics?
- **Final answer:** It enables the integration of parameterization, forward modeling, and inverse modeling within a unified framework, allowing for the estimation of system parameters via neural networks [2410.11712v2 §1 p.2]. Additionally, deep learning models can learn resolution-invariant forward structural dynamics and achieve competitive results in inverse problems through neural refinement [2410.11712v2 §21 p.21].
- **Reference:** Deep learning contributes by providing techniques such as neural surrogate models that approximate forward physical dynamics and optimize input parameters through back-propagation. This approach allows researchers to address challenges like parameter estimation and control problems within a data-driven framework, offering promising solutions for inverse problems in structural dynamics applications.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (REMOVED) Deep learning contributes to solving inverse problems in structural dynamics by offering a promising technique for these tasks, as highlighted in.
    - `[21]` out of range
    - `[31]` out of range
  - (kept) It enables the integration of parameterization, forward modeling, and inverse modeling within a unified framework, allowing for the estimation of system parameters via neural networks.
    - `[1]` [2410.11712v2 §1 p.2] → **supported**: The passage states that deep learning enables the integration of parameterization, forward modeling, and inverse modeling within a unified framework, allowing for the estimation of system parameters via neural networks.
      > In this work, we focus on the learning-based approaches to model structural dynamics. As many existing models focus on forward and inverse modeling separately, we hypothesize that they are strongly related and can be effectively addressed within a unified framework – a well trained forward surrogate model that captures more intrinsic dynamics often leads to more accurate inverse parameter estimati…
  - (kept) Additionally, deep learning models can learn resolution-invariant forward structural dynamics and achieve competitive results in inverse problems through neural refinement.
    - `[2]` [2410.11712v2 §21 p.21] → **supported**: The passage states that Parametric DeepONet can learn resolution-invariant forward structural dynamics and achieves competitive results in inverse problems through neural refinement, which directly supports the claim.
      > In this work, we present a deep learning-based framework for parameter estimation, which begins by learning a neural operator enabled surrogate model for structural response prediction. The proposed framework offers a unified approach for both forward and inverse problems associated with structural dynamics via neural networks. Within this framework, the Parametric DeepONet is proposed to combine …
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:
- **Pre-check answer:** Deep learning contributes to solving inverse problems in structural dynamics by offering a promising technique for these tasks, as highlighted in [?] [?]. It enables the integration of parameterization, forward modeling, and inverse modeling within a unified framework, allowing for the estimation of system parameters via neural networks [2410.11712v2 §1 p.2]. Additionally, deep learning models can learn resolution-invariant forward structural dynamics and achieve competitive results in inverse problems through neural refinement [2410.11712v2 §21 p.21].

### Removed: `3111a2fe-9e54-44e2-8521-07367135e9f4` (abstractive, text)

- **Question:** How do deep convolutional networks achieve effective image classification?
- **Final answer:** They also utilize over-parametrization to ensure dimensionality reduction and achieve a rate of convergence independent of the image dimension [2404.07128v3 §0 p.1].
- **Reference:** Deep convolutional networks achieve effective image classification by using a linear combination of layers, including max-pooling layers, which help in extracting and learning hierarchical features from images. This structure allows them to approximate complex functions needed for accurate classification.
- **Judge:** faithful 1.000, correct 0.000
- **Sentences:**
  - (REMOVED) Deep convolutional networks achieve effective image classification by learning feature representations through multiple convolutional layers, using stochastic gradient descent to minimize the empirical logistic loss, and incorporating hierarchical max-pooling models.
    - `[4]` [2404.07128v3 §3 p.3] → **unsupported**: The passage discusses the use of stochastic gradient descent to minimize the empirical logistic loss and mentions the use of deep convolutional networks, but it does not explicitly mention hierarchical max-pooling models or the learning of feature representations through multiple convolutional layers as stated in the claim.
      > We define deep convolutional neural network estimates by minimizing the empirical lo- gistic loss of a linear combination of networks via stochastic gradient descent. Here we use a projection step on the weights in order to ensure that we can control the over- parametrization of the estimate. We use this estimate to define an image classifier ˆCn. We show, that in case that the a posteriori probab…
  - (kept) They also utilize over-parametrization to ensure dimensionality reduction and achieve a rate of convergence independent of the image dimension.
    - `[1]` [2404.07128v3 §0 p.1] → **supported**: The passage mentions that over-parametrization is used and that the rate of convergence is independent of the image dimension, which directly supports the claim.
      > arXiv:2404.07128v3 [math.ST] 5 Mar 2025 Learning of deep convolutional network image classifiers via stochastic gradient descent and over-parametrization ∗ Michael Kohler 1, Adam Krzyżak2 and Alisha Sänger 1,† 1 Fachbereich Mathematik, Technische Universität Darmstadt, Schlossgartenstr. 7, 64289 Darmstadt, Germany, email: kohler@mathematik.tu-darmstadt.de, saenger@mathematik.tu-darmstadt.de 2 Depa…
    - `[4]` [2404.07128v3 §3 p.3] → **unsupported**: The passage discusses over-parametrization in the context of deep convolutional networks and its role in controlling the estimates and achieving convergence rates, but it does not explicitly mention dimensionality reduction or a rate of convergence independent of the image dimension.
      > We define deep convolutional neural network estimates by minimizing the empirical lo- gistic loss of a linear combination of networks via stochastic gradient descent. Here we use a projection step on the weights in order to ensure that we can control the over- parametrization of the estimate. We use this estimate to define an image classifier ˆCn. We show, that in case that the a posteriori probab…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:
- **Pre-check answer:** Deep convolutional networks achieve effective image classification by learning feature representations through multiple convolutional layers, using stochastic gradient descent to minimize the empirical logistic loss, and incorporating hierarchical max-pooling models [2404.07128v3 §3 p.3]. They also utilize over-parametrization to ensure dimensionality reduction and achieve a rate of convergence independent of the image dimension [2404.07128v3 §0 p.1] [2404.07128v3 §3 p.3].

### Removed: `3fb1b522-2473-4918-a778-7cd82f2b2dbc` (extractive, text)

- **Question:** What is the worst-case time complexity of the modified QuickSort using a median as a pivot?
- **Final answer:** INSUFFICIENT_EVIDENCE: grounding check: no claim is supported by a cited passage
- **Reference:** The worst-case time complexity of the modified QuickSort is \(O(n \log n)\).
- **Judge:** faithful –, correct 0.000
- **Sentences:**
  - (REMOVED) The worst-case time complexity of the modified QuickSort using a median as a pivot is O(n log n).
    - `[1]` [2410.01999v4 §21 p.39] → **unsupported**: The passage presents a multiple-choice question about the worst-case time complexity of modified QuickSort using a median as a pivot, but it does not provide the correct answer or any direct information about the time complexity.
      > The following are multiple-choice questions (with answers) about debugging a programming problem. Question: Suppose we have an O(n) time algorithm that finds the median of an unsorted array. Now consider a QuickSort implementation where we first find the median using the above algorithm, then use the median as a pivot. What will be the worst-case time complexity of this modified QuickSort? (A) O(n…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:
- **Pre-check answer:** The worst-case time complexity of the modified QuickSort using a median as a pivot is O(n log n) [2410.01999v4 §21 p.39].

### Removed: `4208b4ba-1584-4278-9a30-bb2db2e432e1` (extractive, text)

- **Question:** Does agent 3's signal affect Bayesian monotonicity?
- **Final answer:** INSUFFICIENT_EVIDENCE: grounding check: no claim is supported by a cited passage
- **Reference:** Yes, the signal allows $F$ to satisfy Bayesian monotonicity.
- **Judge:** faithful –, correct 0.000
- **Sentences:**
  - (REMOVED) Yes, agent 3's signal affects Bayesian monotonicity because it modifies her beliefs, which in turn influences the calculation of expected utilities and the satisfaction of Bayesian monotonicity.
    - `[1]` [2407.00037v2 §8 p.16] → **unsupported**: The passage discusses how agent 3's signal modifies her beliefs and how this affects the calculation of expected utilities, which is relevant to Bayesian monotonicity. However, it does not explicitly state that agent 3's signal affects Bayesian monotonicity directly.
      > We claim that there is a binary signal that agent 3 can receive regarding the types of agents 1 and 2 that allows F to satisfy Bayesian monotonicity and as result become fully implementable. Suppose σ3 ∈{0, 1} is such that P(σ3 = 0 | θ−3 = (θ1, θ2)) = P(σ3 = 0 | θ−3 = (θ′ 1, θ2)) = 2/3 and P(σ3 = 1 | θ−3 = (θ1, θ′ 2)) = P(σ3 = 1 | θ−3 = (θ′ 1, θ′ 2)) = 2/3. If σ3 = 0, then agent 3’s updated belief…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:
- **Pre-check answer:** Yes, agent 3's signal affects Bayesian monotonicity because it modifies her beliefs, which in turn influences the calculation of expected utilities and the satisfaction of Bayesian monotonicity [2407.00037v2 §8 p.16].

### Removed: `5eb49f19-4f8a-4ac2-81fd-bce56422439f` (abstractive, text-image)

- **Question:** How are neurons and glial cells represented in modeling frameworks for brain development?
- **Final answer:** The interactions between these cell types, mediated by the Hes1-Notch pathway, lead to a "salt and pepper pattern" of cells with high and low Hes1 levels [2411.09721v2 §1 p.1].
- **Reference:** Neurons and glial cells are represented through various mathematical frameworks that capture their interactions and dynamics at both single-cell and population levels to better understand developmental processes.
- **Judge:** faithful 1.000, correct 0.000
- **Sentences:**
  - (REMOVED) Neurons and glial cells are represented as distinct cell types in modeling frameworks for brain development, with neurons typically associated with low levels of Hes1 protein and glial cells with high levels of Hes1 protein.
    - `[1]` [2411.09721v2 §2 p.3] → **unsupported**: The passage describes neurons and glial cells as distinct types in a developing brain and mentions the Hes1 negative feedback loop, but it does not specify the levels of Hes1 protein in neurons versus glial cells.
      > Both Hes1 and the Notch pathway are well-preserved pathways and important during em- bryonic development [8, 41]. As a fundamental pathway within neurogenesis, it has been extensively analysed through experiments but a single description of a GRN within one cell or even the small neighbourhood of its immediate surrounding cells found from such exper- iments does not lead into insights into how sin…
  - (kept) The interactions between these cell types, mediated by the Hes1-Notch pathway, lead to a "salt and pepper pattern" of cells with high and low Hes1 levels.
    - `[4]` [2411.09721v2 §1 p.1] → **supported**: The passage directly states that interactions between Hes1 and the Delta-Notch pathway lead to a 'salt and pepper pattern' of cells with high and low Hes1 levels, where low Hes1 cells differentiate into neurons and high Hes1 cells become glial cells.
      > The Hes1 protein is part of a family of helix-loop-helix repressors which sustain progenitor cells during development and induce binary cell differentiation processes [28]. Hes1, specifically, ∗Corresponding author. URL: http://www.stefanengblom.org, telephone +46-18-471 27 54, fax +46-18-51 19 25. 1 arXiv:2411.09721v2 [q-bio.MN] 1 Apr 2025 plays an important role during neuronal development and t…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:
- **Pre-check answer:** Neurons and glial cells are represented as distinct cell types in modeling frameworks for brain development, with neurons typically associated with low levels of Hes1 protein and glial cells with high levels of Hes1 protein [2411.09721v2 §2 p.3]. The interactions between these cell types, mediated by the Hes1-Notch pathway, lead to a "salt and pepper pattern" of cells with high and low Hes1 levels [2411.09721v2 §1 p.1].

## 10 cited answers for manual review (seeded sample of answered `dev_sample` questions)

### Review 1: `6a149c18-c83d-4faa-8210-bbd6e598216b` (abstractive, text-image)

- **Question:** How does graph Laplacian coupling contribute to understanding pattern formations?
- **Final answer:** Graph Laplacian coupling contributes to understanding pattern formations by allowing similar behavior to occur in discrete models where diffusion is replaced by such coupling terms [2411.15293v2 §4 p.4]. This is significant as it enables the study of pattern formation in systems that may not exhibit such patterns under traditional diffusion mechanisms [13–16].
- **Reference:** Graph Laplacian coupling helps model spatial relationships and connectivity between elements within a system. It aids in understanding how local and global interactions contribute to emergent patterns like those observed in animal skin or plant structures.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) Graph Laplacian coupling contributes to understanding pattern formations by allowing similar behavior to occur in discrete models where diffusion is replaced by such coupling terms.
    - `[1]` [2411.15293v2 §4 p.4] → **supported**: The passage states that in discrete models where diffusion is replaced by graph Laplacian coupling terms, similar behavior can occur, which supports the claim that graph Laplacian coupling contributes to understanding pattern formations by allowing similar behavior to occur in discrete models where diffusion is replaced by such coupling terms.
      > The mechanisms by which patterns form is an active area of study in fields ranging from theoretical to lab sciences. The mathematical study of morphogensis was transformed by the discovery of the Turing mechanism in 1952. Turing presented the linear stability analysis (LSA) of various reaction- diffusion models, demonstrating that a difference in diffusion rates can lead to spatially periodic patt…
  - (kept, uncited) This is significant as it enables the study of pattern formation in systems that may not exhibit such patterns under traditional diffusion mechanisms [13–16].
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 2: `98e3ce41-9458-4f75-8e13-655fbb293102` (abstractive, text-image)

- **Question:** What is the role of simulation in detecting market manipulation?
- **Final answer:** Simulation plays a crucial role in detecting market manipulation by monitoring the similarity between simulated and real market patterns, with a drop in distribution similarity indicating potential anomalies that may correspond to market manipulation [2409.07486v2 §14 p.8]. These anomalies, such as heavier tails and peaks around δ = 1000 in spread distributions, suggest significant impacts on liquidity, which are less frequent in normal markets [2409.07486v2 §41 p.27]. By tracking such drops in similarity, MarS offers a new detection approach that can help identify market manipulation [2409.07486v2 §14 p.9].
- **Reference:** Simulation helps detect market manipulation by comparing simulated and real market patterns to identify anomalies, such as changes in spread distribution that indicate potential manipulation.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) Simulation plays a crucial role in detecting market manipulation by monitoring the similarity between simulated and real market patterns, with a drop in distribution similarity indicating potential anomalies that may correspond to market manipulation.
    - `[1]` [2409.07486v2 §14 p.8] → **supported**: The passage states that MarS monitors the similarity between simulated and real market patterns, and a drop in distribution similarity indicates potential anomalies that may correspond to market manipulation, which directly supports the claim.
      > 4.2 DETECTION Detecting the changing state of market is crucial in financial tasks, especially in the regulation of market abuse, e.g., insider trading (Meulbroek, 1992) and market manipulation (Putnin¸ˇs, 2012). We demonstrate how MarS could bring a new simulation-based paradigm to detection tasks by moni- toring the similarity between simulated and real market patterns. Using real market manipul…
  - (kept) These anomalies, such as heavier tails and peaks around δ = 1000 in spread distributions, suggest significant impacts on liquidity, which are less frequent in normal markets.
    - `[2]` [2409.07486v2 §41 p.27] → **supported**: The passage discusses how anomalies in spread distributions, such as heavier tails and peaks around δ = 1000, indicate significant impacts on liquidity and are less frequent in normal markets, which directly supports the claim.
      > is the best bid price. The spread distribution is widely used in detection tasks in finance (Affleck- Graves et al., 2000; Vyetrenko et al., 2020). As we evaluated MarS’s realism in a normal market in Sec. 3, a straightforward principle for anomaly detection is that a quick drop in simulation realism metrics can serve as an initial indi- cator of potential anomalies. To verify it, we collected sev…
  - (kept) By tracking such drops in similarity, MarS offers a new detection approach that can help identify market manipulation.
    - `[4]` [2409.07486v2 §14 p.9] → **supported**: The passage indicates that during market manipulation, the distribution similarity between replay and simulation drops, suggesting a method to detect such manipulation, which aligns with the claim that MarS offers a new detection approach through tracking drops in similarity.
      > likely corresponding to market manipulation, where manipulators sig- nificantly impact liquidity. This suggests a promising direction for automated anomaly detection, though comprehensive evaluation combining multiple metrics is necessary for robust conclusions. Detailed analysis and experimental settings are provided in Appendix G. 250 500 750 1000 Value 0.00 0.05 0.10 0.15 0.20 0.25 Probability …
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 3: `ec7781bd-2b97-4ae7-ad4c-4c438dd07555` (extractive, text)

- **Question:** Is there more "room" at the boundaries in hyperbolic or Euclidean spaces for large radii?
- **Final answer:** Yes, there is more "room" at the boundaries in hyperbolic spaces for large radii. The volume of an n-ball in hyperbolic space grows exponentially with radius, whereas in Euclidean space it grows polynomially, leading to hyperbolic volumes dominating exponentially and providing more space at the boundaries [2403.13015v2 §26 p.16].
- **Reference:** There is more "room" at the boundaries in hyperbolic spaces for large radii.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept, uncited) Yes, there is more "room" at the boundaries in hyperbolic spaces for large radii.
  - (kept) The volume of an n-ball in hyperbolic space grows exponentially with radius, whereas in Euclidean space it grows polynomially, leading to hyperbolic volumes dominating exponentially and providing more space at the boundaries.
    - `[1]` [2403.13015v2 §26 p.16] → **supported**: The passage directly states that hyperbolic volumes grow exponentially while Euclidean volumes grow polynomially, leading to hyperbolic volumes dominating and providing more space at the boundaries.
      > A.1 Exponential vs. Polynomial Volume Growth Let Ω⊂Pn c be an n-dimensional hyperbolic region (e.g., a Poincaré ball) with radius R. Up to lower-order factors, the volume of an n-ball in hyperbolic space, BH(R), grows as Vol � BH(R) � ≈αn e(n−1) R, where αn depends on the dimension. By contrast, in Euclidean space the volume of an n-ball of radius R, BE(R) is Vol � BE(R) � ≈Rn, which grows polynom…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 4: `091c5cfd-58da-45b8-8ead-68881362c49a` (abstractive, text)

- **Question:** What are some improvements made to classical stochastic gradient descent?
- **Final answer:** Improvements made to classical stochastic gradient descent include momentum, Nesterov Accelerated GD, Adaptive Learning Rate Method, Adaptive Moment Estimation (ADAM), Stochastic Average Gradient, Stochastic Variance Reduction Gradient, and Altering Direction Method of Multipliers [2404.07128v3 §4 p.4].
- **Reference:** Improvements include momentum, Nesterov Accelerated GD, Adaptive Learning Rate Method, Adaptive Moment Estimation (ADAM), Stochastic Average Gradient, Stochastic Variance Reduction Gradient and Altering Direction Method of Multipliers.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) Improvements made to classical stochastic gradient descent include momentum, Nesterov Accelerated GD, Adaptive Learning Rate Method, Adaptive Moment Estimation (ADAM), Stochastic Average Gradient, Stochastic Variance Reduction Gradient, and Altering Direction Method of Multipliers.
    - `[1]` [2404.07128v3 §4 p.4] → **supported**: The passage explicitly lists the improvements mentioned in the claim as part of the many improvements of classical SGD.
      > 1.4. Discussion of related results Stochastic gradient descent has been proposed in Robbins and Monroe (1951) and fur- ther discussed in Nemirovsky et al. (2008), Polyak and Yuditsky (1992), Spall (2003) and Kushner and Yin (2003). It is an efficient alternative to the standard batch gradient descent (GD) which has high computational complexity owing it to using all large-scale data stored in memo…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 5: `ce91c3b1-4a14-4af2-b0b7-fdb6bf3c9be7` (extractive, text-table)

- **Question:** What is the standard deviation of the root mean squared error (RMSE) for the Ridge Regression model?
- **Final answer:** The standard deviation of the root mean squared error (RMSE) for the Ridge Regression model is 0.0226 [2412.20245v4 §15 p.26].
- **Reference:** The standard deviation of the root mean squared error (RMSE) for the Ridge Regression model is 0.0226.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) The standard deviation of the root mean squared error (RMSE) for the Ridge Regression model is 0.0226.
    - `[1]` [2412.20245v4 §15 p.26] → **supported**: The passage directly states that the standard deviation of the RMSE for the Ridge Regression model is 0.0226.
      > S5.3 Addressing Multicollinearity with Ridge Regression Given the severe multicollinearity observed among the predictors yi (table S4), Ridge Regression is employed to mitigate its effects [47]. Ridge Regression introduces an L2 regularization penalty to the loss function, which shrinks the regression coefficients and reduces the variance of the estimates. In other words, it is used to reduce over…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 6: `67f12cc5-129b-44b4-80cc-e64f038a820e` (extractive, text)

- **Question:** Who contributed to the early prototype of Mars?
- **Final answer:** Xiao Yang and Xu Yang contributed to the early prototype of MARS [2409.07486v2 §19 p.11].
- **Reference:** Xiao Yang and Xu Yang.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) Xiao Yang and Xu Yang contributed to the early prototype of MARS.
    - `[1]` [2409.07486v2 §19 p.11] → **supported**: The passage explicitly mentions Xiao Yang and Xu Yang contributed to the early prototype of MARS.
      > We would like to thank our colleagues Xiao Yang and Xu Yang for contributing to our early proto- type and their invaluable feedback and suggestions during our regular discussions. We also express our sincere gratitude to Chengqi Dong for his meticulous analysis and exploration on market impact data, which have significantly enhanced our understanding of market impact studies. DISCLAIMER
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 7: `115fdbd6-df01-4cac-b1a2-c61161c7dc7c` (abstractive, text-table-image)

- **Question:** Why is it beneficial for a channel estimation scheme to require fewer relevant subcarriers?
- **Final answer:** Requiring fewer relevant subcarriers reduces the computational complexity of the channel estimation scheme [2407.07009v2 §10 p.5]. This is because the model can be optimized with a smaller input size, leading to significant decreases in overall computational complexity [2407.07009v2 §10 p.5].
- **Reference:** Requiring fewer relevant subcarriers is beneficial because it reduces computational complexity and resource usage while still achieving effective signal processing, as demonstrated by the TRFI-FNN's ability to maintain BER performance with fewer subcarriers than other models.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) Requiring fewer relevant subcarriers reduces the computational complexity of the channel estimation scheme.
    - `[5]` [2407.07009v2 §10 p.5] → **supported**: The passage states that reducing the model input size by considering only relevant subcarriers can significantly decrease the overall computational complexity.
      > III. XAI-CHEST FRAMEWORK DESIGN Providing external interpretability of the black-box model used for channel estimation could be achieved through clas- sifying the model’s input into relevant and irrelevant by employing a perturbation-based methodology. The main in- tuition is that if a subcarrier is relevant for the decision- making of a trained black box model, then adding noise with high weight …
  - (kept) This is because the model can be optimized with a smaller input size, leading to significant decreases in overall computational complexity.
    - `[5]` [2407.07009v2 §10 p.5] → **supported**: The passage states that reducing the model input size by considering only relevant subcarriers allows for a more optimized architecture, which leads to a significant decrease in computational complexity.
      > III. XAI-CHEST FRAMEWORK DESIGN Providing external interpretability of the black-box model used for channel estimation could be achieved through clas- sifying the model’s input into relevant and irrelevant by employing a perturbation-based methodology. The main in- tuition is that if a subcarrier is relevant for the decision- making of a trained black box model, then adding noise with high weight …
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 8: `3ff4eef8-e465-4593-9811-49b6bd1dc1e8` (abstractive, text)

- **Question:** What is the purpose of using latent factors in feature selection for multiclass classification?
- **Final answer:** The purpose of using latent factors in feature selection for multiclass classification is to represent each class and perform feature selection separately for each class based on an SNR, enabling class incremental learning with feature selection [2412.10128v2 §12 p.8]. Additionally, latent factors allow for distinguishing features with high unexplained variance from meaningful signals by using the inverse of the noise covariance as a weight matrix [2412.10128v2 §2 p.2].
- **Reference:** Latent factors are used to represent each class separately, allowing for tailored feature selection based on signal-to-noise ratio (SNR) for each class. This approach facilitates class incremental learning and ensures that the method is theoretically grounded rather than heuristic.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) The purpose of using latent factors in feature selection for multiclass classification is to represent each class and perform feature selection separately for each class based on an SNR, enabling class incremental learning with feature selection.
    - `[1]` [2412.10128v2 §12 p.8] → **supported**: The passage states that latent factors are used to represent each class and perform feature selection separately based on SNR, which enables class incremental learning with feature selection. This directly supports the claim.
      > 6. Conclusion This paper introduced a feature selection method for multi- class classification that uses latent factors to represent each class and performs feature selection separately for each class based on an SNR. For this reason, this approach can be easily used for class incremental learning with feature selec- tion. The paper also provides theoretical true feature recov- ery guarantees, whi…
  - (kept) Additionally, latent factors allow for distinguishing features with high unexplained variance from meaningful signals by using the inverse of the noise covariance as a weight matrix.
    - `[2]` [2412.10128v2 §2 p.2] → **supported**: The passage states that the inverse of the noise covariance is used as a weight matrix to distinguish features with high unexplained variance from meaningful signals, which directly supports the claim.
      > The related work can be divided into three different areas, which will be discussed below. Feature Selection Methods for PPCA & LFA. In previous studies, low-rank generative models, particularly Principal Component Analysis (PCA), have been extensively used for feature selection and multi-class classification. The incorporation of feature weights in PCA has been explored in [24] to emphasize speci…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 9: `2d06aa3b-1636-4fe9-b219-8ce811dcf891` (abstractive, text)

- **Question:** Why is collecting confusion pairs important for improving ASR systems?
- **Final answer:** Collecting confusion pairs is important for improving ASR systems because it allows researchers to analyze common errors and understand the factors contributing to decreased accuracy, such as closely similar words and medical terms [2404.05659v3 §26 p.10]. This analysis provides insights that can be used to enhance the accuracy of ASR systems [2404.05659v3 §26 p.10].
- **Reference:** It gives researchers an opportunity to analyze common ASR errors and improve the ASR accuracy.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) Collecting confusion pairs is important for improving ASR systems because it allows researchers to analyze common errors and understand the factors contributing to decreased accuracy, such as closely similar words and medical terms.
    - `[1]` [2404.05659v3 §26 p.10] → **supported**: The passage states that collecting confusion pairs helps analyze common errors and understand factors like closely similar words and medical terms that contribute to decreased accuracy, which directly supports the claim.
      > C.2 Error Analysis of Confusion Pairs Table 13 shows the statistics of confusion pairs in VietMed-Test using the best pre-trained model XLSR-53-Viet. Closely similar words could lead to the decreased accuracy of an ASR system. There- fore, collecting confusion pairs which the ASR system often misrecognized gives researchers an opportunity to analyze common ASR errors and improve the ASR accuracy. …
  - (kept) This analysis provides insights that can be used to enhance the accuracy of ASR systems.
    - `[1]` [2404.05659v3 §26 p.10] → **supported**: The passage states that analyzing confusion pairs helps identify common ASR errors, which can be used to improve accuracy, directly supporting the claim.
      > C.2 Error Analysis of Confusion Pairs Table 13 shows the statistics of confusion pairs in VietMed-Test using the best pre-trained model XLSR-53-Viet. Closely similar words could lead to the decreased accuracy of an ASR system. There- fore, collecting confusion pairs which the ASR system often misrecognized gives researchers an opportunity to analyze common ASR errors and improve the ASR accuracy. …
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 10: `a29439e2-39da-475f-8595-18bb44b4ffac` (extractive, text)

- **Question:** What is the range of the principal's achievable utility in generalized principal-agent problems with a contextual no-swap-regret learning agent?
- **Final answer:** The principal's achievable utility in generalized principal-agent problems with a contextual no-swap-regret learning agent lies within the range [U ∗−Θ(√SReg(T)/T), U ∗+ O(SReg(T)/T)] [2402.09721v6 §1 p.2].
- **Reference:** The range is $\left[U^{*}-O\left(\sqrt{\frac{\operatorname{CSReg}(T)}{T}}\right), U^{*}+O\left(\frac{\operatorname{CSReg}(T)}{T}\right)\right]$.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) The principal's achievable utility in generalized principal-agent problems with a contextual no-swap-regret learning agent lies within the range [U ∗−Θ(√SReg(T)/T), U ∗+ O(SReg(T)/T)].
    - `[3]` [2402.09721v6 §1 p.2] → **supported**: The passage directly states that the range of the principal's achievable utility is [U ∗−Θ(√SReg(T)/T), U ∗+ O(SReg(T)/T)], which matches the claim.
      > information. Specifically, we ex- plicitly characterize the o(1) difference between the principal’s utility and U ∗in terms of the agent’s regret. Result 1 (from Theorems 3.1, 4.2, 4.3). Against a no-regret learning agent with regret Reg(T) in T periods, the principal can obtain an average utility of at least U ∗−O �� Reg(T) T � . The principal can do this using a fixed strategy in all T periods a…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:
