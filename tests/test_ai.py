from career_quest.ai import validate_selection


def _cand(eid, tier, score, insufficient=True):
    return {
        "event_id": eid,
        "title": eid,
        "tier": tier,
        "score": score,
        "history": {"insufficient": insufficient},
        "facts": [
            {
                "id": "f01",
                "category": "profile",
                "code": "PROFILE_CONTEXT",
                "values": {"grade": "Middle"},
            },
            {
                "id": "f02",
                "category": "skill_gap",
                "code": "SKILL_GAP",
                "values": {"current": 2, "required": 4},
            },
            {
                "id": "f03",
                "category": "history",
                "code": "HISTORY_INSUFFICIENT",
                "values": {"observations": 1},
            },
        ],
    }


def test_rejects_injected_unknown_event():
    cands = [_cand("EV_1", 0, 50)]
    choices, problems = validate_selection(
        {
            "choices": [
                {"event_id": "EV_FAKE", "evidence_ids": [], "reason_codes": [], "explanation": ""}
            ]
        },
        cands,
    )
    assert choices == [] and problems == ["unknown_event"]


def test_main_step_must_respect_tier():
    cands = [_cand("EV_1", 0, 50), _cand("EV_2", 1, 90)]
    raw = {
        "choices": [
            {
                "event_id": "EV_2",
                "evidence_ids": ["EV_2:f01", "EV_2:f02", "EV_2:f03"],
                "reason_codes": [],
                "explanation": "",
            }
        ]
    }
    choices, _ = validate_selection(raw, cands)
    assert choices == []


def test_ungrounded_numbers_drop_explanation_and_favorable_history_removed():
    cands = [_cand("EV_1", 0, 50)]
    raw = {
        "choices": [
            {
                "event_id": "EV_1",
                "evidence_ids": ["EV_1:f01", "EV_1:f02", "EV_1:f03"],
                "reason_codes": ["TARGET_CRITICAL_GAP", "HISTORY_FAVORABLE"],
                "explanation": "Уровень 2 из 4, вы завершите за 7 дней",
            }
        ]
    }
    choices, problems = validate_selection(raw, cands)
    assert choices[0]["explanation"] == ""
    assert "HISTORY_FAVORABLE" not in choices[0]["reason_codes"]
    assert any("ungrounded" in p for p in problems)


def test_schema_requires_three_choices_when_available():
    from career_quest.ai import _schema

    assert _schema(["A", "B", "C", "D"], ["f"])["properties"]["choices"]["minItems"] == 3
    assert _schema(["A", "B"], ["f"])["properties"]["choices"]["minItems"] == 2


def test_request_params_differ_for_reasoning_models():
    from career_quest.ai import model_params

    chat = model_params("gpt-4.1")
    assert chat["temperature"] == 0.1 and "max_tokens" in chat
    reasoning = model_params("gpt-5")
    assert "temperature" not in reasoning
    assert "max_completion_tokens" in reasoning and "reasoning_effort" in reasoning
    assert "temperature" not in model_params("o4-mini")
