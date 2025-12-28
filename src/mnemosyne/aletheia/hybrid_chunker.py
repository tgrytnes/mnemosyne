"""
Hybrid chunking strategy: heading-based splits + semantic LLM refinement.
"""

from mnemosyne.aletheia.structure_extractor import DocumentStructure, HeadingNode
from mnemosyne.aletheia.text_chunker import TextChunk, TextChunker
from mnemosyne.aletheia.semantic_chunker import SemanticChunker


class HybridChunker:
    """
    Chunk text by heading sections, then apply semantic chunking within sections.
    """

    def __init__(
        self,
        semantic_chunker: SemanticChunker,
        recursive_chunker: TextChunker,
        section_semantic_min_length: int = 1000,
    ):
        self.semantic_chunker = semantic_chunker
        self.recursive_chunker = recursive_chunker
        self.section_semantic_min_length = section_semantic_min_length

    def chunk(
        self, text: str, source_file: str, structure: DocumentStructure | None = None
    ) -> list[TextChunk]:
        if not text or not text.strip():
            return []

        if structure is None:
            return self.semantic_chunker.chunk(text, source_file)

        sections = self._get_sections(structure, text)
        chunks: list[TextChunk] = []
        index = 0

        for section in sections:
            section_text = text[section.start_pos : section.end_pos]
            if not section_text.strip():
                continue

            if len(section_text) >= self.section_semantic_min_length:
                section_chunks = self.semantic_chunker.chunk(section_text, source_file)
            else:
                section_chunks = [
                    TextChunk(text=section_text, index=0, source_file=source_file)
                ]

            heading_path, heading_level, section_title = self._heading_metadata(
                structure, section
            )
            for chunk in section_chunks:
                chunks.append(
                    TextChunk(
                        text=chunk.text,
                        index=index,
                        source_file=source_file,
                        heading_path=heading_path,
                        heading_level=heading_level,
                        section_title=section_title,
                    )
                )
                index += 1

        return chunks

    def _get_sections(
        self, structure: DocumentStructure, text: str
    ) -> list[HeadingNode]:
        root = structure.root
        if root.level == 0:
            return root.children or [root]
        return [root]

    def _heading_metadata(
        self, structure: DocumentStructure, section: HeadingNode
    ) -> tuple[str, int, str]:
        if section.level <= 0:
            return "", 0, ""

        return (
            structure.get_heading_path(section),
            section.level,
            section.title,
        )
