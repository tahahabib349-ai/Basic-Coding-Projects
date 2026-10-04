"""Google Gemini implementation of the LLM provider (google-genai SDK)."""

from __future__ import annotations

import json
import logging
import time

from ..config import get_logger, mask_secret, settings
from ..errors import (
    InvalidAPIKeyError,
    LLMError,
    LLMResponseError,
    MissingAPIKeyError,
    RateLimitError,
)
from .base import LLMProvider, LLMResult

log = get_logger()
logging.getLogger("google_genai").setLevel(logging.ERROR)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None, model: str | None = None):
        if not api_key:
            raise MissingAPIKeyError(
                "No Gemini API key is configured. Add your key in the sidebar, or "
                "save it in the .env file as GEMINI_API_KEY=your-key (see README), "
                "or switch on Demo mode to try the app without AI."
            )
        from google import genai
        from google.genai import types

        self._types = types
        self.model = model or settings.gemini_model
        self._key_hint = mask_secret(api_key)
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=settings.request_timeout_s * 1000),
        )

    # ------------------------------------------------------------------
    def _call(self, contents: str, config) -> object:
        from google.genai import errors as gerrors

        delay = 4.0
        for attempt in range(settings.max_retries + 1):
            try:
                return self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except gerrors.ClientError as exc:  # 4xx
                code = getattr(exc, "code", None)
                text = str(exc)
                if code == 429 and attempt < settings.max_retries:
                    log.info("Gemini rate limit hit; retrying in %.0fs", delay)
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise self._translate_client_error(code, text) from None
            except gerrors.ServerError as exc:  # 5xx, e.g. overloaded
                if attempt < settings.max_retries:
                    log.info("Gemini server error %s; retrying in %.0fs", exc.code, delay)
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise LLMError(
                    "Gemini's servers are temporarily unavailable or overloaded. "
                    "Please wait a minute and try again.",
                    detail=f"ServerError {getattr(exc, 'code', '')}",
                ) from None
            except Exception as exc:  # network problems, timeouts
                name = type(exc).__name__
                if "Timeout" in name and attempt < settings.max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise LLMError(
                    "Could not reach Gemini (network problem or timeout). Check your "
                    "internet connection and try again.",
                    detail=name,
                ) from None
        raise LLMError("Gemini did not respond after several attempts.")

    def _translate_client_error(self, code: int | None, text: str) -> LLMError:
        low = text.lower()
        if code == 429:
            return RateLimitError(
                "Gemini rate limit or quota reached for your API key. Wait a minute "
                "and retry, or check your quota/billing in Google AI Studio.",
                detail=f"429 (key {self._key_hint})",
            )
        if "api key not valid" in low or "api_key_invalid" in low or code in (401, 403):
            return InvalidAPIKeyError(
                f"Gemini rejected the API key ({self._key_hint}). Check that it was "
                "copied correctly and is enabled in Google AI Studio.",
                detail=f"{code}",
            )
        if code == 404 or "not found" in low:
            return LLMError(
                f"The Gemini model '{self.model}' was not found. Choose another model "
                "in the sidebar (e.g. gemini-3.5-flash or gemini-2.5-flash).",
                detail=f"{code}",
            )
        if "token" in low and ("exceed" in low or "too long" in low or "limit" in low):
            return LLMError(
                "The uploaded material is too large for a single Gemini request. "
                "Reduce the 'material sent to AI' limit in Advanced settings or upload fewer files.",
                detail=f"{code}",
            )
        return LLMError(
            "Gemini could not process the request (it reported a problem with the "
            "input). Try again, or try fewer/smaller files.",
            detail=f"{code}: {text[:300]}",
        )

    # ------------------------------------------------------------------
    def generate_json(self, *, system: str, prompt: str, schema: dict,
                      task: dict | None = None) -> LLMResult:
        t = self._types
        config = t.GenerateContentConfig(
            system_instruction=system,
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
            response_mime_type="application/json",
            response_json_schema=schema,
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
        )
        response = self._call(prompt, config)

        finish = ""
        try:
            finish = str(response.candidates[0].finish_reason or "")
        except Exception:
            pass
        text = getattr(response, "text", None) or ""
        if not text:
            feedback = getattr(response, "prompt_feedback", None)
            if feedback and getattr(feedback, "block_reason", None):
                raise LLMResponseError(
                    "Gemini declined to answer (content was blocked by its safety filter)."
                )
            raise LLMResponseError("Gemini returned an empty answer. Please try again.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if "MAX_TOKENS" in finish:
                raise LLMResponseError(
                    "Gemini's answer was cut off because it was too long. Try fewer "
                    "files, or raise IBA_MAX_OUTPUT_TOKENS."
                ) from None
            raise LLMResponseError(
                "Gemini's answer was not in the expected structured format. Please retry."
            ) from None

        usage = getattr(response, "usage_metadata", None)
        return LLMResult(
            data=data,
            provider=self.name,
            model=self.model,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            raw_text=text,
        )

    def test_connection(self) -> str:
        t = self._types
        config = t.GenerateContentConfig(
            temperature=0, max_output_tokens=200,
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
        )
        response = self._call("Reply with the single word: CONNECTED", config)
        reply = (getattr(response, "text", "") or "").strip()
        return f"Connected to Gemini model '{self.model}' (key {self._key_hint}). Reply: {reply[:40]!r}"
