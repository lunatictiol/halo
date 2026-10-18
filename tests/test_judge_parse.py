import pytest

from eval.judge import JudgeParseError, parse_verdict

ALLOWED = ("supported", "unsupported")


def test_parses_plain_json():
    assert parse_verdict('{"verdict": "supported", "reason": "ok"}', ALLOWED) == ("supported", "ok")


def test_parses_fenced_json_and_normalizes_case():
    text = '```json\n{"verdict": "Unsupported", "reason": "claims X"}\n```'
    assert parse_verdict(text, ALLOWED) == ("unsupported", "claims X")


@pytest.mark.parametrize("text", [
    "supported",
    '{"verdict": "maybe", "reason": "x"}',
    '{"reason": "no verdict"}',
    '["supported"]',
])
def test_rejects_malformed_or_out_of_vocabulary(text):
    with pytest.raises(JudgeParseError):
        parse_verdict(text, ALLOWED)
