"""
Generic LLM Provider pour PydanticAI avec support complet des function calls/tools.
Compatible avec toute API OpenAI-like (Mistral, Chocolatine, Ollama, LiteLLM, etc.).
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Iterable

import httpx
from pydantic_ai.models import AgentModel, Model, StreamTextResponse
from pydantic_ai.messages import (
    ArgsDict,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.result import Usage
from pydantic_ai.tools import ToolDefinition

logger = logging.getLogger(__name__)


@dataclass
class GenericStreamTextResponse(StreamTextResponse):
    """Implementation of StreamTextResponse pour les modèles génériques OpenAI-like."""

    _first_content: str | None
    _response_lines: AsyncIterator[str]
    _timestamp: datetime
    _usage: Usage
    _buffer: list[str] = field(default_factory=list, init=False)
    _tool_calls: list[dict] = field(default_factory=list, init=False)
    _has_tool_calls: bool = field(default=False, init=False)

    async def __anext__(self) -> None:
        if self._first_content is not None:
            self._buffer.append(self._first_content)
            self._first_content = None
            return None

        line = await self._response_lines.__anext__()

        # Parser le format SSE (Server-Sent Events)
        if line.startswith("data: "):
            data_str = line[6:]

            # Ignorer les messages [DONE]
            if data_str.strip() == "[DONE]":
                raise StopAsyncIteration

            try:
                data = json.loads(data_str)

                # Debug: log the complete data
                logger.debug(f"SSE data: {json.dumps(data)}")

                # Extraire le contenu delta
                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    delta = choice.get("delta", {})

                    # Ajouter le contenu au buffer
                    if "content" in delta and delta["content"]:
                        self._buffer.append(delta["content"])

                    # Gérer les tool calls
                    if "tool_calls" in delta:
                        logger.debug(f"Tool calls detected in delta: {delta['tool_calls']}")
                        self._has_tool_calls = True
                        # Stocker les tool calls
                        for tool_call in delta["tool_calls"]:
                            # Chercher si ce tool call existe déjà (pour le streaming incrémental)
                            existing = next((tc for tc in self._tool_calls if tc.get("index") == tool_call.get("index")), None)
                            if existing:
                                # Mettre à jour les arguments de manière incrémentale
                                if "function" in tool_call and "arguments" in tool_call["function"]:
                                    if "function" not in existing:
                                        existing["function"] = {}
                                    if "arguments" not in existing["function"]:
                                        existing["function"]["arguments"] = ""
                                    existing["function"]["arguments"] += tool_call["function"]["arguments"]
                                if "id" in tool_call and "id" not in existing:
                                    existing["id"] = tool_call["id"]
                                if "function" in tool_call and "name" in tool_call["function"] and "name" not in existing.get("function", {}):
                                    if "function" not in existing:
                                        existing["function"] = {}
                                    existing["function"]["name"] = tool_call["function"]["name"]
                            else:
                                # Ajouter un nouveau tool call
                                self._tool_calls.append(tool_call.copy())

                    # Mettre à jour l'usage si disponible
                    if "usage" in data:
                        usage_data = data["usage"]
                        self._usage = Usage(
                            request_tokens=usage_data.get("prompt_tokens", 0),
                            response_tokens=usage_data.get("completion_tokens", 0),
                            total_tokens=usage_data.get("total_tokens", 0),
                        )

            except json.JSONDecodeError as e:
                logger.warning(f"Impossible de parser la ligne SSE: {line} - {e}")

        return None

    def get(self, *, final: bool = False) -> Iterable[str]:
        yield from self._buffer
        self._buffer.clear()

    def usage(self) -> Usage:
        return self._usage

    def timestamp(self) -> datetime:
        return self._timestamp


class GenericLLMAgentModel(AgentModel):
    """AgentModel générique pour LLM OpenAI-like avec support des tools."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        model_name: str,
        api_url: str,
        api_key: str,
        function_tools: list[ToolDefinition],
    ):
        self.http_client = http_client
        self.model_name = model_name
        self.chat_endpoint = f"{api_url.rstrip('/')}/v1/chat/completions"
        self.api_key = api_key
        self.function_tools = function_tools

        # Convert PydanticAI ToolDefinition to OpenAI API format
        self.openai_tools = self._convert_tools(function_tools)

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert PydanticAI tools to OpenAI API format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.parameters_json_schema,
                }
            })
        return openai_tools

    async def request(
        self, messages: list[ModelMessage], model_settings: dict | None = None
    ) -> tuple[ModelResponse, Usage]:
        """Requête non-streamée avec support des tools."""

        # Formater les messages pour l'API OpenAI
        formatted_messages = self._format_messages(messages)

        # Construire le payload
        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            **(model_settings or {}),
        }

        # Ajouter les tools si disponibles
        if self.openai_tools:
            payload["tools"] = self.openai_tools
            payload["tool_choice"] = "auto"

        # Faire la requête
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"Generic LLM API request to {self.chat_endpoint}")

        response = await self.http_client.post(
            self.chat_endpoint, json=payload, headers=headers
        )

        # Log error details if request fails
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Generic LLM API error {response.status_code}: {error_text}")

        response.raise_for_status()

        data = response.json()

        # Parser la réponse
        choice = data["choices"][0]
        message = choice["message"]

        # Créer les parts de la réponse
        parts: list = []

        # Ajouter le contenu textuel si présent
        if "content" in message and message["content"]:
            parts.append(TextPart(content=message["content"]))

        # Ajouter les tool calls si présents
        if "tool_calls" in message and message["tool_calls"]:
            for tool_call in message["tool_calls"]:
                func = tool_call["function"]
                # Parser les arguments JSON et créer un ArgsDict
                args_data = json.loads(func["arguments"])
                parts.append(
                    ToolCallPart(
                        tool_name=func["name"],
                        args=ArgsDict(args_dict=args_data),
                        tool_call_id=tool_call.get("id"),
                    )
                )

        # Créer l'usage
        usage_data = data.get("usage", {})
        usage = Usage(
            request_tokens=usage_data.get("prompt_tokens", 0),
            response_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return ModelResponse(parts=parts), usage

    @asynccontextmanager
    async def request_stream(
        self, messages: list[ModelMessage], model_settings: dict | None = None
    ):
        """Requête streamée avec support des tools."""

        # Formater les messages
        formatted_messages = self._format_messages(messages)

        # Construire le payload avec stream=True
        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "stream": True,
            **(model_settings or {}),
        }

        # Ajouter les tools si disponibles
        if self.openai_tools:
            payload["tools"] = self.openai_tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"Generic LLM API stream request to {self.chat_endpoint}")

        # Faire la requête en streaming
        async with self.http_client.stream(
            "POST", self.chat_endpoint, json=payload, headers=headers
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                logger.error(f"Generic LLM API error {response.status_code}: {error_text.decode()}")
            response.raise_for_status()

            # Créer l'itérateur de lignes
            async def line_iterator():
                async for line in response.aiter_lines():
                    if line.strip():
                        yield line

            yield GenericStreamTextResponse(
                _first_content=None,
                _response_lines=line_iterator(),
                _timestamp=datetime.now(),
                _usage=Usage(request_tokens=0, response_tokens=0, total_tokens=0),
            )

    def _format_messages(self, messages: list[ModelMessage]) -> list[dict]:
        """Convertit les messages PydanticAI au format OpenAI API."""
        formatted = []

        for msg in messages:
            if isinstance(msg, ModelRequest):
                # Message utilisateur, système, ou résultat d'outil
                for part in msg.parts:
                    if isinstance(part, SystemPromptPart):
                        formatted.append({
                            "role": "system",
                            "content": part.content,
                        })
                    elif isinstance(part, UserPromptPart):
                        formatted.append({
                            "role": "user",
                            "content": part.content,
                        })
                    elif isinstance(part, ToolReturnPart):
                        # Résultat d'un tool call
                        formatted.append({
                            "role": "tool",
                            "tool_call_id": part.tool_call_id,
                            "content": part.content,
                        })

            elif isinstance(msg, ModelResponse):
                # Message de l'assistant
                content_parts = []
                tool_calls = []

                for part in msg.parts:
                    if isinstance(part, TextPart):
                        content_parts.append(part.content)
                    elif isinstance(part, ToolCallPart):
                        # Extraire le dict depuis ArgsDict avant de sérialiser
                        args_data = part.args.args_dict if isinstance(part.args, ArgsDict) else part.args
                        tool_calls.append(
                            {
                                "id": part.tool_call_id or f"call_{len(tool_calls)}",
                                "type": "function",
                                "function": {
                                    "name": part.tool_name,
                                    "arguments": json.dumps(args_data),
                                },
                            }
                        )

                # Construire le message assistant si on a du contenu ou des tool calls
                if content_parts or tool_calls:
                    assistant_msg = {"role": "assistant"}

                    if content_parts:
                        assistant_msg["content"] = " ".join(content_parts)

                    if tool_calls:
                        assistant_msg["tool_calls"] = tool_calls

                    formatted.append(assistant_msg)

        return formatted


class GenericLLMModel(Model):
    """Modèle LLM générique pour PydanticAI (compatible OpenAI API)."""

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        api_url: str = "https://api.openai.com",
        timeout: float = 120.0,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        self.chat_endpoint = f"{self.api_url.rstrip('/')}/v1/chat/completions"
        self._http_client = httpx.AsyncClient(timeout=self.timeout)

        if not self.api_key:
            logger.warning(
                "No API key provided - this may fail for providers requiring authentication"
            )

    async def agent_model(
        self, *, function_tools: list[ToolDefinition], allow_text_result: bool, result_tools: list
    ) -> AgentModel:
        """Retourne une instance de GenericLLMAgentModel."""
        return GenericLLMAgentModel(
            http_client=self._http_client,
            model_name=self.model_name,
            api_url=self.api_url,
            api_key=self.api_key,
            function_tools=function_tools,
        )

    def name(self) -> str:
        return f"generic:{self.model_name}"


def get_generic_llm_model() -> GenericLLMModel:
    """Factory function pour créer le modèle LLM générique depuis les variables d'environnement."""
    # Support des nouvelles variables LLM_* et fallback sur anciennes MISTRAL_*
    api_url = os.getenv("LLM_API_URL") or os.getenv("MISTRAL_API_URL", "https://api.mistral.ai")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("MISTRAL_API_KEY")
    model_name = os.getenv("LLM_MODEL_NAME") or os.getenv("MISTRAL_MODEL_NAME", "mistral-small-latest")
    timeout = float(os.getenv("LLM_TIMEOUT") or os.getenv("MISTRAL_TIMEOUT", "120.0"))

    return GenericLLMModel(
        model_name=model_name,
        api_key=api_key,
        api_url=api_url,
        timeout=timeout,
    )
