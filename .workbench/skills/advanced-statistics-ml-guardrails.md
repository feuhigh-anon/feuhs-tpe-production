# Skill: Advanced Statistics and Machine Learning Guardrails

Activate this skill for statistical modeling, machine learning, forecasting, causal analysis, inferential statistics, clustering, dimensionality reduction, psychometrics, simulation, or scientific modeling. Do not force the complete checklist onto ordinary application work.

## First classify the task

Choose one or more:

- descriptive
- inferential
- predictive
- causal
- forecasting/time series
- unsupervised
- measurement/psychometric
- simulation/scientific model

The classification determines the relevant assumptions, validation, and uncertainty requirements.

## Preflight gate

Before coding or recommending a model, identify:

1. operational question or scientific question
2. target, estimand, outcome, or decision
3. unit of analysis and data-generating process
4. sampling, grouping, repeated-measures, spatial, and temporal structure
5. missingness mechanism and measurement quality
6. leakage and contamination risks
7. deployment or inference conditions
8. error costs and decision threshold, if applicable
9. privacy, fairness, or governance constraints
10. minimum acceptable evidence for the intended claim

If the target or estimand is undefined, stop at a design memo rather than fitting a model.

## Universal statistical safeguards

- Split before fitting preprocessing, feature selection, resampling, or tuning. Put transformations inside a pipeline and fit them within each training fold.
- Keep the final test or external validation set untouched until the evaluation stage.
- Use group-aware, temporal, spatial, or nested validation when the data structure requires it.
- Establish a naive and a simple interpretable baseline.
- Select metrics that reflect the actual loss, class prevalence, decision, or scientific objective.
- Report uncertainty, variation across folds or resamples, and sensitivity to key assumptions.
- Perform error analysis, subgroup analysis where appropriate, and inspect systematic failure modes.
- Check calibration when outputs are used as probabilities or risk scores.
- Document data version, preprocessing, features, hyperparameters, random seeds, environment, and evaluation protocol.
- Do not convert association, prediction, correlation, feature importance, or cluster membership into a causal claim without an appropriate causal design.
- Do not claim fairness from one metric or small unstable subgroups; report denominators and uncertainty.

## Conditional decisions

- Scaling is needed for many distance-, gradient-, and regularization-based models, but not universally for tree models.
- Shuffling may be useful within an independent training set, but not when it violates temporal, grouped, spatial, sequential, or online-learning structure.
- Imputation and missingness indicators require a missing-data rationale and leakage-safe implementation.
- SMOTE and resampling must occur inside training folds and may be unsuitable for grouped, temporal, spatial, or highly structured data.
- Class weights, threshold tuning, precision-recall analysis, calibration, and decision-curve reasoning may be preferable to resampling.
- Hyperparameter tuning requires a validation design that limits overfitting to the validation data.
- Deep learning, Bayesian optimization, DVC, MLflow, GPU batching, or other advanced tooling should be justified by the task, data scale, and reproducibility benefit.

## Additional checks by task type

### Inferential

Define the estimand, sampling unit, comparison, effect size, uncertainty interval, model assumptions, multiplicity strategy, and sensitivity analyses. Consider clustering, heteroskedasticity, nonlinearity, missing data, and model misspecification.

### Causal

Define treatment, outcome, time zero, population, estimand, confounders, mediators, colliders, identification assumptions, and whether the design supports the intended claim. Do not infer intervention effects from predictive accuracy.

### Forecasting/time series

Use temporal ordering, forecast-origin evaluation, leakage-safe lag construction, seasonality checks, drift monitoring, and a time-series baseline.

### Multilevel/repeated data

Check whether observations are nested or repeated. Consider group-aware splits, random effects or other dependence-aware methods, cluster-robust uncertainty, and the level at which the claim is made.

### Unsupervised learning

Define the purpose of the clusters or representation, scale and distance choices, stability, sensitivity, external or domain validation, and the danger of treating discovered structure as natural or causal.

### Measurement/psychometrics

Check construct definition, item provenance, scoring, reliability, dimensionality, invariance, missing responses, and whether the available evidence supports the intended interpretation.

## Required preflight output

```text
Task classification
Target or estimand
Unit of analysis
Primary risks
Validation design
Baseline
Metrics and uncertainty
Domain-specific checks
Decision: proceed / revise design / stop
```

## Required verification output

```text
Data and leakage checks
Preprocessing placement
Validation results
Baseline comparison
Uncertainty/calibration
Error and subgroup analysis
Assumption and domain review
Reproducibility evidence
Unsupported claims to remove
```
