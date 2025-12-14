# Chunk ID Determinism

## Overview

VectorGit uses deterministic chunk IDs to ensure stable citations across time. This document explains the rules and guarantees.

## Chunk ID Generation

### Rule: Content-Only Hashing

Chunk IDs are generated using **content-only** hashing:

```python
chunk_hash = sha256(content).hexdigest()[:16]
chunk_id = f"chunk_{chunk_hash}"
```

**Key Properties:**
- Same content → Same chunk ID (always)
- Different content → Different chunk ID (always)
- File path changes → Same chunk ID (if content unchanged)
- Line number changes → Same chunk ID (if content unchanged)

### Why Content-Only?

This ensures maximum stability:
1. **Refactoring safe**: Moving functions between files preserves chunk IDs
2. **Merge safe**: Git merges that move code don't break citations
3. **Predictable**: Easy to reason about and debug

### Trade-offs

**Advantages:**
- ✅ Maximum citation stability
- ✅ Deduplication across files (same function in multiple places = one chunk)
- ✅ Refactoring doesn't invalidate old citations

**Disadvantages:**
- ⚠️ Multiple identical functions in different files share one chunk ID
- ⚠️ Chunk metadata (path, lines) reflects last-seen location only

For most use cases, the advantages far outweigh the disadvantages.

## Incremental Re-ingestion

### Stale Detection (Phase 1.1)

When re-ingesting a file:

1. **Track old chunks**: `source_to_chunks[file_path]` remembers old chunk IDs
2. **Generate new chunks**: Parse file and compute new chunk IDs
3. **Detect stale**: `old_ids - new_ids` = stale chunks
4. **Remove stale**: Delete from memory and mark for vector removal

### Example Flow

```python
# Initial ingest
file.py: def foo(): return 1  →  chunk_abc123

# Edit file
file.py: def foo(): return 2  →  chunk_def456  (new content = new ID)

# Re-ingest
- old_ids = {chunk_abc123}
- new_ids = {chunk_def456}
- stale_ids = {chunk_abc123}
- Remove chunk_abc123 from memory and vectors
```

## Vector Store Idempotence

### Rule: Add Updates In-Place

When adding vectors:

```python
if chunk_id in store:
    store.update(chunk_id, new_vector)  # Update existing
else:
    store.append(chunk_id, new_vector)  # Append new
```

**Guarantees:**
- No duplicate chunk IDs in vector store
- Re-ingesting updates vectors instead of duplicating
- Vector count always matches chunk count

### Stale Vector Removal

Vectors are removed when:
1. **File-level**: Chunk removed from file → marked stale → removed from vectors
2. **Global prune**: Periodic cleanup removes vectors not in active chunk set

## Testing

Phase 1.1 tests validate:

### Unit Tests
- `test_determinism.py`: Re-ingest produces identical chunk IDs
- `test_reembed_changed.py`: File changes mark old chunks stale
- `test_vectorstore_idempotent_add.py`: Re-adding updates not duplicates

### Integration Tests
- `test_phase11_incremental.py`: Full definition of done
  - Edit → Re-ingest → Only affected chunks change
  - Semantic search reflects new reality
  - Old stale chunks are gone
  - No duplicates

## Definition of Done

Phase 1.1 is considered complete when:

✅ Edit a file  
✅ Re-ingest  
✅ Only affected chunks change (new IDs for changed content)  
✅ Semantic search reflects new reality (finds new content)  
✅ Old stale chunks are gone (removed from memory and vectors)  
✅ No duplicates (no duplicate chunk IDs or vectors)  

**Status**: ✅ All tests passing (as of Phase 1.1 completion)

## Future Considerations

### Content+Path Hashing?

Alternative approach: `hash(content + path)`

**Pros:**
- ✅ Different locations = different chunks
- ✅ No confusion about "which file has this function?"

**Cons:**
- ❌ Refactoring breaks citations
- ❌ Moving code invalidates old references
- ❌ Higher citation churn

**Decision**: Stick with content-only for maximum stability. The benefits outweigh the edge cases.

### Chunk Versioning?

Track chunk history: `chunk_abc123_v1`, `chunk_abc123_v2`

**Pros:**
- ✅ Historical queries work
- ✅ Can track "what changed" over time

**Cons:**
- ❌ Complexity increases significantly
- ❌ Storage grows unbounded
- ❌ Citation format more complex

**Decision**: Not needed for Phase 1.x. Consider for future if version history becomes critical.
