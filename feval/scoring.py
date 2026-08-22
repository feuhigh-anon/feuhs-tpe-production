"""Statistical scoring for faculty evaluation responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from feval.models import NormalizedExport


WEIGHT_INSTRUCTIONAL = 0.50
WEIGHT_EXPERIENCE = 0.30
WEIGHT_QUALITATIVE = 0.20
CITC_FLOOR = 0.10


@dataclass
class EvaluationScoreResult:
    """Computed evaluation score tables."""

    summary: pd.DataFrame
    per_response: pd.DataFrame
    item_weights: pd.DataFrame
    component_weights: pd.DataFrame
    reliability_alpha: float
    overall_experience_alpha: float
    class_icc: float
    low_discrimination_items: list[str]


def score_evaluations(
    normalized: NormalizedExport,
    qualitative: Optional[pd.DataFrame] = None,
    min_rci_weight: float = 0.40,
    w_instructional: Optional[float] = None,
    w_experience: Optional[float] = None,
    w_qualitative: Optional[float] = None,
) -> EvaluationScoreResult:
    """Score responses using policy component weights and partial pooling."""

    responses = normalized.responses.copy()
    instructional_columns = normalized.present_columns(normalized.faculty_columns)
    experience_columns = normalized.present_columns(normalized.overall_experience_columns)
    rci_columns = normalized.present_columns(normalized.rci_columns)

    if not instructional_columns:
        raise ValueError("No instructional performance columns were available for scoring.")
    if not experience_columns:
        raise ValueError("No overall experience columns were available for scoring.")
    if not rci_columns:
        raise ValueError("No student self-evaluation columns were available for RCI scoring.")

    instructional_scores = responses.loc[:, instructional_columns].apply(pd.to_numeric, errors="coerce")
    experience_scores = responses.loc[:, experience_columns].apply(pd.to_numeric, errors="coerce")
    rci_scores = responses.loc[:, rci_columns].apply(pd.to_numeric, errors="coerce")
    quantitative_scores = responses.loc[:, instructional_columns + experience_columns + rci_columns].apply(
        pd.to_numeric, errors="coerce"
    )

    instructional_item_weights = estimate_item_weights(instructional_scores)
    experience_item_weights = estimate_item_weights(experience_scores)
    low_discrimination_items = list(instructional_item_weights.attrs.get("low_discrimination_items", []))
    low_discrimination_items.extend(experience_item_weights.attrs.get("low_discrimination_items", []))
    instructional_1_5 = row_weighted_likert_scores(instructional_scores, instructional_item_weights)
    experience_1_5 = row_weighted_likert_scores(experience_scores, experience_item_weights)
    rci_evidence_1_5 = rci_scores.mean(axis=1, skipna=True)

    quality = compute_response_quality_weights(
        instructional_scores=instructional_scores,
        experience_scores=experience_scores,
        self_scores=rci_scores,
        all_scores=quantitative_scores,
        min_weight=min_rci_weight,
    )

    per_response = responses[["teacher"]].copy()
    for optional in ("section", "respondent"):
        if optional in responses.columns:
            per_response[optional] = responses[optional]
    per_response["instructional_performance_1_5"] = instructional_1_5
    per_response["overall_experience_1_5"] = experience_1_5
    per_response["naive_instructional_1_5"] = instructional_scores.mean(axis=1, skipna=True)
    per_response["student_self_eval_1_5"] = rci_evidence_1_5
    per_response["rci_weight"] = quality["rci_weight"]
    per_response["rci_base"] = quality["rci_base"]
    per_response["response_flags"] = quality["response_flags"]

    teacher_components = _aggregate_teacher_components(per_response)
    reference_mean = _school_quantitative_reference_mean(teacher_components)
    qualitative_scores = _direct_qualitative_score(qualitative, teacher_components["teacher"], reference_mean)
    teacher_components = teacher_components.merge(qualitative_scores, on="teacher", how="left")
    teacher_components = _attach_qualitative_diagnostics(teacher_components, qualitative)

    component_weight_map = _component_weight_map(
        w_instructional=w_instructional,
        w_experience=w_experience,
        w_qualitative=w_qualitative,
    )
    component_weights = _component_weight_table(component_weight_map)

    teacher_components["observed_teacher_rating_1_5"] = (
        teacher_components["instructional_performance_1_5"] * component_weight_map["instructional_performance"]
        + teacher_components["overall_experience_1_5"] * component_weight_map["overall_experience"]
        + teacher_components["qualitative_score_1_5"] * component_weight_map["qualitative_evidence"]
    ).clip(1.0, 5.0)

    per_response = _attach_response_composite(per_response, qualitative_scores, component_weight_map)
    class_icc = estimate_class_icc(per_response)
    summary = _partial_pool_teacher_scores(teacher_components, per_response, class_icc)

    item_weights = pd.concat(
        [
            _item_weight_table("instructional_performance", instructional_item_weights),
            _item_weight_table("overall_experience", experience_item_weights),
        ],
        ignore_index=True,
    )
    return EvaluationScoreResult(
        summary=summary,
        per_response=per_response,
        item_weights=item_weights,
        component_weights=component_weights,
        reliability_alpha=cronbach_alpha(instructional_scores),
        overall_experience_alpha=cronbach_alpha(experience_scores),
        class_icc=class_icc,
        low_discrimination_items=low_discrimination_items,
    )


def estimate_item_weights(scores: pd.DataFrame) -> pd.Series:
    """Estimate item discrimination weights using corrected item-total correlation."""

    if scores.empty:
        return pd.Series(dtype=float)

    matrix = _impute_column_means(scores.to_numpy(dtype=float))
    item_count = matrix.shape[1]
    if matrix.shape[0] < 3 or item_count == 1:
        return pd.Series(np.full(item_count, 1.0 / item_count), index=scores.columns)

    total = matrix.sum(axis=1)
    weights = []
    raw_correlations = []
    for index in range(item_count):
        item = matrix[:, index]
        rest_total = total - item
        correlation = _safe_corr(item, rest_total)
        raw_correlations.append(correlation)
        weights.append(max(correlation, CITC_FLOOR))

    weight_array = np.asarray(weights, dtype=float)
    if not np.isfinite(weight_array).all() or weight_array.sum() <= 0:
        weight_array = np.full(item_count, 1.0 / item_count)
    else:
        weight_array = weight_array / weight_array.sum()
    result = pd.Series(weight_array, index=scores.columns)
    result.attrs["low_discrimination_items"] = [
        str(column)
        for column, correlation in zip(scores.columns, raw_correlations)
        if correlation < CITC_FLOOR
    ]
    return result


def row_weighted_likert_scores(scores: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Compute per-response weighted Likert scores on the 1..5 scale."""

    aligned_weights = weights.reindex(scores.columns).fillna(0.0).to_numpy(dtype=float)
    matrix = scores.to_numpy(dtype=float)
    output = []
    for row in matrix:
        present = np.isfinite(row)
        if not present.any():
            output.append(np.nan)
            continue
        row_weights = aligned_weights[present]
        if row_weights.sum() <= 0:
            row_weights = np.full(row_weights.shape, 1.0 / len(row_weights))
        output.append(float(np.average(row[present], weights=row_weights)))
    return pd.Series(output, index=scores.index)


def compute_response_quality_weights(
    instructional_scores: pd.DataFrame,
    experience_scores: pd.DataFrame,
    self_scores: pd.DataFrame,
    all_scores: pd.DataFrame,
    min_weight: float = 0.40,
) -> pd.DataFrame:
    """Compute bounded Rater Credibility Index weights and response-pattern flags."""

    if self_scores.empty:
        self_mean = pd.Series(np.nan, index=instructional_scores.index)
    else:
        self_mean = self_scores.mean(axis=1, skipna=True)

    engagement = ((self_mean - 1.0) / 4.0).clip(0.0, 1.0).fillna(0.50)
    base = min_weight + (1.0 - min_weight) * engagement
    quality_factor = pd.Series(1.0, index=instructional_scores.index)
    flags: Dict[int, list[str]] = {index: [] for index in instructional_scores.index}

    instructional_std = instructional_scores.std(axis=1, skipna=True).fillna(0.0)
    all_std = all_scores.std(axis=1, skipna=True).fillna(0.0)
    instructional_count = instructional_scores.count(axis=1)
    all_count = all_scores.count(axis=1)
    teacher_construct_mean = pd.concat([instructional_scores, experience_scores], axis=1).mean(axis=1, skipna=True)

    instructional_straightline = (instructional_count >= 6) & (instructional_std <= 0.10)
    all_straightline = (all_count >= 10) & (all_std <= 0.10)
    mismatch = (self_mean <= 1.40) & (teacher_construct_mean >= 4.20)

    for index in instructional_scores.index[instructional_straightline]:
        flags[index].append("instructional_straightline")
    for index in all_scores.index[all_straightline]:
        flags[index].append("full_straightline")
    for index in instructional_scores.index[mismatch & instructional_straightline]:
        flags[index].append("strategic_mismatch")

    quality_factor.loc[instructional_straightline] *= 0.90
    quality_factor.loc[all_straightline] *= 0.85
    quality_factor.loc[mismatch & instructional_straightline] *= 0.85

    aberrant = _mahalanobis_flags(all_scores)
    for index in all_scores.index[aberrant]:
        flags[index].append("multivariate_outlier")
    quality_factor.loc[aberrant] *= 0.85

    final_weight = (base * quality_factor).clip(lower=min_weight, upper=1.0)
    return pd.DataFrame(
        {
            "rci_base": base.round(4),
            "rci_weight": final_weight.round(4),
            "response_flags": ["; ".join(flags[index]) for index in instructional_scores.index],
        },
        index=instructional_scores.index,
    )


def _component_weight_map(
    w_instructional: Optional[float] = None,
    w_experience: Optional[float] = None,
    w_qualitative: Optional[float] = None,
) -> dict[str, float]:
    """Resolve institutional policy weights, normalizing optional overrides."""

    weights = np.asarray(
        [
            WEIGHT_INSTRUCTIONAL if w_instructional is None else float(w_instructional),
            WEIGHT_EXPERIENCE if w_experience is None else float(w_experience),
            WEIGHT_QUALITATIVE if w_qualitative is None else float(w_qualitative),
        ],
        dtype=float,
    )
    weights = np.where(np.isfinite(weights), weights, 0.0)
    weights = np.clip(weights, 0.0, None)
    if weights.sum() <= 0:
        weights = np.asarray([WEIGHT_INSTRUCTIONAL, WEIGHT_EXPERIENCE, WEIGHT_QUALITATIVE], dtype=float)
    weights = weights / weights.sum()
    return {
        "instructional_performance": float(weights[0]),
        "overall_experience": float(weights[1]),
        "qualitative_evidence": float(weights[2]),
    }


def _component_weight_table(component_weights: Mapping[str, float]) -> pd.DataFrame:
    """Format institutional policy weights for display and export."""

    components = ["instructional_performance", "overall_experience", "qualitative_evidence"]
    weights = [component_weights[component] for component in components]
    return pd.DataFrame(
        {
            "component": components,
            "weight": np.round(weights, 6),
            "weight_percent": np.round(np.asarray(weights) * 100.0, 2),
            "estimation_method": "fixed_policy_weights",
        }
    )


def estimate_class_icc(per_response: pd.DataFrame) -> float:
    """Estimate a one-way class intraclass correlation for clustered responses."""

    if "section" not in per_response.columns or "respondent_composite_1_5" not in per_response.columns:
        return 0.0
    data = per_response[["section", "respondent_composite_1_5"]].dropna()
    if data["section"].nunique() < 2 or len(data) < 5:
        return 0.0

    groups = [group["respondent_composite_1_5"].to_numpy(dtype=float) for _, group in data.groupby("section")]
    groups = [group for group in groups if len(group) > 1]
    if len(groups) < 2:
        return 0.0

    grand_mean = data["respondent_composite_1_5"].mean()
    n_total = sum(len(group) for group in groups)
    k_groups = len(groups)
    ss_between = sum(len(group) * (group.mean() - grand_mean) ** 2 for group in groups)
    ss_within = sum(((group - group.mean()) ** 2).sum() for group in groups)
    df_between = k_groups - 1
    df_within = n_total - k_groups
    if df_between <= 0 or df_within <= 0:
        return 0.0

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    avg_size = (n_total - sum(len(group) ** 2 for group in groups) / n_total) / max(k_groups - 1, 1)
    denominator = ms_between + max(avg_size - 1.0, 0.0) * ms_within
    if denominator <= 0:
        return 0.0
    return float(max(0.0, min(1.0, (ms_between - ms_within) / denominator)))


def cronbach_alpha(scores: pd.DataFrame) -> float:
    """Cronbach's alpha for a quantitative item block."""

    if scores.shape[1] < 2 or scores.shape[0] < 2:
        return float("nan")

    matrix = _impute_column_means(scores.to_numpy(dtype=float))
    item_variances = matrix.var(axis=0, ddof=1)
    total_variance = matrix.sum(axis=1).var(ddof=1)
    if total_variance <= 0:
        return float("nan")
    item_count = matrix.shape[1]
    return float((item_count / (item_count - 1.0)) * (1.0 - item_variances.sum() / total_variance))


def _aggregate_teacher_components(per_response: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for teacher, group in per_response.groupby("teacher", dropna=False):
        weights = group["rci_weight"].fillna(0.0).to_numpy(dtype=float)
        classes = int(group["section"].nunique()) if "section" in group.columns else 1
        rows.append(
            {
                "teacher": teacher,
                "responses": int(len(group)),
                "classes": classes,
                "instructional_performance_1_5": round(
                    _weighted_mean(group["instructional_performance_1_5"], weights), 4
                ),
                "overall_experience_1_5": round(_weighted_mean(group["overall_experience_1_5"], weights), 4),
                "naive_instructional_1_5": round(float(group["naive_instructional_1_5"].mean()), 4),
                "student_self_eval_1_5": round(_weighted_mean(group["student_self_eval_1_5"], weights), 4),
                "mean_rci_weight": round(float(group["rci_weight"].mean()), 4),
                "flagged_responses": int(group["response_flags"].astype(bool).sum()),
            }
        )
    return pd.DataFrame(rows)


def _school_quantitative_reference_mean(teacher_components: pd.DataFrame) -> float:
    """Return the school-wide mean of instructional and experience scores."""

    reference = teacher_components[["instructional_performance_1_5", "overall_experience_1_5"]].mean(axis=1)
    reference_mean = float(reference.mean()) if len(reference) else 3.0
    return reference_mean if np.isfinite(reference_mean) else 3.0


def _direct_qualitative_score(
    qualitative: Optional[pd.DataFrame],
    teachers: pd.Series,
    reference_mean: float,
) -> pd.DataFrame:
    """
    Map qualitative_evidence_raw directly to a 1-5 score.

    Formula:
      raw_score = 3.0 + qualitative_evidence_raw
      final = reference_mean + confidence * (raw_score - reference_mean)
      final = clip(final, 1.0, 5.0)

    Low-confidence qualitative evidence shrinks toward the school-wide
    quantitative reference mean.
    """

    if qualitative is None or qualitative.empty or "qualitative_evidence_raw" not in qualitative.columns:
        return pd.DataFrame(
            {
                "teacher": teachers,
                "qualitative_score_1_5": reference_mean,
                "qualitative_evidence_confidence": 0.0,
            }
        )

    qual = qualitative[["teacher", "qualitative_evidence_raw", "qualitative_evidence_confidence"]].copy()
    qual["qualitative_evidence_raw"] = pd.to_numeric(qual["qualitative_evidence_raw"], errors="coerce").fillna(0.0)
    qual["qualitative_evidence_confidence"] = pd.to_numeric(
        qual["qualitative_evidence_confidence"], errors="coerce"
    ).fillna(0.0)
    merged = pd.DataFrame({"teacher": teachers}).merge(qual, on="teacher", how="left")
    merged["qualitative_evidence_raw"] = merged["qualitative_evidence_raw"].fillna(0.0)
    merged["qualitative_evidence_confidence"] = merged["qualitative_evidence_confidence"].fillna(0.0)

    confidence = merged["qualitative_evidence_confidence"].clip(0.0, 1.0)
    raw_score = (3.0 + merged["qualitative_evidence_raw"]).clip(1.0, 5.0)
    merged["qualitative_score_1_5"] = (reference_mean + confidence * (raw_score - reference_mean)).clip(1.0, 5.0)
    return merged[["teacher", "qualitative_score_1_5", "qualitative_evidence_confidence"]]


def _attach_qualitative_diagnostics(
    teacher_components: pd.DataFrame,
    qualitative: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """Attach non-scoring qualitative diagnostics to teacher components."""

    if qualitative is None or qualitative.empty or "verbose_flag_count" not in qualitative.columns:
        teacher_components["verbose_response_flags"] = 0
        return teacher_components

    diagnostics = qualitative[["teacher", "verbose_flag_count"]].copy()
    diagnostics["verbose_response_flags"] = pd.to_numeric(
        diagnostics["verbose_flag_count"], errors="coerce"
    ).fillna(0).astype(int)
    return teacher_components.merge(
        diagnostics[["teacher", "verbose_response_flags"]],
        on="teacher",
        how="left",
    ).assign(verbose_response_flags=lambda frame: frame["verbose_response_flags"].fillna(0).astype(int))


def _attach_response_composite(
    per_response: pd.DataFrame,
    qualitative_scores: pd.DataFrame,
    component_weights: Mapping[str, float],
) -> pd.DataFrame:
    result = per_response.merge(qualitative_scores[["teacher", "qualitative_score_1_5"]], on="teacher", how="left")
    result["qualitative_score_1_5"] = result["qualitative_score_1_5"].fillna(
        result[["instructional_performance_1_5", "overall_experience_1_5"]].mean(axis=1)
    )
    result["respondent_composite_1_5"] = (
        result["instructional_performance_1_5"] * component_weights["instructional_performance"]
        + result["overall_experience_1_5"] * component_weights["overall_experience"]
        + result["qualitative_score_1_5"] * component_weights["qualitative_evidence"]
    ).clip(1.0, 5.0)
    return result


def _partial_pool_teacher_scores(
    teacher_components: pd.DataFrame,
    per_response: pd.DataFrame,
    class_icc: float,
) -> pd.DataFrame:
    rows = []
    grand_mean = _weighted_mean(
        teacher_components["observed_teacher_rating_1_5"],
        np.maximum(teacher_components["responses"].to_numpy(dtype=float), 1.0),
    )
    if not np.isfinite(grand_mean):
        grand_mean = float(teacher_components["observed_teacher_rating_1_5"].mean())
    global_var = max(float(per_response["respondent_composite_1_5"].var(ddof=1)), 0.05)

    for _, teacher_row in teacher_components.iterrows():
        teacher = teacher_row["teacher"]
        others = teacher_components[teacher_components["teacher"] != teacher]
        if len(others) >= 2:
            other_weights = np.maximum(others["responses"].to_numpy(dtype=float), 1.0)
            shrinkage_target = _weighted_mean(others["observed_teacher_rating_1_5"], other_weights)
            pooling_note = ""
        else:
            shrinkage_target = grand_mean
            pooling_note = "grand_mean_fallback_insufficient_other_teachers"
        if not np.isfinite(shrinkage_target):
            shrinkage_target = grand_mean
            pooling_note = "grand_mean_fallback_insufficient_other_teachers"

        group = per_response[per_response["teacher"] == teacher]
        response_weights = group["rci_weight"].fillna(0.0).to_numpy(dtype=float)
        values = group["respondent_composite_1_5"].to_numpy(dtype=float)
        kish_n = _kish_effective_n(response_weights)
        class_count = int(teacher_row["classes"])
        if "section" in group.columns and class_count > 0:
            class_sizes = group.groupby("section").size().to_numpy(dtype=float)
            avg_class_size = float(class_sizes.mean()) if len(class_sizes) else len(group)
            cluster_n = len(group) / (1.0 + max(avg_class_size - 1.0, 0.0) * class_icc)
        else:
            cluster_n = kish_n
        effective_n = max(1.0, min(kish_n, cluster_n))
        within_var = _weighted_var(values, response_weights)
        if not np.isfinite(within_var) or within_var <= 1e-9:
            within_var = global_var
        standard_error = float(np.sqrt(within_var / effective_n))
        rows.append(
            {
                "teacher": teacher,
                "effective_response_count": effective_n,
                "teacher_standard_error": standard_error,
                "shrinkage_target_1_5": shrinkage_target,
                "pooling_note": pooling_note,
            }
        )

    uncertainty = pd.DataFrame(rows)
    merged = teacher_components.merge(uncertainty, on="teacher", how="left")
    between_var = _weighted_var(
        merged["observed_teacher_rating_1_5"].to_numpy(dtype=float),
        np.maximum(merged["effective_response_count"].to_numpy(dtype=float), 1.0),
    )
    if not np.isfinite(between_var):
        between_var = 0.0
    mean_error_var = float(np.nanmean(merged["teacher_standard_error"] ** 2))
    if not np.isfinite(mean_error_var):
        mean_error_var = 0.0
    teacher_variance = max(between_var - mean_error_var, 1e-6)

    se_squared = merged["teacher_standard_error"] ** 2
    merged["partial_pooling_shrinkage"] = teacher_variance / (teacher_variance + se_squared)
    merged["final_teacher_rating_1_5"] = (
        merged["partial_pooling_shrinkage"] * merged["observed_teacher_rating_1_5"]
        + (1.0 - merged["partial_pooling_shrinkage"]) * merged["shrinkage_target_1_5"]
    ).clip(1.0, 5.0)
    posterior_var = (teacher_variance * se_squared) / (teacher_variance + se_squared)
    merged["rating_ci_low_1_5"] = (merged["final_teacher_rating_1_5"] - 1.96 * np.sqrt(posterior_var)).clip(1.0, 5.0)
    merged["rating_ci_high_1_5"] = (merged["final_teacher_rating_1_5"] + 1.96 * np.sqrt(posterior_var)).clip(1.0, 5.0)
    merged["class_icc"] = class_icc

    display_columns = [
        "teacher",
        "final_teacher_rating_1_5",
        "rating_ci_low_1_5",
        "rating_ci_high_1_5",
        "observed_teacher_rating_1_5",
        "instructional_performance_1_5",
        "overall_experience_1_5",
        "qualitative_score_1_5",
        "student_self_eval_1_5",
        "responses",
        "classes",
        "effective_response_count",
        "partial_pooling_shrinkage",
        "mean_rci_weight",
        "flagged_responses",
        "verbose_response_flags",
        "class_icc",
        "pooling_note",
        "naive_instructional_1_5",
    ]
    for column in display_columns:
        if column in merged.columns and pd.api.types.is_numeric_dtype(merged[column]):
            merged[column] = merged[column].round(4)
    return merged[display_columns].sort_values(
        ["final_teacher_rating_1_5", "effective_response_count"],
        ascending=[False, False],
    )


def _item_weight_table(construct: str, weights: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "construct": construct,
            "item_id": weights.index,
            "weight": weights.values,
            "weight_percent": weights.values * 100.0,
        }
    )


def _weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float:
    value_array = np.asarray(list(values), dtype=float)
    weight_array = np.asarray(list(weights), dtype=float)
    present = np.isfinite(value_array) & np.isfinite(weight_array) & (weight_array > 0)
    if not present.any():
        return float("nan")
    return float(np.average(value_array[present], weights=weight_array[present]))


def _weighted_var(values: Iterable[float], weights: Iterable[float]) -> float:
    value_array = np.asarray(list(values), dtype=float)
    weight_array = np.asarray(list(weights), dtype=float)
    present = np.isfinite(value_array) & np.isfinite(weight_array) & (weight_array > 0)
    if present.sum() < 2:
        return float("nan")
    value_array = value_array[present]
    weight_array = weight_array[present]
    mean = np.average(value_array, weights=weight_array)
    variance = np.average((value_array - mean) ** 2, weights=weight_array)
    return float(variance)


def _kish_effective_n(weights: Iterable[float]) -> float:
    weight_array = np.asarray(list(weights), dtype=float)
    present = np.isfinite(weight_array) & (weight_array > 0)
    if not present.any():
        return 1.0
    weight_array = weight_array[present]
    denominator = float((weight_array**2).sum())
    if denominator <= 0:
        return 1.0
    return float((weight_array.sum() ** 2) / denominator)


def _impute_column_means(matrix: np.ndarray) -> np.ndarray:
    output = matrix.astype(float, copy=True)
    if output.size == 0:
        return output
    column_means = np.nanmean(output, axis=0)
    column_means = np.where(np.isfinite(column_means), column_means, 3.0)
    rows, columns = np.where(~np.isfinite(output))
    output[rows, columns] = column_means[columns]
    return output


def _safe_corr(first: np.ndarray, second: np.ndarray) -> float:
    if np.std(first) <= 1e-9 or np.std(second) <= 1e-9:
        return 0.0
    value = float(np.corrcoef(first, second)[0, 1])
    return value if np.isfinite(value) else 0.0


def _mahalanobis_flags(scores: pd.DataFrame) -> pd.Series:
    matrix = scores.to_numpy(dtype=float)
    if matrix.shape[0] < max(20, matrix.shape[1] + 5) or matrix.shape[1] < 2:
        return pd.Series(False, index=scores.index)

    matrix = _impute_column_means(matrix)
    centered = matrix - matrix.mean(axis=0)
    covariance = np.cov(centered, rowvar=False)
    covariance = covariance + np.eye(covariance.shape[0]) * 0.05
    if not np.isfinite(covariance).all():
        return pd.Series(False, index=scores.index)
    try:
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            inverse = np.linalg.pinv(covariance)
    except np.linalg.LinAlgError:
        return pd.Series(False, index=scores.index)
    if not np.isfinite(inverse).all():
        return pd.Series(False, index=scores.index)

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        distances = np.einsum("ij,jk,ik->i", centered, inverse, centered)
    distances = np.where(np.isfinite(distances), distances, 0.0)
    try:
        from scipy.stats import chi2

        threshold = chi2.ppf(0.999, df=matrix.shape[1])
    except ImportError:
        threshold = _chi_square_ppf_999_approx(matrix.shape[1])
    return pd.Series(distances > threshold, index=scores.index)


def _chi_square_ppf_999_approx(df: int) -> float:
    """
    Approximate the chi-squared p=.999 critical value when SciPy is unavailable.

    Parameters
    ----------
    df : int
        Chi-squared degrees of freedom.

    Returns
    -------
    float
        Wilson-Hilferty approximation to chi2.ppf(0.999, df).

    Methodological note
    -------------------
    The operational path uses scipy.stats.chi2.ppf. This approximation keeps
    local development functional before dependencies are installed; it should
    not be preferred for audited production runs.
    """

    z_999 = 3.090232306167813
    df = max(int(df), 1)
    return float(df * (1.0 - 2.0 / (9.0 * df) + z_999 * np.sqrt(2.0 / (9.0 * df))) ** 3)
