"""Live AI gateway package (Slice 2).

The concrete PydanticAIGateway lives in pydantic_gateway.py and is imported
lazily — the module is never touched unless the gateway is actually constructed
(SELOM_AI_GATEWAY=live + ANTHROPIC_API_KEY), so the dev fast-path carries no
pydantic_ai import cost.
"""
