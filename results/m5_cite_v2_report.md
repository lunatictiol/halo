# M5: citations and grounding check vs M4

Sources: `results/m4_graph_v2_*.json`, `results/m5_cite_v2_*.json`. M5 replays `m4_graph_v2_dev_sample` (commit `1ac9b45`): same hits and grader decisions; only generation (`cite-v2`) and the grounding check (`check-v1`) rerun (D33). Generator, checker and judge `qwen3:8b`; M5 commit `ea97807`. Citation validity is the checker's own verdicts on the pre-check answer, not an independent judge.

| Metric | `m4_graph_v2` | `m5_cite` | `m5_cite_v2` |
|---|---|---|---|
| Correct | 0.908 | 0.884 | 0.894 |
| Correct|ans | 0.939 | 0.927 | 0.928 |
| Faithful (final answer) | 0.986 | 0.983 | 0.980 |
| Faithful (pre-check answer) | – | 0.983 | 0.976 |
| False-abstention | 0.033 | 0.046 | 0.036 |
| Citation validity (self-checked, pre-check answer) | – | 0.964 | 0.971 |
| Citation coverage (pre-check answer) | – | 0.941 | 0.927 |
| Citation coverage (final answer) | – | 0.940 | 0.929 |
| Share of sentences removed | – | 0.027 | 0.005 |
| **Abstention rate on `abstention_set`** | **0.882** | **0.888** | **0.868** |
| Faithful, answered `abstention_set` questions | 0.882 | 0.824 | 0.900 |
| Median end-to-end ms (`dev_sample`; M5 stitched) | 16214 | 25720 | 24922 |
| Median generate ms (`dev_sample`) | 6796 | 8164 | 7994 |

## Citation totals

- `dev_sample`: 294 answers checked, 538 sentences (485 cited, 2 removed), 510 citations: 497 supported, 13 unsupported, 0 out of range, 0 checker errors; 6 sentences re-attributed. Abstained by grader 9, generator 0, **grounding check 2**.
- `abstention_set`: 22 answers checked, 32 sentences (30 cited, 2 removed), 34 citations: 29 supported, 5 unsupported, 0 out of range, 0 checker errors; 1 sentences re-attributed. Abstained by grader 124, generator 6, **grounding check 2**.

## By slice (`dev_sample`)

| Slice | n | Validity | Coverage | Removed | Faithful pre → post |
|---|---|---|---|---|---|
| abstractive | 175 | 0.968 | 0.972 | 0.003 | 0.983 → 0.989 |
| extractive | 119 | 0.975 | 0.861 | 0.008 | 0.966 → 0.966 |
| text | 202 | 0.971 | 0.922 | 0.005 | 0.985 → 0.985 |
| text-image | 66 | 0.985 | 0.941 | 0.000 | 0.985 → 0.985 |
| text-table | 13 | 1.000 | 0.955 | 0.000 | 0.923 → 0.923 |
| text-table-image | 13 | 0.859 | 0.910 | 0.038 | 0.846 → 0.917 |

## Paired per-query changes (`dev_sample`, correctness)

- Wrong/refused in M4, correct in M5: **8**
- Correct in M4, wrong/refused in M5: **12**

## Answers where the check removed a sentence (2 on `dev_sample`; 2 shown)

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

### Removed: `86997f53-2801-4007-a0e4-de847455b000` (abstractive, text-table-image)

- **Question:** How does inheritance affect access to member variables in object-oriented programming?
- **Final answer:** INSUFFICIENT_EVIDENCE: grounding check: no claim is supported by a cited passage
- **Reference:** Inheritance allows a derived class to inherit properties and behaviors from a base class. Member variables with protected access in the base class can be accessed directly by derived classes but remain inaccessible outside these classes unless accessed through public methods or functions provided by those classes.
- **Judge:** faithful –, correct 0.000
- **Sentences:**
  - (kept, uncited) Inheritance allows derived classes to access the members of the base class, but the access level (public, protected, private) determines which members can be accessed.
  - (REMOVED) Protected members of the base class can be accessed by derived classes, while private members cannot.
    - `[1]` [2410.01999v4 §20 p.30] → **unsupported**: The passage describes a scenario where protected members of a base class are accessible by derived classes, but it does not mention private members' accessibility.
      > program, let's analyze it step by step: 1. Class Definition: - `class A` has two protected integer members `a` and `b`. - It also has a public member function `disp()` that prints the values of `a` and `b`. 2. Inheritance: - `class B` publicly inherits from class A. - Class B introduces two additional private integer members, `x` and `y`. 3. Functionality: - The function in class A (`disp()`) is d…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:
- **Pre-check answer:** Inheritance allows derived classes to access the members of the base class, but the access level (public, protected, private) determines which members can be accessed. Protected members of the base class can be accessed by derived classes, while private members cannot [2410.01999v4 §20 p.30].

## 10 cited answers for manual review (seeded sample of answered `dev_sample` questions)

### Review 1: `68f0e09b-fd3c-40c5-982e-38ef7f79191d` (abstractive, text-image)

- **Question:** How does the variational principle apply to Hele-Shaw cell dynamics?
- **Final answer:** The variational principle was derived and applied to pattern selection problems in a Hele-Shaw cell in wedge and channel geometries, resulting in excellent agreement with experiments [2411.03001v2 §0 p.5]. This principle complements a non-variational selection developed earlier, as surface tension is not needed for the selection, contrary to common belief [2411.03001v2 §0 p.5]. The principle was used to maximize the entropy of the most probable (classical) scenario associated with the processes [2411.03001v2 §0 p.1].
- **Reference:** The variational principle maximizes entropy to address pattern selection problems in Hele-Shaw cells, aligning results with experimental data and challenging traditional reliance on surface tension.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) The variational principle was derived and applied to pattern selection problems in a Hele-Shaw cell in wedge and channel geometries, resulting in excellent agreement with experiments.
    - `[3]` [2411.03001v2 §0 p.5] → **supported**: The passage directly states that the variational principle was derived and applied to pattern selection problems in a Hele-Shaw cell in wedge and channel geometries, resulting in excellent agreement with experiments.
      > principle was derived and applied to pattern selection problems in a Hele-Shaw cell in wedge and channel geometries. The results obtained are in excellent agreement with the ex- periments. This principle complements a non-variational selection developed earlier [24], since for both selections, surface tension is not needed, contrary to common belief. The authors acknowledge useful discussions with…
  - (kept) This principle complements a non-variational selection developed earlier, as surface tension is not needed for the selection, contrary to common belief.
    - `[3]` [2411.03001v2 §0 p.5] → **supported**: The passage directly states that the variational principle complements a non-variational selection developed earlier, and that surface tension is not needed for the selection, contrary to common belief.
      > principle was derived and applied to pattern selection problems in a Hele-Shaw cell in wedge and channel geometries. The results obtained are in excellent agreement with the ex- periments. This principle complements a non-variational selection developed earlier [24], since for both selections, surface tension is not needed, contrary to common belief. The authors acknowledge useful discussions with…
  - (kept) The principle was used to maximize the entropy of the most probable (classical) scenario associated with the processes.
    - `[1]` [2411.03001v2 §0 p.1] → **supported**: The passage states that the variational principle was applied to maximize the entropy of the most probable (classical) scenario associated with processes in a Hele-Shaw cell, which directly supports the claim.
      > Variational Pattern Selection Mark Mineev-Weinstein1 and Oleg Alekseev2 1New Mexico Consortium, Los Alamos, NM, 87544, USA 2Chebyshev Laboratory, Department of Mathematics and Computer Science, Saint-Petersburg State University, 14-th line, 199178, Saint-Petersburg, Russia (Dated: March 5, 2025) We address pattern selection problems in non-linear interface dynamics by maximizing the entropy of the…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 2: `96c9ec19-be6a-416f-94c7-d9121966fd0e` (extractive, text)

- **Question:** What type of algorithm does the agent use to decide on actions?
- **Final answer:** The agent uses a contextual no-swap-regret learning algorithm, and also possibly a mean-based learning algorithm [2402.09721v6 §6 p.6].
- **Reference:** The agent uses some adaptive algorithm to learn from history which action to take.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) The agent uses a contextual no-swap-regret learning algorithm, and also possibly a mean-based learning algorithm.
    - `[1]` [2402.09721v6 §6 p.6] → **supported**: The passage states that the principal cannot do much better than the Stackelberg value if the agent uses a contextual no-swap-regret algorithm, which directly supports the claim that the agent uses such an algorithm.
      > In each round t = 1, . . . , T: (1) Using some algorithm that learns from history (including signals, actions, and utility feed- back in the past, described in details later), the agent chooses a strategy ρt : S →∆(A) that maps each possible signal s ∈S to a distribution over actions ρt(s) ∈∆(A). (2) The principal chooses a strategy πt = {(πt s, xt s)}s∈S, which is a distribution over signals S an…
    - `[5]` [2402.09721v6 §13 p.13] → **unsupported**: The passage discusses mean-based learning algorithms and their exploitable nature by the principal but does not mention the use of a contextual no-swap-regret learning algorithm or confirm the use of both algorithms.
      > 3.4 Agent’s Mean-Based Learning: Exploitable by the Principal Many no-regret (but not no-swap-regret) learning algorithms (e.g., MWU, FTPL, EXP-3) satisfy the following contextual mean-based property: Definition 3.1 (Braverman et al. (2018)). Let σt s(a) = � j∈[t]:sj=s v(ωj, a) be the sum of historical utilities of the receiver in the first t rounds if he takes action a when the signal/context is …
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 3: `e84891a6-10a3-44b8-a8e4-8a914e392ef5` (extractive, text)

- **Question:** Can the agent's strategy be randomized in this model?
- **Final answer:** Yes, the agent's strategy can be randomized in this model. The model allows the agent to use a randomized strategy where, for each signal, the agent can take a randomized action [2402.09721v6 §10 p.9]. Additionally, the principal's utility analysis considers the agent's randomized strategies, showing that the principal's expected utility can be affected by the randomness in the agent's actions [2402.09721v6 §1 p.4].
- **Reference:** Yes, we allow the agent's strategy to be randomized.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept, uncited) Yes, the agent's strategy can be randomized in this model.
  - (kept) The model allows the agent to use a randomized strategy where, for each signal, the agent can take a randomized action.
    - `[2]` [2402.09721v6 §10 p.9] → **supported**: The passage explicitly mentions that the agent can use a randomized strategy where the expected utility is at most δ-worst than the best strategy, which supports the claim that the model allows the agent to use a randomized strategy.
      > 3.1 Generalized Principal-Agent Problem with Approximate Best Response We first define the generalized principal-agent problem with an approximately-best-responding agent. The classic generalized principal-agent problem (Section 2.1) assumes that, after receiving a signal s ∈S (and observing the principal’s decision xs ∈X), the agent will take an optimal action with respect to xs. This means that …
  - (kept) Additionally, the principal's utility analysis considers the agent's randomized strategies, showing that the principal's expected utility can be affected by the randomness in the agent's actions.
    - `[3]` [2402.09721v6 §1 p.4] → **supported**: The passage discusses how the principal's expected utility can be affected by the randomness in the agent's actions, specifically mentioning that no-swap-regret learning algorithms are randomized and can lead to sub-optimal actions with certain probabilities.
      > is the reason for the asymmetry between the worst-case utility U ∗−Θ( � SReg(T) T ) and the best-case utility U ∗+ O(SReg(T) T ) that the principal can obtain against a no-swap-regret learning agent? Roughly speaking, a no-swap-regret learning agent is approximately best respond- ing to the principal’s average strategy over all T periods, with the degree of approximate best response measured by th…
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

### Review 5: `cb251bdc-2146-47b8-be8a-8d50fcf2161c` (extractive, text)

- **Question:** Are the performance criteria strictly concave?
- **Final answer:** Yes, the performance criteria are strictly concave. This is supported by the passage which states that "the broker’s and the informed trader’s performance criteria are strictly concave functionals in terms of their respective trading strategies" [2412.17712v2 §2 p.2].
- **Reference:** Yes, both $J^{I}$ and $J^{B}$ are strictly concave.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept, uncited) Yes, the performance criteria are strictly concave.
  - (kept) This is supported by the passage which states that "the broker’s and the informed trader’s performance criteria are strictly concave functionals in terms of their respective trading strategies".
    - `[3]` [2412.17712v2 §2 p.2] → **supported**: The passage directly states that the broker’s and the informed trader’s performance criteria are strictly concave functionals in terms of their respective trading strategies, which supports the claim.
      > section 3, we show that the broker’s and the informed trader’s performance criteria are strictly concave functionals in terms of their respective trading strategies, and compute the Gâteaux-derivatives of the criteria. Finally, in section 4, we characterize the Nash equilibrium as the solution of a filtered system of FBSDEs and prove its existence and uniqueness for small time horizon. Moreover, w…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 6: `679f1070-6689-41f8-adea-603132492a7b` (extractive, text-image)

- **Question:** Are temperature effects incorporated into any forecasting models for short-term forecasts in France?
- **Final answer:** Yes, temperature effects are incorporated into forecasting models for short-term forecasts in France. The \Temp model, which includes temperature effects, performs best in France for horizons greater than a few days, showing an approximate 10% improvement in forecasting accuracy [2405.17070v2 §18 p.29]. Additionally, the inclusion of temperature information is beneficial even when accurate temperature forecasts are unavailable, as it contributes to improved forecasting accuracy [2405.17070v2 §18 p.29].
- **Reference:** Yes, temperature effects are incorporated into forecasting models like GAM for short-term forecasts in France.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept, uncited) Yes, temperature effects are incorporated into forecasting models for short-term forecasts in France.
  - (kept) The \Temp model, which includes temperature effects, performs best in France for horizons greater than a few days, showing an approximate 10% improvement in forecasting accuracy.
    - `[2]` [2405.17070v2 §18 p.29] → **supported**: The passage states that incorporating temperature effects contributes to improved forecasting accuracy in France for horizons greater than a few days, with an approximate 10% improvement.
      > 6.4. Weekly and Hourly Performance For deeper insights, how MAE changes throughout the one-year forecasting horizons and the hours in one day, Figure 11 shows the weekly and hourly averaged MAEs for the three best-performing non- GAM-based benchmarks alongside our GAM-type models for France and Germany. France Germany 1 5 9 13 17 21 25 29 33 37 41 45 49 3 4 5 1.5 2.0 2.5 3.0 3.5 Week MAE [GW] SRWA…
  - (kept) Additionally, the inclusion of temperature information is beneficial even when accurate temperature forecasts are unavailable, as it contributes to improved forecasting accuracy.
    - `[1]` [2405.17070v2 §18 p.29] → **supported**: The passage states that incorporating temperature effects improves forecasting accuracy in France even when accurate temperature forecasts are unavailable, which directly supports the claim.
      > we observe in Germany that the full GAM model and \Temp model perform best (approx. 10%, 15% and 7% better than \AR, \HLD and \States). In France, in particular, incorporating temperature effects contributes to improved forecasting accuracy (approx. 10% for horizons greater than a few days). This, along with the worse 29 performance of the STL benchmark (approx. 15% and 60% in France and Germany, …
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 7: `115fdbd6-df01-4cac-b1a2-c61161c7dc7c` (abstractive, text-table-image)

- **Question:** Why is it beneficial for a channel estimation scheme to require fewer relevant subcarriers?
- **Final answer:** Requiring fewer relevant subcarriers reduces the computational complexity of the channel estimation scheme [2407.07009v2 §10 p.5]. This is because the model can be optimized by considering only the relevant subcarriers, leading to a decrease in the overall computational load [2407.07009v2 §10 p.5]. Additionally, fewer relevant subcarriers may indicate higher accuracy in conventional channel estimation, as the model can maintain BER performance with a reduced number of subcarriers [2407.07009v2 §21 p.12].
- **Reference:** Requiring fewer relevant subcarriers is beneficial because it reduces computational complexity and resource usage while still achieving effective signal processing, as demonstrated by the TRFI-FNN's ability to maintain BER performance with fewer subcarriers than other models.
- **Judge:** faithful 0.000, correct 1.000
- **Sentences:**
  - (kept) Requiring fewer relevant subcarriers reduces the computational complexity of the channel estimation scheme.
    - `[5]` [2407.07009v2 §10 p.5] → **supported**: The passage states that reducing the model input size by considering only relevant subcarriers can significantly decrease the overall computational complexity.
      > III. XAI-CHEST FRAMEWORK DESIGN Providing external interpretability of the black-box model used for channel estimation could be achieved through clas- sifying the model’s input into relevant and irrelevant by employing a perturbation-based methodology. The main in- tuition is that if a subcarrier is relevant for the decision- making of a trained black box model, then adding noise with high weight …
  - (kept) This is because the model can be optimized by considering only the relevant subcarriers, leading to a decrease in the overall computational load.
    - `[5]` [2407.07009v2 §10 p.5] → **supported**: The passage states that considering only relevant subcarriers can reduce computational complexity and improve channel estimation performance, which directly supports the claim that requiring fewer relevant subcarriers decreases computational load.
      > III. XAI-CHEST FRAMEWORK DESIGN Providing external interpretability of the black-box model used for channel estimation could be achieved through clas- sifying the model’s input into relevant and irrelevant by employing a perturbation-based methodology. The main in- tuition is that if a subcarrier is relevant for the decision- making of a trained black box model, then adding noise with high weight …
  - (kept) Additionally, fewer relevant subcarriers may indicate higher accuracy in conventional channel estimation, as the model can maintain BER performance with a reduced number of subcarriers.
    - `[2]` [2407.07009v2 §21 p.12] → **supported**: The passage indicates that higher accuracy in conventional channel estimation is associated with fewer relevant subcarriers, as the TRFI-FNN model requires fewer subcarriers to maintain BER performance compared to STA-FNN.
      > that the TRFI-FNN model may neglect more subcarriers than the STA-FNN channel estimation scheme. This is shown in Figure 11(a), where we can notice that even though we consider the HFS channel model, the noise distribution of the HFS channel model is still shifted towards one, signifying that the TRFI-FNN requires less relevant subcarriers than the STA-FNN channel estimation scheme in order to pre…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 8: `3ff4eef8-e465-4593-9811-49b6bd1dc1e8` (abstractive, text)

- **Question:** What is the purpose of using latent factors in feature selection for multiclass classification?
- **Final answer:** The purpose of using latent factors in feature selection for multiclass classification is to represent each class and perform feature selection separately for each class based on an SNR, enabling class incremental learning with feature selection [2412.10128v2 §12 p.8]. This approach allows distinguishing features with high unexplained variance from meaningful signals by using the inverse of the noise covariance as a weight matrix [2412.10128v2 §2 p.2].
- **Reference:** Latent factors are used to represent each class separately, allowing for tailored feature selection based on signal-to-noise ratio (SNR) for each class. This approach facilitates class incremental learning and ensures that the method is theoretically grounded rather than heuristic.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) The purpose of using latent factors in feature selection for multiclass classification is to represent each class and perform feature selection separately for each class based on an SNR, enabling class incremental learning with feature selection.
    - `[1]` [2412.10128v2 §12 p.8] → **supported**: The passage states that latent factors are used to represent each class and perform feature selection separately based on SNR, which enables class incremental learning with feature selection.
      > 6. Conclusion This paper introduced a feature selection method for multi- class classification that uses latent factors to represent each class and performs feature selection separately for each class based on an SNR. For this reason, this approach can be easily used for class incremental learning with feature selec- tion. The paper also provides theoretical true feature recov- ery guarantees, whi…
  - (kept) This approach allows distinguishing features with high unexplained variance from meaningful signals by using the inverse of the noise covariance as a weight matrix.
    - `[2]` [2412.10128v2 §2 p.2] → **supported**: The passage states that using the inverse of the noise covariance as a weight matrix helps distinguish features with high unexplained variance from meaningful signals, which directly supports the claim.
      > The related work can be divided into three different areas, which will be discussed below. Feature Selection Methods for PPCA & LFA. In previous studies, low-rank generative models, particularly Principal Component Analysis (PCA), have been extensively used for feature selection and multi-class classification. The incorporation of feature weights in PCA has been explored in [24] to emphasize speci…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 9: `2d06aa3b-1636-4fe9-b219-8ce811dcf891` (abstractive, text)

- **Question:** Why is collecting confusion pairs important for improving ASR systems?
- **Final answer:** Collecting confusion pairs is important for improving ASR systems because it allows researchers to analyze common errors and understand the sources of decreased accuracy, such as words that are parts of medical terms and fillers [2404.05659v3 §26 p.10]. This analysis provides opportunities to enhance the accuracy of ASR systems [2404.05659v3 §26 p.10].
- **Reference:** It gives researchers an opportunity to analyze common ASR errors and improve the ASR accuracy.
- **Judge:** faithful 1.000, correct 1.000
- **Sentences:**
  - (kept) Collecting confusion pairs is important for improving ASR systems because it allows researchers to analyze common errors and understand the sources of decreased accuracy, such as words that are parts of medical terms and fillers.
    - `[1]` [2404.05659v3 §26 p.10] → **supported**: The passage states that collecting confusion pairs helps analyze common errors and understand sources of decreased accuracy, including words that are parts of medical terms and fillers, which directly supports the claim.
      > C.2 Error Analysis of Confusion Pairs Table 13 shows the statistics of confusion pairs in VietMed-Test using the best pre-trained model XLSR-53-Viet. Closely similar words could lead to the decreased accuracy of an ASR system. There- fore, collecting confusion pairs which the ASR system often misrecognized gives researchers an opportunity to analyze common ASR errors and improve the ASR accuracy. …
  - (kept) This analysis provides opportunities to enhance the accuracy of ASR systems.
    - `[1]` [2404.05659v3 §26 p.10] → **supported**: The passage states that analyzing confusion pairs helps identify common ASR errors, which can be used to improve the accuracy of ASR systems.
      > C.2 Error Analysis of Confusion Pairs Table 13 shows the statistics of confusion pairs in VietMed-Test using the best pre-trained model XLSR-53-Viet. Closely similar words could lead to the decreased accuracy of an ASR system. There- fore, collecting confusion pairs which the ASR system often misrecognized gives researchers an opportunity to analyze common ASR errors and improve the ASR accuracy. …
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:

### Review 10: `a1eb98ba-a821-42de-9d7d-894d9dd9594c` (extractive, text)

- **Question:** Is there a statistically significant difference in labor productivity spillovers between Low and High peers?
- **Final answer:** Yes, there is a statistically significant difference in labor productivity spillovers between Low and High peers. The results show that the spillovers, in general, tend to be stronger when coming from smaller and less productive firms, and the only exception is the labor productivity of customers, for which we do not find a statistically significant difference between the strength of spillovers of Low and High peers [2405.13422v2 §12 p.29]. However, the coefficients for labor productivity spillovers from Low and High peers are statistically significant [2405.13422v2 §16 p.41].
- **Reference:** No, there is no statistically significant difference between the strength of spillovers of Low and High peers for labor productivity.
- **Judge:** faithful 0.000, correct 0.000
- **Sentences:**
  - (kept, uncited) Yes, there is a statistically significant difference in labor productivity spillovers between Low and High peers.
  - (kept) The results show that the spillovers, in general, tend to be stronger when coming from smaller and less productive firms, and the only exception is the labor productivity of customers, for which we do not find a statistically significant difference between the strength of spillovers of Low and High peers.
    - `[1]` [2405.13422v2 §12 p.29] → **supported**: The passage directly states that there is no statistically significant difference in labor productivity spillovers between Low and High peers, which matches the claim.
      > below the median. The results are reported in Table 4. We find that the spillovers, in general, tend to be stronger when coming from smaller and less productive firms. That is, big and more productive firms are relatively worse at disseminating information about importing (or are more capable of shielding such in- formation). The only exception is the labour productivity of customers, for which we…
  - (kept) However, the coefficients for labor productivity spillovers from Low and High peers are statistically significant.
    - `[5]` [2405.13422v2 §16 p.41] → **supported**: The passage provides coefficients for labor productivity spillovers from both Low and High peers, all of which are statistically significant as indicated by the asterisks.
      > observed median value of that characteristic divided by the total number of suppliers or customers of firm i, respectively. zHigh i is an indicator variable for having the value of the considered characteristic above the observed median value of that characteristic. In the last column, the numerator of the variables ¯yD,High ihc,t−1 and ¯yU,High ihc,t−1 counts only the neighbours that are wholesal…
- **Your verdict:** citations valid? [ ] yes [ ] no; notes:
