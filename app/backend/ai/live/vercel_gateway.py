"""Live AI gateway — Vercel AI Gateway (OpenAI-compatible) ActionGateway impl.

Calls ``https://ai-gateway.vercel.sh/v1`` with provider failover (Groq → Bedrock by
default, both serving ``meta/llama-3.3-70b``). A thin ``httpx`` port of the eamos gateway
broker, adapted to the :class:`ai.gateway.ActionGateway` Protocol (``model_id`` /
``propose`` / ``explain``).

Provider-agnostic by construction: the Vercel gateway routes by the model-id string, so
swapping ``ai_gateway_model`` (``meta/llama-3.3-70b`` → ``openai/gpt-4o`` → ``anthropic/…``)
changes the model/provider with **zero code change here** — the launch swap the owner asked
for. Nothing is Anthropic-locked.

Degrade-clean in both directions (mirrors :class:`PydanticAIGateway`): any error — network,
auth, timeout, retryable status exhausted, empty / unparseable body — makes ``explain`` return
the deterministic fallback and ``propose`` return an empty plan, never raising into the loop.
The deterministic core is never on the AI's critical path.
"""

from __future__ import annotations

import json as _json
import logging
import time
from typing import TYPE_CHECKING, Callable

import httpx

from ai.models import ActionContext, ActionPlan

if TYPE_CHECKING:  # pragma: no cover - typing only
    from config import Settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_EXPLAIN_SYSTEM = (
    "You are an analytical explainer.  You explain or suggest based ONLY on the "
    "structured data provided — you never fabricate analytical results or values. "
    "Be concise (≤120 words)."
)

# Appended to the closed-vocabulary action system prompt for the JSON-only propose path.
_JSON_INSTRUCTION = (
    '\n\nReturn ONLY a JSON object, no prose, no markdown fences:\n'
    '{"actions": [{"type": "...", "target": "...", "payload": {...}, "rationale": "..."}], '
    '"notes": "..."}\n'
    "An empty actions list is valid when nothing in the closed vocabulary applies."
)


class GatewayError(RuntimeError):
    """Raised internally when the gateway cannot serve a request after retries."""


def _extract_json_object(raw: str) -> dict:
    """Parse a JSON object from a model completion, tolerating fences / surrounding prose.

    Tries a direct parse first; on failure, slices the first ``{`` … last ``}`` span and
    parses that. Raises on anything that still isn't a JSON object so the caller degrades
    to an empty plan rather than acting on garbage.
    """
    raw = (raw or "").strip()
    try:
        obj = _json.loads(raw)
    except _json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise GatewayError("no JSON object in completion") from None
        obj = _json.loads(raw[start : end + 1])
    if not isinstance(obj, dict):
        raise GatewayError("completion JSON is not an object")
    return obj


class VercelAIGateway:
    """Live gateway over the Vercel AI Gateway. Implements the ``ActionGateway`` Protocol."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        provider_order: list[str],
        temperature: float = 0.3,
        max_tokens: int = 700,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model_id = model  # stamped into provenance for every proposed action
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._provider_order = list(provider_order)
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._transport = transport
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: "Settings", **overrides) -> "VercelAIGateway":
        """Build from app settings (the production path). ``overrides`` aid testing."""
        kwargs = dict(
            api_key=settings.ai_gateway_api_key or "",
            model=settings.ai_gateway_model,
            base_url=settings.ai_gateway_base_url,
            provider_order=settings.ai_gateway_provider_order,
            temperature=settings.ai_gateway_temperature,
            max_tokens=settings.ai_gateway_max_tokens,
            timeout_s=settings.ai_timeout_s,
        )
        kwargs.update(overrides)
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # ActionGateway API
    # ------------------------------------------------------------------

    def explain(self, request_type: str, data: dict, goal: str) -> str:
        """Return AI-generated explanatory text grounded in ``data`` (degrade-clean)."""
        from ai.gateway import _deterministic_explain

        try:
            text = self._chat(
                [
                    {"role": "system", "content": _EXPLAIN_SYSTEM},
                    {"role": "user", "content": self._explain_user_prompt(request_type, data, goal)},
                ],
                max_tokens=min(self._max_tokens, 400),
            ).strip()
            # An empty completion is a degrade, not an answer — fall back so `source` reads
            # "deterministic" (the FE ✨ only lights up when text != the deterministic summary).
            return text or _deterministic_explain(request_type, data, goal)
        except Exception:  # noqa: BLE001 — degrade clean, never propagate AI errors
            return _deterministic_explain(request_type, data, goal)

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        """Translate goal + context into a validated ``ActionPlan`` (degrade-clean)."""
        try:
            return self._propose_inner(context, goal)
        except Exception:  # noqa: BLE001 — degrade clean to an empty plan
            return ActionPlan(goal=goal, actions=[])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _explain_user_prompt(request_type: str, data: dict, goal: str) -> str:
        return "\n".join(
            [
                f"Request: {request_type}",
                f"Goal: {goal}",
                f"Data: {_json.dumps(data, indent=2)}",
            ]
        )

    def _propose_inner(self, context: ActionContext, goal: str) -> ActionPlan:
        # Lazy import: reuse the closed-vocabulary system prompt, the bounded prompt builder,
        # the validated ProposedPlan, and the canonical mapper from the pydantic gateway.
        from ai.live.pydantic_gateway import (
            ProposedPlan,
            PydanticAIGateway,
            _SYSTEM_PROMPT,
            build_action_prompt,
        )

        raw = self._chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT + _JSON_INSTRUCTION},
                {"role": "user", "content": build_action_prompt(context, goal)},
            ],
            max_tokens=self._max_tokens,
        )
        payload = _extract_json_object(raw)
        proposed = ProposedPlan.model_validate(payload)  # ActionType Literal guard re-applied here
        return PydanticAIGateway._map_plan(goal, proposed)

    def _chat(self, messages: list[dict[str, str]], *, max_tokens: int) -> str:
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": max_tokens,
            "providerOptions": {"gateway": {"order": self._provider_order}},
        }
        with httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout_s,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            transport=self._transport,
        ) as client:
            response = self._send_with_retry(client, body)
            try:
                data = response.json()
            finally:
                response.close()
        choices = data.get("choices") or [{}]
        return (choices[0].get("message") or {}).get("content") or ""

    def _send_with_retry(self, client: httpx.Client, body: dict) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = client.post("/chat/completions", json=body)
            except httpx.TransportError as exc:
                last_error = exc
                self._backoff(attempt)
                continue
            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries - 1:
                response.close()
                self._backoff(attempt)
                continue
            if response.status_code >= 400:
                detail = response.text[:300]
                response.close()
                raise GatewayError(f"AI Gateway returned {response.status_code}: {detail}")
            return response
        raise GatewayError(f"AI Gateway unreachable after {self._max_retries} attempts: {last_error}")

    def _backoff(self, attempt: int) -> None:
        self._sleep(self._backoff_base_seconds * (2**attempt))
