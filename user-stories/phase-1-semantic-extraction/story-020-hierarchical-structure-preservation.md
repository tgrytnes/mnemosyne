# Story 005: Hierarchical Structure Preservation

**As a** user
**I want** Obsidian document structure (headings, outline) preserved during ingestion
**So that** I can query by section, navigate document hierarchies, and improve clustering with structural metadata

## Acceptance Criteria
- [ ] All chunks know their parent heading
- [ ] Can query "all chunks under ## Daily Notes"
- [ ] Document outline available for navigation
- [ ] Structure metadata used in clustering (Story 002)
- [ ] Backward compatible (existing chunks still work)
- [ ] Re-ingestion script to add structure to existing chunks
- [ ] Structure preservation score >95% (measured via Story 004)

## Technical Notes

### Implementation Approach

**New Module:**
`/src/mnemosyne/aletheia/structure_extractor.py`
- `DocumentStructure` dataclass (heading tree)
- `StructureExtractor` class
- Heading hierarchy parser (#, ##, ###, etc.)
- Outline tree builder

**Modified Modules:**
1. `/src/mnemosyne/aletheia/markdown_cleaner.py` (+50 lines)
   - Extract structure BEFORE cleaning
   - Return tuple: (cleaned_text, structure)

2. `/src/mnemosyne/aletheia/text_chunker.py` (+100 lines)
   - Accept structure metadata
   - Assign chunks to parent headings
   - Calculate heading path

3. `/src/mnemosyne/aletheia/obsidian_ingestor.py` (+100 lines)
   - Updated pipeline: extract_structure → clean → chunk_with_structure → embed → store
   - Pass structure through pipeline

4. `/src/mnemosyne/alexandria/weaviate_schema.py` (+50 lines)
   - Add properties:
     - `headingPath` (TEXT): "## Projects > ### ML > #### Transformers"
     - `headingLevel` (INT): 0-6 (0 = no heading)
     - `sectionTitle` (TEXT): Immediate parent heading
     - `documentStructure` (JSON): Full outline for navigation

### Document Structure Model

```python
@dataclass
class HeadingNode:
    level: int  # 1-6
    title: str
    start_pos: int  # Character offset in original doc
    end_pos: int
    children: List[HeadingNode]

@dataclass
class DocumentStructure:
    root: HeadingNode
    heading_map: Dict[int, HeadingNode]  # char_offset → heading

    def get_heading_at_pos(self, pos: int) -> Optional[HeadingNode]:
        """Find deepest heading at character position"""
        pass

    def get_heading_path(self, heading: HeadingNode) -> str:
        """Return path like '## Projects > ### ML'"""
        pass
```

### Chunking with Structure

```python
# Before (Story 000)
chunks = chunker.chunk_text(cleaned_text)

# After (Story 005)
structure = extractor.extract_structure(original_text)
cleaned_text = cleaner.clean_markdown(original_text)
chunks = chunker.chunk_text(cleaned_text, structure=structure)

# Each chunk now has:
# - headingPath: "## Projects > ### Machine Learning"
# - headingLevel: 3
# - sectionTitle: "Machine Learning"
```

### Weaviate Query Examples

```python
# Find all chunks under a specific section
collection.query.fetch_objects(
    filters=Filter.by_property("headingPath").like("## Daily Notes*")
)

# Find all top-level sections (heading level = 1)
collection.query.fetch_objects(
    filters=Filter.by_property("headingLevel").equal(1)
)
```

### Migration Strategy

- Schema changes are backward compatible (nullable fields)
- Existing chunks get:
  - `headingPath = null`
  - `headingLevel = 0`
  - `sectionTitle = null`
- Re-ingest vault to populate structure metadata:
  ```bash
  python -m mnemosyne.cli.ingest once --force-reingest
  ```

### Dependencies
- Markdown heading parsing (regex or markdown library)
- Weaviate client library
- Existing chunking infrastructure (Story 000)

### Data Flow

```
Markdown File → [Structure Extractor] → Document Structure
                                            ↓
                                    [Markdown Cleaner]
                                            ↓
                                    [Text Chunker with Structure]
                                            ↓
                                    Chunks with heading metadata
```

## Affected Components
- **Aletheia**: Primary implementation location (input processing)
- **Alexandria**: Schema extension (Weaviate)
- **Iris**: Benefits from structure metadata for semantic routing

## Priority
**High** - Foundation for Story 006 (hybrid chunking uses heading boundaries)

## Estimate
5 story points (3-4 days)

## Linear Labels
`phase-1`, `structure-preservation`, `metadata`, `aletheia`, `core-feature`

## Related Stories
- Story 000: Obsidian Vault Ingestion (extends this pipeline)
- Story 002: Structured Metadata Synthesis (uses heading paths in cluster profiles)
- Story 006: Semantic Chunking with LLM (hybrid strategy uses heading boundaries)

## Future Enhancements (Not in Scope)

- Wiki-link resolution (`[[...]]` → actual chunks)
- Table of contents generation
- Section-level similarity search
- Parent-child chunk relationships
