# Story 031: Robust Raw Email Ingestion with Semantic Chunking

**As a** user with large, growing email archives
**I want** to directly ingest my raw email files (.eml, .mbox) in a robust, resumable, and semantically optimized way
**So that** I can reliably process my entire email history, keep it up-to-date, and achieve high-quality search and clustering results through semantic chunking.

## 🎯 Architectural Note

This story **replaces and deprecates** the TSV-based ingestion from **Story 024**. We will pivot to a more direct, robust, and semantically enhanced raw email ingestion pipeline, fulfilling and extending the original vision of Story 024. The ingestion will now focus on storing semantically coherent chunks rather than entire emails, to improve retrieval and clustering performance.

**This story ingests email *chunks* into The Lethe collection (NOT The Muses).**

## Excellent Acceptance Criteria

### Functional Criteria
- [ ] **Scenario: TSV is Fully Deprecated**
    - **Given** the old `EMAIL_TSV` environment variable is set
    - **When** the `email_ingest.py` script is executed
    - **Then** the script must fail with an error message indicating that `EMAIL_TSV` is no longer supported and `SOURCE_DIR` should be used instead.

- [ ] **Scenario: Mixed Source Ingestion and Chunking**
    - **Given** a `SOURCE_DIR` containing a mix of `5` `.eml` files and `1` `mbox` file with `10` unique emails (total 15 distinct emails)
    - **When** the ingestion script is run to completion with `CHUNKING_STRATEGY=semantic`
    - **Then** the Weaviate collection "TheLetheChunks" (or similar) must contain more than `15` items (representing multiple chunks per email).
    - **And** each ingested item in Weaviate must be an `EmailChunk` linked to its original parent email.

- [ ] **Scenario: Checkpointing and Resumability**
    - **Given** a `SOURCE_DIR` with `100` emails
    - **When** the ingestion script is run with semantic chunking and then manually stopped after ingesting `~50` emails
    - **And** the script is restarted
    - **Then** the script's output should show it is skipping the first `~50` emails (i.e., not re-chunking them)
    - **And** the total number of *unique parent emails* processed in "The LetheChunks" at the end should be exactly `100`.

- [ ] **Scenario: Delta Ingestion**
    - **Given** a `SOURCE_DIR` has been successfully ingested with semantic chunking
    - **When** `5` new `.eml` files are added to the `SOURCE_DIR`
    - **And** the ingestion script is run again with semantic chunking
    - **Then** the script should process and ingest only the `5` new emails and their corresponding chunks
    - **And** the total count of *unique parent emails* processed in Weaviate should reflect the addition of exactly `5` new parent emails.

- [ ] **Scenario: Semantic Chunking Verification**
    - **Given** an email with a multi-topic body (e.g., discussion of software, then a marketing section, then a personal anecdote)
    - **When** this email is ingested with `CHUNKING_STRATEGY=semantic`
    - **Then** the Weaviate collection must contain multiple `EmailChunk` items for this email.
    - **And** manual inspection of these `EmailChunk` items should show distinct chunks, each representing a single coherent topic or idea from the original email body, and linked back to the parent email.

### Non-Functional & Quality Criteria
- [ ] **Scenario: Data Integrity and Cleaning**
    - **Given** an email with known HTML tags, a signature, and tracking links is ingested
    - **When** the corresponding `EmailChunk` items are retrieved from Weaviate
    - **Then** their `chunk_text` field must be plain text, with the HTML, signature, and tracking links removed by `email_cleaner.py`.

- [ ] **Scenario: Correct Unique ID Generation**
    - **Given** a mix of emails, some with and some without a `Message-ID` header
    - **When** the `.email_ingestion_state.json` file is inspected after ingestion
    - **Then** it must contain entries starting with `<` (for `Message-ID`) and entries starting with `hash-` for the emails that were missing a `Message-ID`.

- [ ] **Scenario: Performance Baseline**
    - **Given** a large archive of at least `1,000` emails
    - **When** the ingestion script is run with `CHUNKING_STRATEGY=semantic`
    - **Then** the average ingestion rate (including chunking and embedding) must be no less than 50 emails per minute on the target hardware (e.g., Raspberry Pi 5).

- [ ] **Scenario: Downstream Compatibility**
    - **Given** emails are ingested via semantic chunking into "TheLetheChunks"
    - **When** clustering and labeling processes from Story 024's design are applied to this collection
    - **Then** these processes must function correctly and yield meaningful results, indicating that the chunk-level data is usable.

## Technical Plan

### 1. Deprecate TSV and Refine Configuration
- The `EmailIngestor` and its configuration will be updated to remove all references to TSV.
- The entry point (`main` function) will be changed to accept a `SOURCE_DIR` environment variable pointing to the directory with email archives.

### 2. Checkpointing and Delta Ingestion
- A state file (e.g., `.email_ingestion_state.json`) will be used to track the unique IDs of all successfully ingested emails.
- The **Unique ID Strategy** will be as follows:
    1.  Prioritize the `Message-ID` header from the email, which is a globally unique identifier.
    2.  If `Message-ID` is absent, generate a stable unique ID by hashing key fields of the email (e.g., `subject`, `sender`, `date`, first 256 chars of `body`).
- On startup, the `EmailIngestor` will load this state file.
- Before processing any email message (from an `.eml` or within an `mbox`), it will check if its unique_id is in the state file. If so, it will be skipped entirely (including chunking).
- After all chunks for an `Email` object are successfully stored in Weaviate, its `unique_id` will be written to the state file.

### 3. Unified Email Parsing (`email_parser.py`)
- A new `src/mnemosyne/aletheia/email_parser.py` module will be created.
- It will contain functions to handle both `.eml` files and `mbox` archives, yielding `Email` objects.
- Python's built-in `email` and `mailbox` modules will be used for parsing.
- The parser will be responsible for extracting the content and metadata into the `Email` data model and applying `email_cleaner.py` to the body during parsing.

### 4. Data Models (`models.py`)
- A new `src/mnemosyne/aletheia/models.py` file will define:
    - The `Email` dataclass (representing a parsed raw email with a `unique_id` property).
    - The `EmailChunk` dataclass (representing an individual semantic chunk, including `parent_email_unique_id`, `chunk_text`, `chunk_index`, `parent_subject`, `parent_sender`, `parent_date`, `parent_source_path`).

### 5. Semantic Chunking Integration
- The `EmailIngestor` will utilize `src/mnemosyne/aletheia/chunking_strategy_factory.py` to create an `IChunker` instance (e.g., `SemanticChunker`).
- After an email's body is parsed and cleaned, it will be passed to this `IChunker` which will return a list of `TextChunk` objects.
- Each `TextChunk` will then be transformed into an `EmailChunk` object, embedded, and inserted into Weaviate.

### 6. Scheduling (Out of Scope)
- **Note**: The script itself will be designed for manual execution and will handle delta ingestion automatically. The task of running this script on a recurring schedule (e.g., daily) is a separate operational concern to be handled by a system scheduler like `cron` or a `systemd` timer. This will not be part of the Python application.

## Affected Components
- **Aletheia**: `email_ingest.py` will be significantly refactored. `models.py` and `email_parser.py` will be added. Integration with `chunking_strategy_factory.py` and `semantic_chunker.py`.
- **Alexandria**: Weaviate schema for "TheLethe" collection will be adapted to store `EmailChunk` objects, potentially creating a new collection like "TheLetheChunks".

## Priority
**High** - This is a foundational improvement for robust data ingestion and quality.

## Estimate
13 story points (8-10 days) - Increased due to semantic chunking complexity.

## Linear Labels
`phase-0`, `ingestion`, `email`, `aletheia`, `enhancement`, `semantic-chunking`

## Related Stories
- **Story 021: Semantic Chunking with LLM**: Leverages the core chunking functionality implemented in this story.
- **Story 024: Email Archive Ingestion**: This story's TSV implementation is now deprecated by this story. This new story fulfills the original raw ingestion goal of Story 024 and significantly enhances its quality.
