#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def _load_schema(schema_path: str | None) -> dict:
    if not schema_path:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "summary": {"type": "string"},
            },
            "required": ["ok", "summary"],
            "additionalProperties": False,
        }
    data = json.loads(Path(schema_path).read_text())
    return data.get("schema", data)


def _request(base_url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a strict JSON test against a vLLM server.")
    parser.add_argument("input_file", help="Path to a text/markdown file.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("VLLM_BASE_URL", "http://127.0.0.1:18888"),
        help="vLLM base URL (default: http://127.0.0.1:18888).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("VLLM_LLM_MODEL", "NousResearch/Hermes-2-Pro-Mistral-7B"),
        help="Model ID served by vLLM.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Max tokens for the completion.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="How many times to run the request.",
    )
    parser.add_argument(
        "--schema-file",
        help=(
            "Optional JSON schema file. If it contains a top-level 'schema' key, "
            "that value is used."
        ),
    )
    parser.add_argument(
        "--prompt",
        default="Return only JSON with keys: ok (bool), summary (string).",
        help="Instruction prefix for the model.",
    )
    args = parser.parse_args()

    text = Path(args.input_file).read_text()
    schema = _load_schema(args.schema_file)

    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": f"{args.prompt}\n\nTEXT:\n{text}",
            }
        ],
        "guided_json": schema,
        "max_tokens": args.max_tokens,
    }

    for i in range(args.iterations):
        try:
            response = _request(args.base_url, payload)
        except Exception as exc:
            print(f"[{i + 1}] request failed: {exc}", file=sys.stderr)
            return 1

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        print(f"\n=== iteration {i + 1} ===")
        print(content)
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            print(f"[{i + 1}] invalid JSON: {exc}", file=sys.stderr)
            return 2

    print("\nOK: JSON parsed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
