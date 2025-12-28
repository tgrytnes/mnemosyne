# Weaviate v4 API Patterns and Best Practices

This document captures critical patterns for working with Weaviate v4 Python client to prevent common issues.

## Table of Contents
- [Updating Existing Objects](#updating-existing-objects)
- [Deleting Objects](#deleting-objects)
- [Batch Operations](#batch-operations)
- [Vector Retrieval](#vector-retrieval)
- [Querying with Filters](#querying-with-filters)
- [Aggregation Queries](#aggregation-queries)
- [Eventual Consistency](#eventual-consistency)

---

## Updating Existing Objects

### ❌ WRONG - Using batch.add_object()
```python
# This CREATES new objects, does NOT update existing ones!
with collection.batch.dynamic() as batch:
    for uuid, label in zip(uuids, labels):
        batch.add_object(
            uuid=uuid,
            properties={"clusterId": int(label)},
        )
```

**Problem**: `batch.add_object()` attempts to create new objects. If the UUID already exists, the operation may fail silently or create duplicates.

### ✅ CORRECT - Using data.update()
```python
# Properly updates existing objects
for uuid_str, label in zip(uuids, labels):
    collection.data.update(
        uuid=uuid_str,
        properties={"clusterId": int(label)},
    )
```

**Why**: `data.update()` is the correct method for modifying properties of existing objects.

**Note**: For large-scale updates, Weaviate v4 doesn't have batch update yet. You must update objects individually or use delete + recreate pattern.

---

## Deleting Objects

### ❌ WRONG - Using where=None
```python
# This fails with gRPC error in Weaviate v4
collection.data.delete_many(where=None)
```

**Error**: `grpc._channel._InactiveRpcError: batch delete params: no filters in batch delete request`

### ✅ CORRECT - Using Filter that matches all objects
```python
from weaviate.classes.query import Filter

# Delete all objects by filtering on a property that all objects have
delete_result = collection.data.delete_many(
    where=Filter.by_property("clusterId").greater_or_equal(0)
)

# Check results
logger.info(
    f"Deleted {delete_result.matches} objects "
    f"(successful: {delete_result.successful}, failed: {delete_result.failed})"
)
```

**Alternative - Collection Recreation** (use sparingly):
```python
# Only if you want to completely reset a collection
if client.collections.exists("CollectionName"):
    client.collections.delete("CollectionName")
schema_manager.ensure_collection_exists("CollectionName")
```

**Warning**: Collection recreation invalidates all existing collection references in code.

---

## Batch Operations

### Fixed-Size vs Dynamic Batching

**Dynamic Batching** (default):
```python
with collection.batch.dynamic() as batch:
    for item in items:
        batch.add_object(properties=item, vector=vec)
```
- Adjusts batch size based on object size
- Good for variable-sized objects
- Less predictable timing

**Fixed-Size Batching** (recommended for critical operations):
```python
with collection.batch.fixed_size(batch_size=100) as batch:
    for item in items:
        batch.add_object(properties=item, vector=vec)
```
- Predictable batch sizes
- Better for debugging
- Recommended when you need verification afterward

### Auto-Flush on Context Exit
Both `dynamic()` and `fixed_size()` automatically flush remaining objects when the context manager exits. You don't need to call `flush()` manually.

---

## Vector Retrieval

### ❌ WRONG - Assuming vectors are returned by default
```python
response = collection.query.fetch_objects(limit=10)
vector = response.objects[0].vector["default"]  # KeyError!
```

### ✅ CORRECT - Explicitly request vectors
```python
response = collection.query.fetch_objects(
    limit=10,
    include_vector=True  # CRITICAL: Must explicitly request vectors
)

# Safe access pattern
if response.objects and response.objects[0].vector:
    # Safely access vector with get() to handle missing 'default' key
    vector_data = response.objects[0].vector.get("default")
    if vector_data:
        return np.array(vector_data)
    # Fallback: try direct access if vector is a list
    if isinstance(response.objects[0].vector, list):
        return np.array(response.objects[0].vector)
```

**Key Points**:
- Vectors are NOT returned by default
- Must use `include_vector=True` in queries
- Vectors are stored under `"default"` key for unnamed vectors
- Always use safe access patterns (`.get()`) to prevent KeyError

---

## Querying with Filters

### ❌ WRONG - Using iterator() with filters
```python
# iterator() does NOT support filters parameter
for item in collection.iterator(
    filters=Filter.by_property("clusterId").equal(1),  # TypeError!
    include_vector=True
):
    process(item)
```

**Error**: `TypeError: Collection.iterator() got an unexpected keyword argument 'filters'`

### ✅ CORRECT - Using fetch_objects() with filters
```python
from weaviate.classes.query import Filter

response = collection.query.fetch_objects(
    filters=Filter.by_property("clusterId").equal(1),
    include_vector=True,
    limit=10000  # Set high limit to get all matching objects
)

all_vectors = [obj.vector["default"] for obj in response.objects]
```

**When to use each**:
- `iterator()`: Paginating through ALL objects (no filtering needed)
- `fetch_objects()`: Filtering objects by property + pagination

---

## Aggregation Queries

### ❌ WRONG - Old v3 API
```python
total = collection.aggregate.total_count()["total_count"]  # AttributeError!
```

**Error**: `'_AggregateCollection' object has no attribute 'total_count'`

### ✅ CORRECT - Weaviate v4 API
```python
# Count all objects in collection
total = collection.aggregate.over_all(total_count=True).total_count

# With grouping
result = collection.aggregate.over_all(
    total_count=True,
    group_by="clusterId"
)
for group in result.groups:
    print(f"Cluster {group.grouped_by}: {group.total_count} objects")
```

---

## Eventual Consistency

Weaviate operations (especially batch inserts and deletes) are **eventually consistent**. Objects may not be immediately queryable after insertion.

### ✅ Verification Pattern with Retries
```python
import time

# Insert objects
with collection.batch.fixed_size(batch_size=100) as batch:
    for item in items:
        batch.add_object(vector=vec, properties=props)

# Verify insertion with retries
time.sleep(0.5)  # Initial delay
for attempt in range(3):
    verify = collection.query.fetch_objects(limit=1, include_vector=True)
    if len(verify.objects) > 0:
        logger.info(f"Verified {len(items)} objects stored successfully")
        break
    logger.warning(
        f"Verification attempt {attempt + 1}: No objects found yet, retrying..."
    )
    time.sleep(0.5)
```

**Best Practices**:
1. Add small delay (0.5s) after batch operations
2. Verify with retries (3 attempts)
3. Log verification results for debugging
4. Increase delays if consistency issues persist

---

## Common Errors and Solutions

### KeyError: 'default'
**Cause**: Trying to access vector without `include_vector=True` or unsafe access pattern

**Solution**:
```python
response = collection.query.fetch_objects(include_vector=True)
vector_data = response.objects[0].vector.get("default")  # Safe access
```

### assert 0 == 5 (empty results)
**Cause**: Objects not updated correctly or eventual consistency

**Solutions**:
1. Check you're using `data.update()` not `batch.add_object()`
2. Add verification loop with retries
3. Add timing delays after batch operations

### delete_many returns 0 matches
**Cause**: Filter not matching objects or timing issue

**Solutions**:
1. Verify filter syntax: `Filter.by_property("field").greater_or_equal(0)`
2. Check property exists on all objects
3. Add delay before delete if objects were just created

---

## Testing Patterns

### Unit Tests - Mock Weaviate Client
```python
from unittest.mock import MagicMock

mock_item = MagicMock()
mock_item.vector = {"default": [0.1, 0.2, 0.3]}
mock_item.properties = {"clusterId": 1}

mock_client.collections.get.return_value.query.fetch_objects.return_value = \
    MagicMock(objects=[mock_item])
```

### Integration Tests - Real Weaviate
```python
@pytest.fixture
def weaviate_client():
    client = weaviate.connect_to_local(host="localhost", port=8080, grpc_port=50051)
    yield client
    client.close()

def test_with_real_weaviate(weaviate_client):
    collection = weaviate_client.collections.get("TheMuses")
    # Use real Weaviate operations
    assert collection.aggregate.over_all(total_count=True).total_count >= 0
```

**Prefer integration tests** for Weaviate operations to catch API changes.

---

## Version Compatibility

This document applies to:
- **Weaviate Server**: v1.23+
- **weaviate-client Python**: v4.x

**Breaking Changes from v3 → v4**:
- `aggregate.total_count()` → `aggregate.over_all(total_count=True).total_count`
- `delete_many(where=None)` → requires Filter object
- `iterator(filters=...)` → not supported, use `fetch_objects()`
- Vectors not returned by default → must use `include_vector=True`

---

## Quick Reference

| Operation | Correct Method | Key Parameter |
|-----------|---------------|---------------|
| Create objects | `batch.add_object()` | `vector`, `properties` |
| Update objects | `data.update()` | `uuid`, `properties` |
| Delete all | `delete_many(where=Filter...)` | Filter that matches all |
| Get vectors | `fetch_objects()` | `include_vector=True` |
| Filter query | `fetch_objects()` | `filters=Filter.by_property()` |
| Count objects | `aggregate.over_all()` | `total_count=True` |

---

## References

- [Weaviate v4 Python Client Docs](https://weaviate.io/developers/weaviate/client-libraries/python)
- [Weaviate Batch Operations](https://weaviate.io/developers/weaviate/manage-data/import)
- [Weaviate Query API](https://weaviate.io/developers/weaviate/search/basics)
