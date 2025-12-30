# Weaviate Client Gotchas and Troubleshooting

This document captures important learnings, gotchas, and troubleshooting tips for working with Weaviate Python client v4 in the Mnemosyne project.

## Filter Query Behavior (CRITICAL)

### Problem: `.like()` and `.contains_any()` Filters Don't Work as Expected

When filtering objects by file paths (e.g., `sourceFile` property), Weaviate's filter methods have unexpected behavior:

**What Doesn't Work:**
```python
from weaviate.classes.query import Filter

# ❌ Using glob-style wildcards - matches WRONG files
results = collection.query.fetch_objects(
    filters=Filter.by_property("sourceFile").like("*/test_note.md")
)

# ❌ Using SQL-style wildcards - matches WRONG files
results = collection.query.fetch_objects(
    filters=Filter.by_property("sourceFile").like("%/test_note.md")
)

# ❌ Using contains_any - matches too broadly
results = collection.query.fetch_objects(
    filters=Filter.by_property("sourceFile").contains_any(["/test_note.md"])
)
```

**Observed Behavior:**
- Query for `test_note.md` returns `advanced_note.md` and `long_note.md` instead
- Filter appears to match substrings incorrectly
- Wildcard patterns (`*`, `%`) don't match expected paths

### Solution: Filter in Python After Fetching

**Workaround (Recommended for Small Result Sets):**
```python
from types import SimpleNamespace

# Fetch all objects (or use reasonable limit)
all_results = collection.query.fetch_objects(limit=100)

# Filter in Python using standard string methods
results_list = [
    obj for obj in all_results.objects
    if obj.properties.get('sourceFile', '').endswith('/test_note.md')
]

# Create mock results object for compatibility
results = SimpleNamespace(objects=results_list)
```

**When This Works Well:**
- Small to medium result sets (< 1000 objects)
- Test environments
- Exact filename matching needed

**When to Avoid:**
- Large datasets (performance impact)
- Production queries with millions of objects
- When Weaviate-side filtering is required for performance

### Alternative Solutions (To Investigate)

If Python-side filtering isn't suitable, consider:

1. **Exact Match Filters:**
   ```python
   # Store and query by exact filename separately
   filters=Filter.by_property("fileName").equal("test_note.md")
   ```

2. **UUID-based Lookup:**
   ```python
   # Store UUID mapping for deterministic lookups
   obj_uuid = collection.query.fetch_object_by_id(uuid)
   ```

3. **Hybrid Approach:**
   ```python
   # Use broad filter + Python refinement
   results = collection.query.fetch_objects(
       filters=Filter.by_property("sourceType").equal("obsidian"),
       limit=1000
   )
   filtered = [r for r in results.objects if r.properties['sourceFile'].endswith('/test_note.md')]
   ```

## Vector Storage Format

### Issue: Vector is a Dictionary, Not an Array

**Problem:**
```python
# ❌ This fails: TypeError or wrong length
assert len(obj.vector) == 1024
```

**Root Cause:**
Weaviate v4 stores vectors in a nested dictionary structure with named vector spaces.

**Solution:**
```python
# ✅ Access the vector through the 'default' key
assert "default" in obj.vector
assert len(obj.vector["default"]) == 1024
assert sum(obj.vector["default"]) != 0  # Verify non-zero
```

**Why This Matters:**
- Weaviate supports multiple named vector spaces per object
- The default vector space is called `"default"`
- Always access vectors via `obj.vector["default"]` or appropriate named key

## Schema and Collection Management

### Cleanup Fixture Must Handle Missing Collections

**Problem:**
```python
# ❌ Fails on first test run when collection doesn't exist
collection = client.collections.get("TheMuses")
collection.data.delete_many(...)
```

**Solution:**
```python
# ✅ Wrap in try-except for idempotency
@pytest.fixture(autouse=True)
def cleanup_weaviate(self, weaviate_client):
    """Clean up Weaviate collection before each test."""
    try:
        collection = weaviate_client.collections.get("TheMuses")
        collection.data.delete_many(
            where=Filter.by_property("sourceType").equal("obsidian")
        )
    except Exception:
        # Collection doesn't exist yet - this is fine for first test
        pass
    yield
```

**When This Applies:**
- E2E tests with fresh Weaviate instances
- CI/CD environments
- Any fixture that runs before collection creation

## API Changes from v3 to v4

### Parameter Name Changes

**Query Parameters:**
```python
# v3 (old)
collection.query.fetch_objects(return_vectors=True)

# v4 (new) ✅
collection.query.fetch_objects(include_vector=True)
```

**Always Check:**
- Review [Weaviate v4 migration guide](https://weaviate.io/developers/weaviate/migration)
- Parameter names changed between major versions
- TypeErrors often indicate deprecated parameters

## Testing with Real Weaviate Services

### Test Data Management

**Challenge:** Tests can see data from previous test runs

**Solutions:**
1. **Cleanup Fixture (Preferred):**
   ```python
   @pytest.fixture(autouse=True)
   def cleanup_weaviate(self, weaviate_client):
       # Clean BEFORE each test
       try:
           collection = weaviate_client.collections.get("TheMuses")
           collection.data.delete_many(
               where=Filter.by_property("sourceType").equal("obsidian")
           )
       except Exception:
           pass
       yield
       # No cleanup after - next test will clean before it runs
   ```

2. **Unique Test Identifiers:**
   ```python
   # Use pytest's tmp_path for unique paths per test
   vault = tmp_path / "test_vault_000"
   ```

3. **Collection per Test (Expensive):**
   ```python
   # Create/delete entire collection per test (slow)
   collection_name = f"Test_{uuid.uuid4()}"
   ```

### Real vs Mock Embeddings

**Our Approach:**
- E2E tests use **real** Ollama embeddings (qwen3-embedding:0.6b)
- Vectors are 1024-dimensional
- Tests verify embeddings are non-zero (not mocked)

**Verification:**
```python
# Verify real Ollama embeddings
assert "default" in obj.vector
assert len(obj.vector["default"]) == 1024
assert sum(obj.vector["default"]) != 0  # Proves real embedding
```

## Performance Considerations

### Chunking and Structure Preservation

**Observation:** Story 020's structure preservation can create very short chunks

**Example:**
```markdown
# Long Document

Content here...
```

With structure preservation:
- Heading "# Long Document" → separate chunk (15 chars)
- Content → normal chunks (~400 chars)

**Test Adjustment:**
```python
# Allow for short heading-only chunks
assert 10 < text_len < 800  # Not 50 < text_len < 800
```

## Debugging Tips

### 1. Always Verify What's Actually in the Database

```python
# Fetch ALL objects to see what exists
all_results = collection.query.fetch_objects(limit=100)
print(f"Total objects: {len(all_results.objects)}")
for obj in all_results.objects:
    print(f"sourceFile: {obj.properties.get('sourceFile')}")
```

### 2. Log Filter Results Before Assertions

```python
results = collection.query.fetch_objects(filters=...)
print(f"Filter returned {len(results.objects)} objects")
for obj in results.objects:
    print(f"  - {obj.properties.get('sourceFile')}")
```

### 3. Test Filters with Known Data

```python
# Create test object with known properties
collection.data.insert(
    properties={"sourceFile": "/known/path/test.md", "text": "test"}
)

# Verify filter finds it
results = collection.query.fetch_objects(filters=...)
assert len(results.objects) == 1
```

## Related Issues and Resources

### Weaviate Documentation
- [Filters Documentation](https://weaviate.io/developers/weaviate/search/filters)
- [Python Client v4 Reference](https://weaviate.io/developers/weaviate/client-libraries/python)
- [Migration Guide v3 → v4](https://weaviate.io/developers/weaviate/migration)

### Known Issues in This Project
- PR #4: Fixed E2E test filter issues (see commit history)
- Story 000: Weaviate filter troubleshooting
- Story 020: Structure preservation affecting chunk sizes

## Version Information

**Current Setup:**
- Weaviate Client: `^4.0.0` (see pyproject.toml)
- Weaviate Server: Running via Docker (localhost:8080)
- Ollama Model: qwen3-embedding:0.6b (1024 dimensions)

## Future Improvements

**TODO: Investigate and Document**
1. Is there a `.ends_with()` filter method in Weaviate v4?
2. Can we use regex filters for path matching?
3. What's the performance impact of Python-side filtering at scale?
4. Should we create indexed fields specifically for filtering (e.g., `fileName` separate from `sourceFile`)?

---

**Last Updated:** 2025-12-29
**Contributors:** Story 020 E2E Test Debugging Session
