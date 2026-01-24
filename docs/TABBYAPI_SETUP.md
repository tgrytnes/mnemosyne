# TabbyAPI Structured Outputs Setup

TabbyAPI exposes an OpenAI-compatible chat completions API. Mnemosyne can use
it for strict JSON steps (schema-constrained outputs).

## Run TabbyAPI

Start TabbyAPI with your model and enable the OpenAI-compatible API.

## Mnemosyne env vars

```bash
LLM_PROVIDER=tabbyapi
TABBYAPI_BASE_URL=http://localhost:8080
TABBYAPI_API_KEY=your_key_optional
TABBYAPI_LLM_MODEL=<model-id>

# Strict JSON enforcement
STRICT_JSON_STEPS=semantic_chunking,cluster_profiles
ALLOW_JSON_FALLBACK=false
```

## Notes

- TabbyAPI supports `response_format` with `json_schema` for structured outputs.
- Configure embeddings separately (e.g., `EMBEDDING_PROVIDER=ollama`).
