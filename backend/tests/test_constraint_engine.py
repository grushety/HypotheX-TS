from app.services.constraint_engine import ConstraintEngine


def test_constraint_engine_returns_pass_for_valid_trend_and_plateau_segments():
    engine = ConstraintEngine()
    series = [0.0, 0.2, 0.4, 0.6, 1.0, 1.0, 1.01, 0.99]
    segments = [
        {"segmentId": "segment-trend", "startIndex": 0, "endIndex": 3, "label": "trend"},
        {"segmentId": "segment-plateau", "startIndex": 4, "endIndex": 7, "label": "plateau"},
    ]

    result = engine.evaluate(series, segments, operation_id="op-pass")

    assert result.status == "PASS"
    assert result.constraintMode == "soft"
    assert result.violations == ()


def test_constraint_engine_warns_for_soft_trend_monotonicity_violation():
    engine = ConstraintEngine()
    series = [0.0, 1.0, 0.1, 1.1]
    segments = [
        {"segmentId": "segment-trend", "startIndex": 0, "endIndex": 3, "label": "trend"},
    ]

    result = engine.evaluate(series, segments, operation_id="op-trend-warn")

    assert result.status == "WARN"
    assert result.constraintMode == "soft"
    assert result.violations[0].constraintId == "monotonic_trend_consistency"
    assert result.violations[0].severity == "soft"
    assert result.to_dict()["status"] == "WARN"


def test_constraint_engine_fails_for_hard_minimum_duration_violation():
    engine = ConstraintEngine()
    series = [0.0, 0.1, 0.2]
    segments = [
        {"segmentId": "segment-short", "startIndex": 1, "endIndex": 1, "label": "plateau"},
    ]

    result = engine.evaluate(series, segments, operation_id="op-duration-fail")

    assert result.status == "FAIL"
    assert result.constraintMode == "hard"
    assert result.violations[0].constraintId == "minimum_segment_duration"
    assert result.violations[0].severity == "hard"


def test_constraint_engine_mode_override_changes_severity_handling_only():
    engine = ConstraintEngine()
    series = [0.0, 1.0, 0.1, 1.1]
    segments = [
        {"segmentId": "segment-trend", "startIndex": 0, "endIndex": 3, "label": "trend"},
    ]

    soft_result = engine.evaluate(
        series,
        segments,
        operation_id="op-mode-soft",
        constraint_mode="soft",
    )
    hard_result = engine.evaluate(
        series,
        segments,
        operation_id="op-mode-hard",
        constraint_mode="hard",
    )

    assert soft_result.status == "WARN"
    assert soft_result.violations[0].severity == "soft"
    assert hard_result.status == "FAIL"
    assert hard_result.violations[0].severity == "hard"
    assert soft_result.violations[0].constraintId == hard_result.violations[0].constraintId


def test_constraint_engine_reports_basic_label_compatibility_violation():
    engine = ConstraintEngine()
    series = [0.0, 0.1, 0.3, 0.2, 0.0, 0.2]
    segments = [
        {"segmentId": "segment-event-a", "startIndex": 0, "endIndex": 2, "label": "event"},
        {"segmentId": "segment-event-b", "startIndex": 3, "endIndex": 5, "label": "event"},
    ]

    result = engine.evaluate(series, segments, operation_id="op-label-compat")

    assert result.status == "WARN"
    assert any(violation.constraintId == "label_compatibility" for violation in result.violations)
    label_violation = next(
        violation for violation in result.violations if violation.constraintId == "label_compatibility"
    )
    assert label_violation.repairHint == {"suggestedAction": "merge_or_insert_transition"}
