"""Application configuration via environment variables.

All settings are prefixed with CSR_ and can be overridden via environment
variables (e.g. CSR_MODEL_ID=gemma3:27b).
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """CSR Service configuration. All fields map to CSR_<FIELD_NAME> env vars."""

    model_config = {"env_prefix": "CSR_"}

    ollama_base_url: str = "http://localhost:11435/v1"
    model_id: str = "llama3"
    model_timeout: float = 30.0
    standards_dir: str = "standards"
    auth_token: str = "demo-token"
    max_content_length: int = 50000
    policy_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 9020


settings = Settings()
