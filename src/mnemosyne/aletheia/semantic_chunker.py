"""
Semantic chunking using LLM boundary detection.
"""

import hashlib
import json
import logging
import math
import os
import re

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.text_chunker import TextChunk, TextChunker
from mnemosyne.llm.strict_json import StrictJsonConfig, StrictJsonError
from mnemosyne.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Split text into chunks using LLM-detected topic boundaries.
    """

    BOUNDARY_VERSION = "blocks-v3"

    def __init__(
        self,
        llm_provider: LLMProvider,
        state_tracker: IngestionStateTracker | None = None,
        fallback_chunker: TextChunker | None = None,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        model: str | None = None,  # Better for semantic understanding, runs on Pi
        temperature: float = 0.1,  # Lower temperature for more consistent boundary detection
        request_timeout: float = 10.0,  # Longer timeout for larger model
        total_timeout: float = 60.0,
        json_max_chars: int | None = 12000,
        json_max_tokens: int | None = 512,
        json_max_prompt_tokens: int | None = 16000,
    ):
        self.llm_provider = llm_provider
        self.state_tracker = state_tracker
        self.fallback_chunker = fallback_chunker or TextChunker()
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.model = model or os.getenv("SEMANTIC_LLM_MODEL", "glm-4.6v-flash")
        self.temperature = temperature
        self.request_timeout = request_timeout
        self.total_timeout = total_timeout
        self.json_max_chars = json_max_chars if json_max_chars and json_max_chars > 0 else None
        self.json_max_tokens = json_max_tokens if json_max_tokens and json_max_tokens > 0 else None
        self.json_max_prompt_tokens = (
            json_max_prompt_tokens
            if json_max_prompt_tokens and json_max_prompt_tokens > 0
            else None
        )
        self._last_json_skip_reason: str | None = None

    def chunk(self, text: str, source_file: str, structure=None) -> list[TextChunk]:
        """
        Chunk text using LLM boundaries with fallback to recursive splitting.
        """
        if not text or not text.strip():
            return []

        if len(text) <= self.min_chunk_size:
            return [TextChunk(text=text, index=0, source_file=source_file)]

        cache_key = self._cache_key(text)
        boundaries = self._get_cached_boundaries(cache_key)

        if boundaries is None:
            try:
                boundaries = self._identify_boundaries(text, source_file)
                self._cache_boundaries(cache_key, boundaries)
            except StrictJsonError as exc:
                logger.error("Semantic chunking strict JSON failed: %s", exc)
                raise
            except Exception as exc:
                logger.warning("Semantic chunking failed, falling back: %s", exc)
                return self.fallback_chunker.chunk(text, source_file)

        return self._chunks_from_boundaries(text, source_file, boundaries)

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return (
            f"{self.BOUNDARY_VERSION}:{self.model}:{self.min_chunk_size}:"
            f"{self.max_chunk_size}:{digest}"
        )

    def _get_cached_boundaries(self, cache_key: str) -> list[int] | None:
        if not self.state_tracker:
            return None
        return self.state_tracker.get_cached_semantic_boundaries(cache_key)

    def _cache_boundaries(self, cache_key: str, boundaries: list[int]) -> None:
        if not self.state_tracker:
            return
        self.state_tracker.cache_semantic_boundaries(
            cache_key=cache_key,
            boundaries=boundaries,
            model=self.model,
            min_chunk_size=self.min_chunk_size,
            max_chunk_size=self.max_chunk_size,
        )

    def _identify_boundaries(self, text: str, source_file: str) -> list[int]:
        boundaries = self._request_boundary_json(text)
        if boundaries is not None:
            return boundaries
        if self._last_json_skip_reason == "too_large":
            return self._boundaries_from_fallback(text, source_file)

        # If JSON failed for any other reason, avoid the per-sentence LLM loop and
        # fall back to deterministic chunking instead.
        return self._boundaries_from_fallback(text, source_file)

    def _request_boundary_json(self, text: str) -> list[int] | None:
        self._last_json_skip_reason = None
        blocks = self._build_blocks(text)
        if len(blocks) <= 1:
            return []
        if len(blocks) > 200 or (self.json_max_chars and len(text) > self.json_max_chars):
            return self._request_boundary_json_chunked(text, blocks)

        block_list = self._format_blocks(blocks)
        if self.json_max_prompt_tokens:
            prompt_tokens = self._estimate_prompt_tokens(
                self._build_prompt(block_list, len(blocks), len(text))
            )
            if prompt_tokens > self.json_max_prompt_tokens:
                return self._request_boundary_json_chunked(text, blocks)

        return self._request_boundary_json_single(text, blocks, block_list=block_list)

    def _request_boundary_json_chunked(
        self, text: str, blocks: list[dict[str, object]]
    ) -> list[int] | None:
        self._last_json_skip_reason = "too_large"
        max_chars = self.json_max_chars or 12000
        groups = self._group_blocks_by_size(blocks, max_chars)
        if not groups:
            return None

        boundaries: list[int] = []
        for start_idx, end_idx in groups:
            group_blocks = blocks[start_idx:end_idx]
            group_start = int(group_blocks[0]["start"])
            group_end = int(group_blocks[-1]["end"])
            group_text = text[group_start:group_end]
            local_blocks = self._normalize_blocks(group_blocks, group_start)
            group_boundaries = self._request_boundary_json_single(group_text, local_blocks)
            if group_boundaries is None:
                return None
            if group_start > 0:
                boundaries.append(group_start)
            boundaries.extend([group_start + b for b in group_boundaries])

        return sorted(set(boundaries))

    def _request_boundary_json_single(
        self,
        text: str,
        blocks: list[dict[str, object]],
        block_list: str | None = None,
    ) -> list[int] | None:
        target_chunks = self._estimate_target_chunks(len(text), len(blocks))
        max_boundaries = max(0, min(len(blocks) - 1, target_chunks - 1))

        strict_config = StrictJsonConfig.from_env()
        strict = strict_config.is_strict("semantic_chunking")
        if strict and not self.llm_provider.supports_structured_output():
            if strict_config.allow_fallback:
                logger.warning(
                    "Structured outputs unavailable for semantic_chunking; "
                    "falling back to non-strict parsing."
                )
            else:
                raise StrictJsonError(
                    "LLM provider does not support structured output for semantic_chunking."
                )

        block_list = block_list or self._format_blocks(blocks)
        prompt = self._build_prompt(block_list, len(blocks), len(text))
        options = {"temperature": self.temperature}
        if self.json_max_tokens:
            estimated_tokens = max(64, max_boundaries * 12 + 32)
            options["max_tokens"] = min(self.json_max_tokens, estimated_tokens)
        if strict and self.llm_provider.supports_structured_output():
            options["json_schema"] = self._boundary_schema()

        response = self.llm_provider.generate(
            model=self.model,
            prompt=prompt,
            format="json" if strict else None,
            options=options,
        )
        raw = response.get("response", "")
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            if strict and not strict_config.allow_fallback:
                raise StrictJsonError("Semantic chunking returned invalid JSON.")
            return None
        boundaries = data.get("boundaries")
        if not isinstance(boundaries, list):
            if strict and not strict_config.allow_fallback:
                raise StrictJsonError("Semantic chunking JSON missing boundaries list.")
            return None
        normalized: list[int] = []
        for b in boundaries:
            if not isinstance(b, (int, float)):
                continue
            idx = int(b)
            if 0 < idx < len(blocks):
                normalized.append(idx)

        normalized = sorted(set(normalized))
        if max_boundaries and len(normalized) > max_boundaries:
            if strict and not strict_config.allow_fallback:
                raise StrictJsonError("Semantic chunking returned too many boundaries.")
            return None

        return [int(blocks[idx]["start"]) for idx in normalized]

    @staticmethod
    def _boundary_schema() -> dict[str, object]:
        return {
            "name": "semantic_boundaries",
            "schema": {
                "type": "object",
                "properties": {"boundaries": {"type": "array", "items": {"type": "integer"}}},
                "required": ["boundaries"],
                "additionalProperties": False,
            },
        }

    def _estimate_target_chunks(self, text_len: int, block_count: int) -> int:
        if text_len <= self.max_chunk_size:
            return 1
        approx = math.ceil(text_len / self.max_chunk_size)
        approx = max(1, min(approx, block_count))
        return min(approx, 12)

    def _format_blocks(self, blocks: list[dict[str, object]], max_preview_chars: int = 240) -> str:
        lines: list[str] = []
        for idx, block in enumerate(blocks):
            raw = str(block["text"]).strip()
            compact = re.sub(r"\\s+", " ", raw)
            if len(compact) > max_preview_chars:
                preview = f"{compact[:max_preview_chars].rstrip()}..."
            else:
                preview = compact
            lines.append(f"[{idx}] ({block['type']}, {len(str(block['text']))} chars) {preview}")
        return "\n".join(lines)

    def _build_prompt(self, block_list: str, block_count: int, text_len: int) -> str:
        target_chunks = self._estimate_target_chunks(text_len, block_count)
        max_boundaries = max(0, min(block_count - 1, target_chunks - 1))
        return (
            "You are splitting a document into coherent chunks using the numbered blocks below.\n"
            'Return JSON only in the form {"boundaries": [block_index, ...]}.\n'
            "Each block_index is the index of a block where a new chunk should start.\n"
            "Rules:\n"
            f"- Block indices must be integers in the range 1..{block_count - 1}.\n"
            "- Indices must be sorted and unique.\n"
            f"- Use at most {max_boundaries} boundaries.\n"
            f"- Aim for about {target_chunks} chunks overall.\n"
            f"- Keep chunk sizes between {self.min_chunk_size} and "
            f"{self.max_chunk_size} characters when possible.\n"
            "- Prefer boundaries at topic shifts or section changes; avoid splitting inside "
            "tables or code blocks.\n\n"
            "Blocks:\n"
            f"{block_list}\n"
        )

    @staticmethod
    def _estimate_prompt_tokens(prompt: str) -> int:
        # Approximate token count; avoids extra deps.
        return max(1, len(prompt) // 4)

    def _group_blocks_by_size(
        self, blocks: list[dict[str, object]], max_chars: int
    ) -> list[tuple[int, int]]:
        groups: list[tuple[int, int]] = []
        start_idx = 0
        current_len = 0
        for idx, block in enumerate(blocks):
            block_len = int(block["end"]) - int(block["start"])
            if current_len and current_len + block_len > max_chars:
                groups.append((start_idx, idx))
                start_idx = idx
                current_len = 0
            current_len += block_len
        if start_idx < len(blocks):
            groups.append((start_idx, len(blocks)))
        return groups

    @staticmethod
    def _normalize_blocks(blocks: list[dict[str, object]], offset: int) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for block in blocks:
            normalized.append(
                {
                    "start": int(block["start"]) - offset,
                    "end": int(block["end"]) - offset,
                    "text": block["text"],
                    "type": block.get("type", "paragraph"),
                }
            )
        return normalized

    def _boundaries_from_fallback(self, text: str, source_file: str) -> list[int]:
        fallback_chunks = self.fallback_chunker.chunk(text, source_file)
        if len(fallback_chunks) <= 1:
            return []
        boundaries: list[int] = []
        cursor = 0
        for idx, chunk in enumerate(fallback_chunks):
            start = text.find(chunk.text, cursor)
            if start == -1:
                start = text.find(chunk.text)
            if start == -1:
                start = cursor
            if idx > 0:
                boundaries.append(start)
            cursor = max(cursor, start + len(chunk.text))
        return boundaries

    def _build_blocks(self, text: str) -> list[dict[str, object]]:
        lines = text.splitlines(keepends=True)
        blocks: list[dict[str, object]] = []
        current_lines: list[str] = []
        current_type: str | None = None
        block_start = 0
        in_code_fence = False
        cursor = 0

        def flush() -> None:
            nonlocal current_lines, current_type, block_start
            if not current_lines:
                return
            block_text = "".join(current_lines)
            blocks.append(
                {
                    "start": block_start,
                    "end": block_start + len(block_text),
                    "text": block_text,
                    "type": current_type or "paragraph",
                }
            )
            current_lines = []
            current_type = None

        for line in lines:
            line_start = cursor
            cursor += len(line)
            stripped = line.strip()

            if in_code_fence:
                current_lines.append(line)
                if stripped.startswith("```"):
                    in_code_fence = False
                    flush()
                continue

            if stripped.startswith("```"):
                flush()
                in_code_fence = True
                current_type = "code"
                block_start = line_start
                current_lines = [line]
                continue

            if not stripped:
                flush()
                continue

            if self._is_table_line(line):
                if current_type not in (None, "table"):
                    flush()
                if current_type is None:
                    current_type = "table"
                    block_start = line_start
                current_lines.append(line)
                continue

            if self._is_list_line(line):
                if current_type not in (None, "list"):
                    flush()
                if current_type is None:
                    current_type = "list"
                    block_start = line_start
                current_lines.append(line)
                continue

            if current_type not in (None, "paragraph"):
                flush()
            if current_type is None:
                current_type = "paragraph"
                block_start = line_start
            current_lines.append(line)

        flush()
        return blocks

    @staticmethod
    def _is_table_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            return False
        if stripped.startswith("|") or stripped.endswith("|"):
            return True
        if re.match(r"^[\\s|:-]+$", stripped):
            return True
        return False

    @staticmethod
    def _is_list_line(line: str) -> bool:
        stripped = line.lstrip()
        if not stripped:
            return False
        if stripped.startswith(("-", "*", "+")) and len(stripped) > 1:
            return stripped[1].isspace()
        return bool(re.match(r"^\\d+[.)]\\s+", stripped))

    def _split_sentences(self, text: str) -> list[dict[str, int | str]]:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        results: list[dict[str, int | str]] = []
        cursor = 0
        for sentence in sentences:
            if not sentence.strip():
                continue
            start = text.find(sentence, cursor)
            if start == -1:
                continue
            end = start + len(sentence)
            results.append({"text": sentence, "start": start, "end": end})
            cursor = end
        return results

    def _has_paragraph_break(self, text: str, prev_end: int, start: int) -> bool:
        if start <= prev_end:
            return False
        return "\n\n" in text[prev_end:start]

    def _chunks_from_boundaries(
        self, text: str, source_file: str, boundaries: list[int]
    ) -> list[TextChunk]:
        positions = [0] + sorted({b for b in boundaries if 0 < b < len(text)}) + [len(text)]
        segments = [text[start:end] for start, end in zip(positions, positions[1:])]
        segments = [segment for segment in segments if segment.strip()]

        merged = []
        current = ""
        for segment in segments:
            if not current:
                current = segment
                continue

            if len(current) < self.min_chunk_size or len(segment) < self.min_chunk_size:
                current += segment
            else:
                merged.append(current)
                current = segment

        if current:
            merged.append(current)

        chunks: list[TextChunk] = []
        index = 0
        for segment in merged:
            if len(segment) > self.max_chunk_size and self.fallback_chunker:
                fallback_chunks = self.fallback_chunker.chunk(segment, source_file)
                for fallback_chunk in fallback_chunks:
                    chunks.append(
                        TextChunk(
                            text=fallback_chunk.text,
                            index=index,
                            source_file=source_file,
                        )
                    )
                    index += 1
            else:
                chunks.append(TextChunk(text=segment, index=index, source_file=source_file))
                index += 1

        return chunks
