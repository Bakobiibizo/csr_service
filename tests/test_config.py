import os
import tempfile

from src.csr_service.config import (
    PolicyConfig,
    PromptsConfig,
    _apply_env_overrides,
    load_policy_config,
    load_prompts_config,
)


class TestLoadPolicyConfig:
    def test_loads_from_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("retrieval:\n  k_low: 4\n  k_medium: 8\n  k_high: 12\n")
            f.flush()
            config = load_policy_config(f.name)
        os.unlink(f.name)

        assert config.retrieval.k_low == 4
        assert config.retrieval.k_medium == 8
        assert config.retrieval.k_high == 12

    def test_missing_file_uses_defaults(self):
        config = load_policy_config("/nonexistent/path/policy.yaml")
        assert config.retrieval.k_low == 6
        assert config.retrieval.k_medium == 10
        assert config.retrieval.k_high == 14
        assert config.thresholds.violation_low == 0.85
        assert config.defaults.min_confidence == 0.55

    def test_partial_yaml_merges_with_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("retrieval:\n  k_low: 3\n")
            f.flush()
            config = load_policy_config(f.name)
        os.unlink(f.name)

        assert config.retrieval.k_low == 3
        # Other fields keep defaults
        assert config.retrieval.k_medium == 10
        assert config.thresholds.violation_low == 0.85

    def test_empty_yaml_uses_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            config = load_policy_config(f.name)
        os.unlink(f.name)

        assert config.retrieval.k_low == 6

    def test_k_by_strictness_property(self):
        config = PolicyConfig()
        assert config.retrieval.k_by_strictness == {"low": 6, "medium": 10, "high": 14}

    def test_thresholds_by_strictness_property(self):
        config = PolicyConfig()
        assert config.thresholds.by_strictness == {
            "low": 0.85,
            "medium": 0.75,
            "high": 0.70,
        }


class TestApplyEnvOverrides:
    def test_overrides_int_value(self, monkeypatch):
        monkeypatch.setenv("CSR_POLICY_RETRIEVAL_K_LOW", "20")
        data = {"retrieval": {"k_low": 6, "k_medium": 10}}
        result = _apply_env_overrides(data)
        assert result["retrieval"]["k_low"] == 20

    def test_overrides_float_value(self, monkeypatch):
        monkeypatch.setenv("CSR_POLICY_THRESHOLDS_VIOLATION_LOW", "0.95")
        data = {"thresholds": {"violation_low": 0.85}}
        result = _apply_env_overrides(data)
        assert result["thresholds"]["violation_low"] == 0.95

    def test_overrides_string_value(self, monkeypatch):
        monkeypatch.setenv("CSR_POLICY_CUSTOM_NAME", "test")
        data = {"custom": {"name": "default"}}
        result = _apply_env_overrides(data)
        assert result["custom"]["name"] == "test"

    def test_ignores_non_dict_sections(self):
        data = {"version": "1.0", "retrieval": {"k_low": 6}}
        # Should not crash on non-dict value
        result = _apply_env_overrides(data)
        assert result["version"] == "1.0"

    def test_no_env_preserves_original(self):
        data = {"retrieval": {"k_low": 6}}
        result = _apply_env_overrides(data)
        assert result["retrieval"]["k_low"] == 6


class TestLoadPromptsConfig:
    def test_loads_from_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write('system_prompt: "Custom system prompt"\n')
            f.write('rule_format: "* {standard_ref}: {title}"\n')
            f.flush()
            config = load_prompts_config(f.name)
        os.unlink(f.name)

        assert config.system_prompt == "Custom system prompt"
        assert config.rule_format == "* {standard_ref}: {title}"

    def test_missing_file_uses_defaults(self):
        config = load_prompts_config("/nonexistent/prompts.yaml")
        assert "content standards reviewer" in config.system_prompt
        assert "{rules_text}" in config.user_prompt_template
        assert "medium" in config.strictness_instructions

    def test_partial_yaml_merges_with_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                "strictness_instructions:\n  low: Custom low message\n  medium: Custom medium\n  high: Custom high\n"
            )
            f.flush()
            config = load_prompts_config(f.name)
        os.unlink(f.name)

        assert config.strictness_instructions["low"] == "Custom low message"
        # system_prompt still defaults
        assert "content standards reviewer" in config.system_prompt

    def test_valid_severities_default(self):
        config = PromptsConfig()
        assert "info" in config.valid_severities
        assert "warning" in config.valid_severities
        assert "violation" in config.valid_severities

    def test_valid_categories_default(self):
        config = PromptsConfig()
        assert "clarity" in config.valid_categories
        assert "pedagogy" in config.valid_categories
        assert "other" in config.valid_categories

    def test_custom_severities_from_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("valid_severities:\n  - low\n  - medium\n  - high\n  - critical\n")
            f.flush()
            config = load_prompts_config(f.name)
        os.unlink(f.name)

        assert config.valid_severities == ["low", "medium", "high", "critical"]

    def test_custom_categories_from_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("valid_categories:\n  - safety\n  - performance\n  - other\n")
            f.flush()
            config = load_prompts_config(f.name)
        os.unlink(f.name)

        assert "safety" in config.valid_categories
        assert "performance" in config.valid_categories
