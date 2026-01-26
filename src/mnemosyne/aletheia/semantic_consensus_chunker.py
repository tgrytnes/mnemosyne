"""
Consensus chunking: keep boundaries where semantic and recursive agree.
"""

from __future__ import annotations

import logging

from mnemosyne.aletheia.semantic_chunker import SemanticChunker
from mnemosyne.aletheia.text_chunker import TextChunk, TextChunker

logger = logging.getLogger(__name__)


class SemanticConsensusChunker:
    """
    Run semantic + recursive chunking and keep overlapping boundaries.
    """

    def __init__(
        self,
        semantic_chunker: SemanticChunker,
        recursive_chunker: TextChunker,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        boundary_tolerance: int = 20,
    ):
        self.semantic_chunker = semantic_chunker
        self.recursive_chunker = recursive_chunker
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.boundary_tolerance = boundary_tolerance

    def chunk(self, text: str, source_file: str, structure=None) -> list[TextChunk]:
        if not text or not text.strip():
            return []

        try:
            semantic_chunks = self.semantic_chunker.chunk(text, source_file, structure=structure)
        except Exception as exc:
            logger.warning("Semantic consensus failed; falling back: %s", exc)
            return self._recursive_chunks(text, source_file, structure)

        recursive_chunks = self._recursive_chunks(text, source_file, structure)

        fallback_structure = None
        if structure is not None:
            from mnemosyne.aletheia.structure_extractor import StructureExtractor

            fallback_structure = StructureExtractor().extract_structure(text)

        if structure is not None and semantic_chunks:
            semantic_chunks = self._apply_structure_metadata(
                text, semantic_chunks, structure, fallback_structure
            )

        if not semantic_chunks:
            return recursive_chunks
        if not recursive_chunks:
            return semantic_chunks

        semantic_boundaries = self._extract_boundaries(text, semantic_chunks)
        recursive_boundaries = self._extract_boundaries(text, recursive_chunks)
        consensus = self._consensus_boundaries(semantic_boundaries, recursive_boundaries)

        heading_boundaries: list[int] = []
        if structure is not None:
            heading_boundaries = self._heading_boundaries(structure, fallback_structure, len(text))
        heading_boundary_set = set(heading_boundaries)

        if heading_boundaries:
            if consensus:
                combined = sorted(set(consensus).union(heading_boundaries))
            else:
                combined = sorted(set(semantic_boundaries).union(heading_boundaries))
            return self._chunks_from_boundaries(
                text, source_file, combined, structure, fallback_structure, heading_boundary_set
            )

        if not consensus:
            return semantic_chunks

        return self._chunks_from_boundaries(
            text, source_file, consensus, structure, fallback_structure, heading_boundary_set
        )

    def _recursive_chunks(self, text: str, source_file: str, structure=None) -> list[TextChunk]:
        if structure is not None:
            return self.recursive_chunker.chunk_with_structure(text, source_file, structure)
        return self.recursive_chunker.chunk(text, source_file)

    def _extract_boundaries(self, text: str, chunks: list[TextChunk]) -> list[int]:
        boundaries: list[int] = []
        cursor = 0
        for idx, chunk in enumerate(chunks):
            start = text.find(chunk.text, cursor)
            if start == -1:
                start = text.find(chunk.text)
            if start == -1:
                start = cursor
            if idx > 0:
                boundaries.append(start)
            cursor = max(cursor, start + len(chunk.text))
        return boundaries

    def _consensus_boundaries(self, primary: list[int], secondary: list[int]) -> list[int]:
        result: list[int] = []
        for boundary in primary:
            if any(abs(boundary - other) <= self.boundary_tolerance for other in secondary):
                result.append(boundary)
        return sorted(set(result))

    @staticmethod
    def _heading_boundaries(structure, fallback_structure, text_len: int) -> list[int]:
        active_structure = fallback_structure or structure
        if active_structure is None:
            return []
        candidates = list(getattr(active_structure, "heading_map", {}).keys())
        return sorted({pos for pos in candidates if 0 < pos < text_len})

    def _chunks_from_boundaries(
        self,
        text: str,
        source_file: str,
        boundaries: list[int],
        structure=None,
        fallback_structure=None,
        heading_boundaries: set[int] | None = None,
    ) -> list[TextChunk]:
        heading_boundaries = heading_boundaries or set()
        positions = [0] + sorted({b for b in boundaries if 0 < b < len(text)}) + [len(text)]
        segments: list[dict[str, object]] = []
        for start, end in zip(positions, positions[1:]):
            segment = text[start:end]
            stripped = segment.strip()
            if not stripped:
                continue
            leading = len(segment) - len(segment.lstrip())
            segments.append(
                {
                    "text": stripped,
                    "start": start + leading,
                    "is_heading": start in heading_boundaries,
                }
            )

        merged: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        for segment in segments:
            segment_text = str(segment["text"])
            if current is None:
                current = segment
                continue
            current_text = str(current["text"])
            if bool(current.get("is_heading")) or bool(segment.get("is_heading")):
                merged.append(current)
                current = segment
                continue
            if len(current_text) < self.min_chunk_size or len(segment_text) < self.min_chunk_size:
                combined_len = len(current_text) + len(segment_text)
                if combined_len <= self.max_chunk_size:
                    current["text"] = current_text + segment_text
                else:
                    merged.append(current)
                    current = segment
            else:
                merged.append(current)
                current = segment

        if current is not None:
            merged.append(current)

        chunks: list[TextChunk] = []
        index = 0
        for segment in merged:
            segment_text = str(segment["text"])
            segment_start = int(segment["start"])
            if len(segment_text) > self.max_chunk_size:
                fallback_chunks = self.recursive_chunker.chunk(segment_text, source_file)
                cursor = 0
                for fallback in fallback_chunks:
                    rel_start = segment_text.find(fallback.text, cursor)
                    if rel_start == -1:
                        rel_start = segment_text.find(fallback.text)
                    if rel_start == -1:
                        rel_start = cursor
                    chunks.append(
                        self._build_chunk(
                            fallback.text,
                            index,
                            source_file,
                            structure,
                            fallback_structure,
                            segment_start + rel_start,
                        )
                    )
                    index += 1
                    cursor = max(cursor, rel_start + len(fallback.text))
            else:
                chunks.append(
                    self._build_chunk(
                        segment_text,
                        index,
                        source_file,
                        structure,
                        fallback_structure,
                        segment_start,
                    )
                )
                index += 1

        return chunks

    @staticmethod
    def _build_chunk(
        text: str,
        index: int,
        source_file: str,
        structure,
        fallback_structure,
        start_pos: int,
    ) -> TextChunk:
        if structure is None:
            return TextChunk(text=text, index=index, source_file=source_file)

        heading, heading_source = _resolve_heading(start_pos, structure, fallback_structure)
        if heading and heading.level > 0:
            heading_path = heading_source.get_heading_path(heading)
            heading_level = heading.level
            section_title = heading.title
        else:
            heading_path = ""
            heading_level = 0
            section_title = ""

        return TextChunk(
            text=text,
            index=index,
            source_file=source_file,
            heading_path=heading_path,
            heading_level=heading_level,
            section_title=section_title,
        )

    def _apply_structure_metadata(
        self, text: str, chunks: list[TextChunk], structure, fallback_structure
    ) -> list[TextChunk]:
        cursor = 0
        updated: list[TextChunk] = []
        for chunk in chunks:
            start = text.find(chunk.text, cursor)
            if start == -1:
                start = text.find(chunk.text)
            if start == -1:
                start = cursor
            heading, heading_source = _resolve_heading(start, structure, fallback_structure)
            if heading and heading.level > 0:
                heading_path = heading_source.get_heading_path(heading)
                heading_level = heading.level
                section_title = heading.title
            else:
                heading_path = ""
                heading_level = 0
                section_title = ""

            updated.append(
                TextChunk(
                    text=chunk.text,
                    index=chunk.index,
                    source_file=chunk.source_file,
                    heading_path=heading_path,
                    heading_level=heading_level,
                    section_title=section_title,
                )
            )
            cursor = max(cursor, start + len(chunk.text))

        return updated


def _resolve_heading(start_pos: int, structure, fallback_structure):
    heading = structure.get_heading_at_pos(start_pos)
    if heading and heading.level > 0:
        return heading, structure
    if fallback_structure is not None:
        fallback_heading = fallback_structure.get_heading_at_pos(start_pos)
        if fallback_heading and fallback_heading.level > 0:
            return fallback_heading, fallback_structure
    return None, structure
