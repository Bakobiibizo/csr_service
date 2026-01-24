"""Application configuration via environment variables and YAML.

All service settings are prefixed with CSR_ and can be overridden via
environment variables (e.g. CSR_MODEL_ID=gemma3:27b).

Policy config is loaded from a YAML file with environment override support.
Priority: environment variables > YAML file > code defaults.
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings

load_dotenv()

ENV_PREFIX = "CSR_POLICY_"


class RetrievalConfig(BaseModel):
    k_low: int = 6
    k_medium: int = 10
    k_high: int = 14

    @property
    def k_by_strictness(self) -> dict[str, int]:
        return {"low": self.k_low, "medium": self.k_medium, "high": self.k_high}


class ThresholdsConfig(BaseModel):
    violation_low: float = 0.85
    violation_medium: float = 0.75
    violation_high: float = 0.70

    @property
    def by_strictness(self) -> dict[str, float]:
        return {"low": self.violation_low, "medium": self.violation_medium, "high": self.violation_high}


class DefaultsConfig(BaseModel):
    min_confidence: float = 0.55
    max_observations: int = 25


class PolicyConfig(BaseModel):
    retrieval: RetrievalConfig = RetrievalConfig()
    thresholds: ThresholdsConfig = ThresholdsConfig()
    defaults: DefaultsConfig = DefaultsConfig()


_DEFAULT_SYSTEM_PROMPT = """You are a content standards reviewer. You analyze instructional content against provided standards rules and return structured observations.

You MUST respond with raw JSON only. No markdown, no code fences, no explanation text.

Your response must match this exact schema:
{
  "observations": [
    {
      "span": [start_char, end_char] or null,
      "severity": "info" | "warning" | "violation",
      "category": "clarity" | "accuracy" | "structure" | "accessibility" | "pedagogy" | "compliance" | "other",
      "standard_ref": "the rule's standard_ref",
      "message": "clear description of the issue",
      "suggested_fix": "how to fix it" or null,
      "rationale": "why this is an issue per the standard" or null,
      "standard_excerpt": "relevant quote from the standard" or null,
      "confidence": 0.0 to 1.0
    }
  ]
}

Rules for observations:
- span must be [start, end] character offsets into the content where 0 <= start < end <= content_length, or null if not locatable
- severity: "violation" for clear breaches, "warning" for likely issues, "info" for suggestions
- confidence: how certain you are this is a real issue (0.0-1.0)
- standard_ref must exactly match one of the provided rules' standard_ref values
- Only report genuine issues. Do not fabricate problems.
- If the content fully complies with all provided rules, return {"observations": []}
"""

_DEFAULT_USER_PROMPT_TEMPLATE = """## Standards Rules

{rules_text}

## Strictness

{strictness_instruction}

## Content to Review (length: {content_length} characters)

{content}

## Instructions

Review the content above against the provided standards rules. Return your observations as JSON.
"""


class PromptsConfig(BaseModel):
    system_prompt: str = _DEFAULT_SYSTEM_PROMPT
    user_prompt_template: str = _DEFAULT_USER_PROMPT_TEMPLATE
    rule_format: str = "- [{standard_ref}] {title}: {body}"
    strictness_instructions: dict[str, str] = {
        "low": "Be lenient. Only flag clear, unambiguous issues.",
        "medium": "Apply standard review criteria.",
        "high": "Be thorough and strict. Flag any potential issue, even minor ones.",
    }
    valid_severities: list[str] = ["info", "warning", "violation"]
    valid_categories: list[str] = [
        "clarity", "accuracy", "structure", "accessibility",
        "pedagogy", "compliance", "other",
    ]


def _apply_env_overrides(data: dict) -> dict:
    """Override flat YAML values with CSR_POLICY_<SECTION>_<KEY> env vars."""
    for section_name, section in data.items():
        if not isinstance(section, dict):
            continue
        for key in section:
            env_key = f"{ENV_PREFIX}{section_name.upper()}_{key.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                # Coerce to the same type as the existing value
                existing = section[key]
                if isinstance(existing, int):
                    section[key] = int(env_val)
                elif isinstance(existing, float):
                    section[key] = float(env_val)
                else:
                    section[key] = env_val
    return data


def load_prompts_config(config_path: str = "config/prompts.yaml") -> PromptsConfig:
    """Load prompt templates from YAML, fall back to code defaults."""
    path = Path(config_path)
    data: dict = {}

    if path.exists():
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}

    return PromptsConfig.model_validate(data)


def load_policy_config(config_path: str = "config/policy.yaml") -> PolicyConfig:
    """Load policy config from YAML, apply env overrides, fall back to defaults."""
    path = Path(config_path)
    data: dict = {}

    if path.exists():
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}

    data = _apply_env_overrides(data)
    return PolicyConfig.model_validate(data)


class Settings(BaseSettings):
    """CSR Service configuration. All fields map to CSR_<FIELD_NAME> env vars."""

    model_config = {"env_prefix": "CSR_"}

    ollama_base_url: str = "http://localhost:11435/v1"
    model_id: str = "llama3"
    model_api_key: str = "ollama"
    model_timeout: float = 30.0
    model_temperature: float = 0.1
    model_json_mode: bool = True
    standards_dir: str = "standards"
    auth_token: str = "demo-token"
    max_content_length: int = 50000
    policy_version: str = "1.0.0"
    policy_config_path: str = "config/policy.yaml"
    prompts_config_path: str = "config/prompts.yaml"
    cors_origins: str = "*"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 9020


settings = Settings()
policy_config = load_policy_config(settings.policy_config_path)
prompts_config = load_prompts_config(settings.prompts_config_path)

if __name__ == "__main__":
    print(settings)
    print(policy_config.model_dump())
