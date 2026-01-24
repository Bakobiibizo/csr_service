"""Prompt construction for the review model.

Loads system and user prompt templates from config/prompts.yaml.
Templates use {placeholder} syntax for variable substitution.
Priority: YAML file > code defaults.
"""

from ..config import prompts_config
from ..schemas.standards import StandardRule


def get_system_prompt() -> str:
    return prompts_config.system_prompt


def build_user_prompt(
    content: str,
    rules: list[StandardRule],
    strictness: str,
) -> str:
    rules_text = "\n".join(
        prompts_config.rule_format.format(
            standard_ref=r.standard_ref, title=r.title, body=r.body
        )
        for r in rules
    )

    strictness_instruction = prompts_config.strictness_instructions.get(
        strictness, prompts_config.strictness_instructions.get("medium", "")
    )

    # Use simple string replacement instead of str.format() to avoid
    # failures when content or rule bodies contain curly braces
    prompt = prompts_config.user_prompt_template
    prompt = prompt.replace("{rules_text}", rules_text)
    prompt = prompt.replace("{strictness_instruction}", strictness_instruction)
    prompt = prompt.replace("{content_length}", str(len(content)))
    prompt = prompt.replace("{content}", content)
    return prompt
