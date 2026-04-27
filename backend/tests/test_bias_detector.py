from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.bias_detector import (
    compute_fairness_metrics,
    normalize_dataframe,
    normalize_hired_column,
    run_bias_detection,
)


def _make_candidate_df(
    *,
    male_count: int = 24,
    female_count: int = 24,
    non_binary_count: int = 12,
    male_hire_rate: float = 0.5,
    female_hire_rate: float = 0.5,
    non_binary_hire_rate: float = 0.5,
) -> pd.DataFrame:
    groups = [
        ("Male", male_count, male_hire_rate, "Indian"),
        ("Female", female_count, female_hire_rate, "Black"),
        ("Non-binary", non_binary_count, non_binary_hire_rate, "East Asian"),
    ]
    education_cycle = ["High School", "Bachelor's", "Master's", "PhD"]
    rows: list[dict[str, object]] = []

    for gender, count, hire_rate, ethnicity in groups:
        hires = int(round(count * hire_rate))
        for index in range(count):
            age = 22 + (index % 18) + (2 if gender == "Male" else 0)
            years_experience = max(0, min(20, age - 22 - (index % 4)))
            rows.append(
                {
                    "name": f"{gender}-{index + 1}",
                    "gender": gender,
                    "age": age,
                    "ethnicity": ethnicity,
                    "years_experience": years_experience,
                    "education_level": education_cycle[index % len(education_cycle)],
                    "hired": 1 if index < hires else 0,
                    "skills": "Python, SQL",
                    "previous_companies": "FairFlow Labs",
                    "caste": "Unknown",
                    "religion": "Unknown",
                    "disability_status": "Unknown",
                    "region": "Unknown",
                    "dialect": "Unknown",
                }
            )

    return pd.DataFrame(rows)


@pytest.fixture
def biased_candidates_df() -> pd.DataFrame:
    return _make_candidate_df(
        male_hire_rate=0.65,
        female_hire_rate=0.25,
        non_binary_hire_rate=0.25,
    )


@pytest.fixture
def balanced_candidates_df() -> pd.DataFrame:
    return _make_candidate_df(
        male_hire_rate=0.5,
        female_hire_rate=0.5,
        non_binary_hire_rate=0.5,
    )


@pytest.fixture
def fairness_fixture() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    encoded_features = pd.DataFrame(
        {
            "gender": [
                "Male",
                "Male",
                "Male",
                "Male",
                "Female",
                "Female",
                "Female",
                "Female",
                "Non-binary",
                "Non-binary",
                "Non-binary",
                "Non-binary",
            ],
            "years_experience": [12, 11, 7, 6, 10, 9, 5, 4, 8, 8, 3, 3],
        }
    )
    y_true = np.array([1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0])
    y_pred = np.array([1, 1, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0])
    return encoded_features, y_true, y_pred


def test_normalize_dataframe_maps_male_aliases() -> None:
    df = pd.DataFrame({"gender": ["m", "male", "Man"], "hired": [1, 1, 1]})
    normalized = normalize_dataframe(df)
    assert normalized["gender"].tolist() == ["Male", "Male", "Male"]


def test_normalize_dataframe_maps_female_aliases() -> None:
    df = pd.DataFrame({"gender": ["f", "female", "Woman"], "hired": [1, 1, 1]})
    normalized = normalize_dataframe(df)
    assert normalized["gender"].tolist() == ["Female", "Female", "Female"]


def test_normalize_dataframe_maps_non_binary_aliases() -> None:
    df = pd.DataFrame(
        {
            "gender": ["nb", "nonbinary", "they/them", "enby", "X", "other", "prefer not to say"],
            "hired": [1, 1, 1, 1, 1, 1, 1],
        }
    )
    normalized = normalize_dataframe(df)
    assert normalized["gender"].tolist() == ["Non-binary"] * 7


def test_normalize_dataframe_normalizes_hired_values() -> None:
    df = pd.DataFrame({"gender": ["male", "female"], "hired": ["yes", "no"]})
    normalized = normalize_dataframe(df)
    assert normalized["hired"].tolist() == [1, 0]


def test_normalize_hired_column_accepts_numeric_binary() -> None:
    series = pd.Series([0, 1, 1, 0])
    normalized = normalize_hired_column(series)
    assert normalized.tolist() == [0, 1, 1, 0]


def test_normalize_hired_column_accepts_text_binary_tokens() -> None:
    series = pd.Series(["yes", "no", "true", "false", "hired", "rejected"])
    normalized = normalize_hired_column(series)
    assert normalized.tolist() == [1, 0, 1, 0, 1, 0]


def test_normalize_hired_column_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        normalize_hired_column(pd.Series(["pending", "yes"]))


def test_run_bias_detection_returns_required_keys(
    balanced_candidates_df: pd.DataFrame,
) -> None:
    result = run_bias_detection(balanced_candidates_df)
    required_keys = {
        "disparate_impact",
        "stat_parity_diff",
        "equal_opp_diff",
        "avg_odds_diff",
        "pass_flags",
        "group_selection_rates",
        "bias_detected",
        "model",
        "label_encoders",
        "encoded_features",
        "normalized_dataframe",
        "predictions",
        "probabilities",
        "feature_names",
        "majority_values",
    }
    assert required_keys.issubset(result.keys())


def test_run_bias_detection_detects_bias_with_gender_gap(
    biased_candidates_df: pd.DataFrame,
) -> None:
    result = run_bias_detection(biased_candidates_df)
    assert result["bias_detected"] is True
    assert result["disparate_impact"] < 0.8


def test_run_bias_detection_reports_no_bias_when_rates_equal(
    balanced_candidates_df: pd.DataFrame,
) -> None:
    result = run_bias_detection(balanced_candidates_df)
    assert result["bias_detected"] is False
    assert result["disparate_impact"] == pytest.approx(1.0, abs=1e-6)


def test_compute_fairness_metrics_returns_required_metric_keys(
    fairness_fixture: tuple[pd.DataFrame, np.ndarray, np.ndarray],
) -> None:
    encoded_features, y_true, y_pred = fairness_fixture
    metrics = compute_fairness_metrics(encoded_features, y_true, y_pred)
    assert {
        "disparate_impact",
        "stat_parity_diff",
        "equal_opp_diff",
        "avg_odds_diff",
        "pass_flags",
        "group_selection_rates",
    }.issubset(metrics.keys())


def test_compute_fairness_metrics_returns_all_group_selection_rates(
    fairness_fixture: tuple[pd.DataFrame, np.ndarray, np.ndarray],
) -> None:
    encoded_features, y_true, y_pred = fairness_fixture
    metrics = compute_fairness_metrics(encoded_features, y_true, y_pred)
    assert set(metrics["group_selection_rates"]) == {"Male", "Female", "Non-binary"}


def test_compute_fairness_metrics_uses_worst_case_disparate_impact(
    fairness_fixture: tuple[pd.DataFrame, np.ndarray, np.ndarray],
) -> None:
    encoded_features, y_true, y_pred = fairness_fixture
    metrics = compute_fairness_metrics(encoded_features, y_true, y_pred)
    assert metrics["disparate_impact"] == pytest.approx(0.3333, abs=1e-4)


def test_compute_fairness_metrics_returns_expected_core_values(
    fairness_fixture: tuple[pd.DataFrame, np.ndarray, np.ndarray],
) -> None:
    encoded_features, y_true, y_pred = fairness_fixture
    metrics = compute_fairness_metrics(encoded_features, y_true, y_pred)
    assert metrics["stat_parity_diff"] == pytest.approx(-0.5, abs=1e-4)
    assert metrics["equal_opp_diff"] == pytest.approx(-0.5, abs=1e-4)
    assert metrics["avg_odds_diff"] == pytest.approx(0.5, abs=1e-4)
