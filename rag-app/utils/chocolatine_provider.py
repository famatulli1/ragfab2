"""
Provider personnalisé pour Chocolatine-2-14B via API FastAPI
Compatible avec PydanticAI
"""

import os
import httpx
import logging
from typing import AsyncIterator, Optional, Union
from pydantic_ai.models import Model, AgentModel, KnownModelName
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
    SystemPromptPart,
)
from pydantic_ai.result import Usage
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ChocolatineAgentModel(AgentModel):
    """AgentModel pour Chocolatine avec support des tools"""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        model_name: str,
        chat_endpoint: str,
        api_key: Optional[str],
        allow_text_result: bool,
        tools: list,
    ):
        self.http_client = http_client
        self.model_name = model_name
        self.chat_endpoint = chat_endpoint
        self.api_key = api_key
        self.allow_text_result = allow_text_result
        self.tools = tools

    async def request(
        self, messages: list[ModelMessage], model_settings: Optional[ModelSettings]
    ) -> tuple[ModelResponse, Usage]:
        """Execute a request with tools support"""
        # Format messages
        formatted_messages = self._format_messages(messages)

        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Prepare payload
        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False,
        }

        # Add tools if available
        if self.tools:
            payload["tools"] = self.tools

        try:
            response = await self.http_client.post(
                self.chat_endpoint,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()

            # Extract response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extract usage
            usage_data = result.get("usage", {})
            usage = Usage(
                request_tokens=usage_data.get("prompt_tokens", 0),
                response_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            return ModelResponse(parts=[TextPart(content=content)]), usage

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in Chocolatine request: {e}")
            raise

    def _format_messages(self, messages: list[ModelMessage]) -> list[dict]:
        """Convert PydanticAI messages to OpenAI format"""
        formatted = []

        for msg in messages:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, SystemPromptPart):
                        formatted.append({"role": "system", "content": part.content})
                    elif isinstance(part, UserPromptPart):
                        formatted.append({"role": "user", "content": part.content})
            elif isinstance(msg, ModelResponse):
                content = ""
                for part in msg.parts:
                    if isinstance(part, TextPart):
                        content += part.content
                if content:
                    formatted.append({"role": "assistant", "content": content})

        return formatted


class ChocolatineModel(Model):
    """
    Modèle personnalisé pour Chocolatine-2-14B via API FastAPI
    Compatible avec l'interface PydanticAI
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = "chocolatine-2-14b",
        timeout: float = 120.0,
    ):
        """
        Initialize Chocolatine model

        Args:
            api_url: URL de l'API (ex: https://apigpt.mynumih.fr)
            api_key: Clé API si nécessaire
            model_name: Nom du modèle
            timeout: Timeout des requêtes en secondes
        """
        self.api_url = api_url or os.getenv("CHOCOLATINE_API_URL", "https://apigpt.mynumih.fr")
        self.api_key = api_key or os.getenv("CHOCOLATINE_API_KEY", "")
        self.model_name = model_name
        self.timeout = timeout

        # Endpoint pour chat completion
        self.chat_endpoint = f"{self.api_url.rstrip('/')}/v1/chat/completions"

        # HTTP client for agent model
        self._http_client = httpx.AsyncClient(timeout=self.timeout)

        logger.info(f"Chocolatine model initialized with API: {self.api_url}")

    def name(self) -> Union[KnownModelName, str]:
        """Retourne le nom du modèle"""
        return self.model_name

    async def agent_model(
        self,
        *,
        function_tools: list[ToolDefinition],
        allow_text_result: bool,
        result_tools: list[ToolDefinition],
    ) -> AgentModel:
        """Create an agent model with tools support"""
        # Convert tool definitions if needed
        tools = []
        # For now, we'll pass tools as-is
        # You may need to convert ToolDefinition to OpenAI format here

        return ChocolatineAgentModel(
            http_client=self._http_client,
            model_name=self.model_name,
            chat_endpoint=self.chat_endpoint,
            api_key=self.api_key,
            allow_text_result=allow_text_result,
            tools=tools,
        )

    async def request(
        self, messages: list[ModelMessage]
    ) -> ModelResponse:
        """
        Effectue une requête au modèle (sans streaming)

        Args:
            messages: Liste des messages de conversation

        Returns:
            Réponse du modèle
        """
        # Convertir les messages PydanticAI au format OpenAI
        formatted_messages = self._format_messages(messages)

        # Préparer les headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Préparer le payload
        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.chat_endpoint,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

            # Extraire la réponse
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extraire l'usage si disponible
            usage_data = result.get("usage", {})
            usage = Usage(
                request_tokens=usage_data.get("prompt_tokens", 0),
                response_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            return ModelResponse(
                parts=[TextPart(content=content)],
                usage=usage,
            )

        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors de la requête à Chocolatine: {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la requête à Chocolatine: {e}")
            raise

    async def request_stream(
        self, messages: list[ModelMessage]
    ) -> AsyncIterator[ModelResponse]:
        """
        Effectue une requête au modèle avec streaming

        Args:
            messages: Liste des messages de conversation

        Yields:
            Réponses du modèle en streaming
        """
        # Convertir les messages
        formatted_messages = self._format_messages(messages)

        # Préparer les headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Préparer le payload
        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    self.chat_endpoint,
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()

                    # Parser le stream SSE
                    async for line in response.aiter_lines():
                        if not line.strip() or line.startswith(":"):
                            continue

                        if line.startswith("data: "):
                            data = line[6:]  # Enlever "data: "

                            if data.strip() == "[DONE]":
                                break

                            try:
                                import json
                                chunk = json.loads(data)

                                # Extraire le contenu du delta
                                delta_content = (
                                    chunk.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )

                                if delta_content:
                                    yield ModelResponse(
                                        parts=[TextPart(content=delta_content)]
                                    )

                            except json.JSONDecodeError:
                                logger.warning(f"Impossible de parser le chunk JSON: {data}")
                                continue

        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors du streaming Chocolatine: {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur lors du streaming Chocolatine: {e}")
            raise

    def _format_messages(self, messages: list[ModelMessage]) -> list[dict]:
        """
        Convertit les messages PydanticAI au format OpenAI

        Args:
            messages: Messages PydanticAI

        Returns:
            Messages au format OpenAI
        """
        formatted = []

        for msg in messages:
            if isinstance(msg, ModelRequest):
                # Message utilisateur ou système
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
            elif isinstance(msg, ModelResponse):
                # Message assistant
                content = ""
                for part in msg.parts:
                    if isinstance(part, TextPart):
                        content += part.content

                if content:
                    formatted.append({
                        "role": "assistant",
                        "content": content,
                    })

        return formatted


def get_chocolatine_model(
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ChocolatineModel:
    """
    Factory function pour créer un modèle Chocolatine

    Args:
        api_url: URL de l'API
        api_key: Clé API

    Returns:
        Instance de ChocolatineModel
    """
    return ChocolatineModel(api_url=api_url, api_key=api_key)
