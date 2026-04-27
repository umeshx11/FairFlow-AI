from __future__ import annotations

from sdg_mapping import all_sdg_targets_pass, build_sdg_mapping


def test_sdg_10_3_passes_when_disparate_impact_at_threshold() -> None:
    mapping = build_sdg_mapping(
        {"disparate_impact": 0.8, "demographic_parity": 0.0, "equalized_odds": 0.0}
    )
    assert mapping["sdg_10_3"]["pass"] is True


def test_sdg_10_3_fails_when_disparate_impact_below_threshold() -> None:
    mapping = build_sdg_mapping(
        {"disparate_impact": 0.79, "demographic_parity": 0.0, "equalized_odds": 0.0}
    )
    assert mapping["sdg_10_3"]["pass"] is False


def test_sdg_8_5_passes_when_demographic_parity_is_within_threshold() -> None:
    mapping = build_sdg_mapping(
        {"disparate_impact": 1.0, "demographic_parity": 0.1, "equalized_odds": 0.0}
    )
    assert mapping["sdg_8_5"]["pass"] is True


def test_sdg_8_5_fails_when_demographic_parity_exceeds_threshold() -> None:
    mapping = build_sdg_mapping(
        {"disparate_impact": 1.0, "demographic_parity": 0.12, "equalized_odds": 0.0}
    )
    assert mapping["sdg_8_5"]["pass"] is False


def test_sdg_16_b_passes_when_equalized_odds_is_within_threshold() -> None:
    mapping = build_sdg_mapping(
        {"disparate_impact": 1.0, "demographic_parity": 0.0, "equalized_odds": 0.08}
    )
    assert mapping["sdg_16_b"]["pass"] is True


def test_sdg_16_b_fails_when_equalized_odds_exceeds_threshold() -> None:
    mapping = build_sdg_mapping(
        {"disparate_impact": 1.0, "demographic_parity": 0.0, "equalized_odds": 0.14}
    )
    assert mapping["sdg_16_b"]["pass"] is False


def test_all_sdg_targets_pass_returns_true_only_when_all_targets_pass() -> None:
    mapping = build_sdg_mapping(
        {"disparate_impact": 0.91, "demographic_parity": 0.04, "equalized_odds": 0.03}
    )
    assert all_sdg_targets_pass(mapping) is True


def test_all_sdg_targets_pass_returns_false_when_any_target_fails() -> None:
    mapping = build_sdg_mapping(
        {"disparate_impact": 0.7, "demographic_parity": 0.04, "equalized_odds": 0.03}
    )
    assert all_sdg_targets_pass(mapping) is False
