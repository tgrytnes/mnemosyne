# vLLM Structured Outputs Setup

This project supports vLLM as an OpenAI-compatible LLM backend for strict JSON
outputs (schema-constrained). FastAPI can remain in place for embeddings.

## RunPod (example)

Start vLLM with a model of your choice:

```bash
vllm serve <model-id> \
  --host 0.0.0.0 \
  --port 8001 \
  --api-key "$VLLM_API_KEY"
```

## Mnemosyne env vars

```bash
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8001
VLLM_API_KEY=your_key_optional
VLLM_LLM_MODEL=<model-id>

# Strict JSON enforcement
STRICT_JSON_STEPS=semantic_chunking,cluster_profiles
ALLOW_JSON_FALLBACK=false
```

## Notes

- Strict JSON enforcement requires structured outputs. If a provider does not
  support JSON schema, Mnemosyne fails fast unless `ALLOW_JSON_FALLBACK=true`.
- FastAPI embeddings remain unchanged; configure `EMBEDDING_PROVIDER` separately.
