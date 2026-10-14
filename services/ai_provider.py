from functools import lru_cache
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionMessageParam,
)

from core.config import settings


SUPPORTED_PROVIDERS = {
    "openai",
    "openrouter",
    "groq",
    "gemini",
}


def get_ai_provider() -> str:
    """
    Return the currently selected AI provider.
    """

    provider = settings.AI_PROVIDER.strip().lower()

    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported AI provider: {provider}"
        )

    return provider


@lru_cache(maxsize=1)
def get_ai_client() -> OpenAI:
    """
    Create an OpenAI-compatible client for the
    currently selected AI provider.

    OpenRouter, Groq and Gemini expose
    OpenAI-compatible API endpoints.
    """

    provider = get_ai_provider()

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is missing."
            )

        return OpenAI(
            api_key=settings.OPENAI_API_KEY,
        )

    if provider == "openrouter":
        if not settings.OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY is missing."
            )

        return OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=(
                "https://openrouter.ai/api/v1"
            ),
        )

    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY is missing."
            )

        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=(
                "https://api.groq.com/openai/v1"
            ),
        )

    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is missing."
            )

        return OpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url=(
                "https://generativelanguage."
                "googleapis.com/v1beta/openai/"
            ),
        )

    raise ValueError(
        f"Unable to create AI client for: {provider}"
    )


def get_ai_model() -> str:
    """
    Return the configured model for the
    currently selected AI provider.
    """

    provider = get_ai_provider()

    if provider == "openai":
        model = settings.OPENAI_MODEL

    elif provider == "openrouter":
        model = settings.OPENROUTER_MODEL

    elif provider == "groq":
        model = settings.GROQ_MODEL

    elif provider == "gemini":
        model = settings.GEMINI_MODEL

    else:
        raise ValueError(
            f"Unsupported AI provider: {provider}"
        )

    model = model.strip()

    if not model:
        raise ValueError(
            "No model configured for provider: "
            f"{provider}"
        )

    return model


def extract_message_text(
    content: Any,
) -> str:
    """
    Normalize text returned by an
    OpenAI-compatible Chat Completions API.
    """

    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        content_list = cast(
            list[Any],
            content,
        )

        text_parts: list[str] = []

        for raw_item in content_list:
            if isinstance(raw_item, str):
                text_parts.append(
                    raw_item
                )
                continue

            if isinstance(raw_item, dict):
                item = cast(
                    dict[str, Any],
                    raw_item,
                )

                text_value = item.get(
                    "text"
                )

                if text_value is not None:
                    text_parts.append(
                        str(text_value)
                    )

                continue

            text_value = getattr(
                raw_item,
                "text",
                None,
            )

            if text_value is not None:
                text_parts.append(
                    str(text_value)
                )

        return "\n".join(
            text_parts
        ).strip()

    return str(content).strip()


def generate_ai_text(
    prompt: str,
) -> str:
    """
    Send a text request through the selected
    AI provider using Chat Completions.

    Supported providers:
    - OpenAI
    - OpenRouter
    - Groq
    - Gemini
    """

    client = get_ai_client()
    model = get_ai_model()

    messages: list[
        ChatCompletionMessageParam
    ] = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    if not response.choices:
        raise ValueError(
            "AI provider returned no choices."
        )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    output_text = extract_message_text(
        content
    )

    if not output_text:
        raise ValueError(
            "AI provider returned an empty response."
        )

    return output_text


def generate_ai_vision(
    prompt: str,
    image_data_urls: list[str],
) -> str:
    """
    Send a vision request through the selected
    AI provider using Chat Completions.

    The selected model must support image input.

    Supported provider connections:
    - OpenAI
    - OpenRouter
    - Groq
    - Gemini
    """

    if not image_data_urls:
        raise ValueError(
            "No images were provided for AI vision."
        )

    client = get_ai_client()
    model = get_ai_model()

    text_part: ChatCompletionContentPartTextParam = {
        "type": "text",
        "text": prompt,
    }

    content: list[
        ChatCompletionContentPartTextParam
        | ChatCompletionContentPartImageParam
    ] = [
        text_part
    ]

    for image_data_url in image_data_urls:
        image_part: (
            ChatCompletionContentPartImageParam
        ) = {
            "type": "image_url",
            "image_url": {
                "url": image_data_url,
                "detail": "high",
            },
        }

        content.append(
            image_part
        )

    messages: list[
        ChatCompletionMessageParam
    ] = [
        {
            "role": "user",
            "content": content,
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    if not response.choices:
        raise ValueError(
            "AI provider returned no choices."
        )

    content_result = (
        response
        .choices[0]
        .message
        .content
    )

    output_text = extract_message_text(
        content_result
    )

    if not output_text:
        raise ValueError(
            "AI provider returned an empty "
            "vision response."
        )

    return output_text