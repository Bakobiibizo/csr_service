from src.csr_service.engine.prompt import build_user_prompt, get_system_prompt
from src.csr_service.schemas.standards import StandardRule


def _rule(ref="R-1", title="Title", body="Body"):
    return StandardRule(standard_ref=ref, title=title, body=body, tags=[])


class TestGetSystemPrompt:
    def test_returns_non_empty_string(self):
        prompt = get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_json_schema(self):
        prompt = get_system_prompt()
        assert '"observations"' in prompt
        assert '"severity"' in prompt
        assert '"confidence"' in prompt

    def test_contains_instructions(self):
        prompt = get_system_prompt()
        assert "raw JSON only" in prompt
        assert "standard_ref" in prompt


class TestBuildUserPrompt:
    def test_contains_rules(self):
        rules = [_rule(ref="NAV-1.1", title="Use verbs", body="Must use measurable verbs")]
        prompt = build_user_prompt("Some content", rules, "medium")
        assert "[NAV-1.1]" in prompt
        assert "Use verbs" in prompt
        assert "Must use measurable verbs" in prompt

    def test_contains_content(self):
        prompt = build_user_prompt("The student will understand.", [_rule()], "medium")
        assert "The student will understand." in prompt

    def test_contains_content_length(self):
        content = "Hello world"
        prompt = build_user_prompt(content, [_rule()], "medium")
        assert str(len(content)) in prompt

    def test_strictness_low(self):
        prompt = build_user_prompt("content", [_rule()], "low")
        assert "lenient" in prompt.lower()

    def test_strictness_high(self):
        prompt = build_user_prompt("content", [_rule()], "high")
        assert "thorough" in prompt.lower() or "strict" in prompt.lower()

    def test_strictness_medium(self):
        prompt = build_user_prompt("content", [_rule()], "medium")
        assert "standard review" in prompt.lower()

    def test_unknown_strictness_falls_back(self):
        prompt = build_user_prompt("content", [_rule()], "unknown")
        # Should not crash, falls back to medium
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_curly_braces_in_content(self):
        # Content with braces should not cause format errors
        content = 'function() { return {"key": value}; }'
        prompt = build_user_prompt(content, [_rule()], "medium")
        assert '{"key": value}' in prompt

    def test_curly_braces_in_rule_body(self):
        rule = _rule(body='Must match pattern {name} in config')
        prompt = build_user_prompt("content", [rule], "medium")
        assert "{name}" in prompt

    def test_multiple_rules_formatted(self):
        rules = [
            _rule(ref="A-1", title="First", body="First body"),
            _rule(ref="B-2", title="Second", body="Second body"),
            _rule(ref="C-3", title="Third", body="Third body"),
        ]
        prompt = build_user_prompt("content", rules, "medium")
        assert "[A-1]" in prompt
        assert "[B-2]" in prompt
        assert "[C-3]" in prompt

    def test_empty_content(self):
        prompt = build_user_prompt("", [_rule()], "medium")
        assert "0 characters" in prompt or "length: 0" in prompt

    def test_unicode_content(self):
        content = "学生は航行の基本を理解する"
        prompt = build_user_prompt(content, [_rule()], "medium")
        assert content in prompt
