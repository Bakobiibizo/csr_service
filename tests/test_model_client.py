from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.csr_service.engine.model_client import ModelClient
from src.csr_service.schemas.response import Usage


class TestModelClientInit:
    def test_uses_settings_values(self):
        with patch("src.csr_service.engine.model_client.settings") as mock_settings:
            mock_settings.ollama_base_url = "http://test:1234/v1"
            mock_settings.model_api_key = "test-key"
            mock_settings.model_timeout = 60.0
            mock_settings.model_id = "test-model"
            client = ModelClient()
            assert client.model_id == "test-model"


class TestModelClientGenerate:
    @pytest.fixture
    def mock_client(self):
        with patch("src.csr_service.engine.model_client.settings") as mock_settings:
            mock_settings.ollama_base_url = "http://localhost:11434/v1"
            mock_settings.model_api_key = "ollama"
            mock_settings.model_timeout = 30.0
            mock_settings.model_id = "llama3"
            mock_settings.model_temperature = 0.1
            mock_settings.model_json_mode = True
            client = ModelClient()
        return client

    async def test_successful_generation(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"observations": []}'
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        content, usage = await mock_client.generate("system", "user")
        assert content == '{"observations": []}'
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    async def test_empty_content_returns_empty_string(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        content, usage = await mock_client.generate("system", "user")
        assert content == ""
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0

    async def test_passes_temperature_from_settings(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "{}"
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("src.csr_service.engine.model_client.settings") as mock_settings:
            mock_settings.model_temperature = 0.7
            mock_settings.model_json_mode = True
            await mock_client.generate("sys", "usr")

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7

    async def test_json_mode_enabled(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "{}"
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("src.csr_service.engine.model_client.settings") as mock_settings:
            mock_settings.model_temperature = 0.1
            mock_settings.model_json_mode = True
            await mock_client.generate("sys", "usr")

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}

    async def test_json_mode_disabled(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "{}"
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("src.csr_service.engine.model_client.settings") as mock_settings:
            mock_settings.model_temperature = 0.1
            mock_settings.model_json_mode = False
            await mock_client.generate("sys", "usr")

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        assert "response_format" not in call_kwargs

    async def test_raises_on_api_error(self, mock_client):
        mock_client.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        with pytest.raises(Exception, match="Connection refused"):
            await mock_client.generate("system", "user")

    async def test_messages_structure(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "{}"
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("src.csr_service.engine.model_client.settings") as mock_settings:
            mock_settings.model_temperature = 0.1
            mock_settings.model_json_mode = False
            await mock_client.generate("my system prompt", "my user prompt")

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "my system prompt"}
        assert messages[1] == {"role": "user", "content": "my user prompt"}
