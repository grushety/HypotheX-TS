from app.config import TestingConfig
from app.factory import create_app
from app.services.audit_log import AuditLogService
from app.services.operations.structural import StructuralOperationsService
from app.services.segmentation_state import SegmentationStateService


def create_segmentation_payload():
    return {
        "schemaVersion": "1.0.0",
        "segmentationId": "seg-audit-001",
        "seriesId": "series-audit-001",
        "segments": [
            {
                "segmentId": "segment-trend",
                "startIndex": 0,
                "endIndex": 3,
                "label": "trend",
                "provenance": "user",
            },
            {
                "segmentId": "segment-plateau",
                "startIndex": 4,
                "endIndex": 7,
                "label": "plateau",
                "provenance": "user",
            },
        ],
    }


def create_series():
    return [0.0, 0.2, 0.4, 0.6, 1.0, 1.0, 1.01, 0.99]


def create_operation_payload(operation_id: str, operation_type: str, target_segment_ids: list[str], parameters: dict):
    return {
        "schemaVersion": "1.0.0",
        "operationId": operation_id,
        "operationType": operation_type,
        "seriesId": "series-audit-001",
        "segmentationId": "seg-audit-001",
        "targetSegmentIds": target_segment_ids,
        "parameters": parameters,
        "requestedBy": "user",
    }


def create_app_with_context():
    app = create_app(TestingConfig)
    return app


def test_audit_log_records_successful_and_failed_operations_and_exports_ordered_session():
    app = create_app_with_context()
    with app.app_context():
        state = SegmentationStateService().create_state(create_segmentation_payload())
        operation_service = StructuralOperationsService()
        audit_service = AuditLogService()

        passed_result = operation_service.reclassify_segment(
            state,
            create_series(),
            segment_id="segment-plateau",
            new_label="event",
        )
        failed_result = operation_service.edit_boundary(
            state,
            create_series(),
            left_segment_id="segment-trend",
            right_segment_id="segment-plateau",
            new_left_end_index=0,
        )

        audit_service.log_operation(
            session_id="session-audit-001",
            operation=create_operation_payload(
                "operation-001",
                "reclassify",
                ["segment-plateau"],
                {"newLabel": "event"},
            ),
            result=passed_result,
            timestamp="2026-03-29T10:00:00Z",
        )
        audit_service.log_operation(
            session_id="session-audit-001",
            operation=create_operation_payload(
                "operation-002",
                "edit_boundary",
                ["segment-trend", "segment-plateau"],
                {"newLeftEndIndex": 0},
            ),
            result=failed_result,
            timestamp="2026-03-29T10:01:00Z",
        )
        audit_service.log_suggestion_decision(
            session_id="session-audit-001",
            series_id="series-audit-001",
            segmentation_id="seg-audit-001",
            suggestion_id="suggestion-001",
            decision="overridden",
            target_segment_ids=["segment-plateau"],
            timestamp="2026-03-29T10:02:00Z",
            metadata={"reason": "user_preferred_manual_label"},
        )

        export_payload = audit_service.export_session("session-audit-001")

        assert export_payload["sessionId"] == "session-audit-001"
        assert export_payload["endedAt"] == "2026-03-29T10:02:00Z"
        assert [event["eventType"] for event in export_payload["events"]] == [
            "operation_applied",
            "operation_rejected",
            "suggestion_overridden",
        ]
        assert export_payload["events"][0]["operationResult"]["status"] == "PASS"
        assert export_payload["events"][1]["operationResult"]["status"] == "FAIL"
        assert export_payload["events"][1]["operationResult"]["applied"] is False
        assert export_payload["events"][1]["metadata"]["targetSegmentIds"] == ["segment-trend", "segment-plateau"]
        assert export_payload["events"][2]["suggestion"]["decision"] == "overridden"


def test_audit_export_route_returns_complete_session_payload():
    app = create_app_with_context()
    with app.app_context():
        audit_service = AuditLogService()
        audit_service.log_suggestion_decision(
            session_id="session-route-001",
            series_id="series-audit-001",
            segmentation_id="seg-audit-001",
            suggestion_id="suggestion-002",
            decision="accepted",
            target_segment_ids=["segment-trend"],
            timestamp="2026-03-29T11:00:00Z",
            metadata={"reason": "user_accepted_model_boundary"},
        )
        app.config["AUDIT_LOG_SERVICE"] = audit_service

    client = app.test_client()
    response = client.get("/api/audit/sessions/session-route-001/export")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["sessionId"] == "session-route-001"
    assert payload["events"][0]["eventType"] == "suggestion_accepted"


def test_audit_export_route_returns_404_for_unknown_session():
    app = create_app_with_context()
    client = app.test_client()

    response = client.get("/api/audit/sessions/missing-session/export")

    assert response.status_code == 404
    assert "missing-session" in response.get_json()["error"]


def test_suggestion_decision_route_records_accept_and_override_events():
    app = create_app_with_context()
    client = app.test_client()

    accepted_response = client.post(
        "/api/audit/sessions/session-decision-001/suggestions/decision",
        json={
            "seriesId": "series-audit-001",
            "segmentationId": "seg-audit-001",
            "suggestionId": "suggestion-accept-001",
            "decision": "accepted",
            "targetSegmentIds": ["segment-trend"],
            "timestamp": "2026-03-30T09:00:00Z",
            "metadata": {"reason": "user_accepted_model_proposal"},
        },
    )
    overridden_response = client.post(
        "/api/audit/sessions/session-decision-001/suggestions/decision",
        json={
            "seriesId": "series-audit-001",
            "segmentationId": "seg-audit-001",
            "suggestionId": "suggestion-override-001",
            "decision": "overridden",
            "targetSegmentIds": ["segment-plateau"],
            "timestamp": "2026-03-30T09:01:00Z",
            "metadata": {"reason": "manual_edit_after_review"},
        },
    )

    assert accepted_response.status_code == 201
    assert accepted_response.get_json()["eventType"] == "suggestion_accepted"
    assert overridden_response.status_code == 201
    assert overridden_response.get_json()["eventType"] == "suggestion_overridden"

    export_response = client.get("/api/audit/sessions/session-decision-001/export")
    export_payload = export_response.get_json()
    assert [event["eventType"] for event in export_payload["events"]] == [
        "suggestion_accepted",
        "suggestion_overridden",
    ]
