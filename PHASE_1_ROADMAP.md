# Phase 1.2-1.4 Implementation Roadmap

This document tracks the implementation progress of the performance, durability, and quality upgrades outlined in the Phase 1.2-1.4 plan.

## Implementation Status

### ✅ Phase 1.3: Operational Durability (COMPLETED)

**Goal**: Crash safety and data integrity

#### Completed Features:
1. **Atomic Writes** ✅
   - Implemented `.tmp` file pattern with `os.replace()` for atomic operations
   - VectorStore now uses atomic writes for both vectors and manifest
   - ChunkManager now uses atomic writes for manifest
   - Files: `store/vectors.py`, `store/chunks.py`

2. **Corruption Detection** ✅
   - Added `CorruptedIndexError` exception class
   - Startup validation checks vector count vs chunk_ids vs manifest count
   - Mismatch detection triggers error with detailed diagnostics
   - Files: `store/vectors.py`

3. **Self-Healing Workflow** ✅
   - VectorGit now has `auto_heal` parameter (default: True)
   - On corruption detection, can automatically rebuild vectors from chunks
   - Added `rebuild_vectors()` method for manual rebuilding
   - Corrupted stores can be recovered without manual intervention
   - Files: `tool/vectorgit.py`

4. **Tests** ✅
   - Added comprehensive test suite in `tests/vectorgit/test_atomic_writes.py`
   - Tests for atomic write behavior
   - Tests for corruption detection
   - Tests for self-healing workflows
   - All tests passing (6 new tests)

### ✅ Phase 1.2: Performance & Scale Hygiene (PARTIALLY COMPLETED)

**Goal**: Fast search without external databases

#### Completed Features:
1. **Inverted Index (Keyword Cache)** ✅
   - Implemented token -> [chunk_ids] mapping
   - O(1) keyword lookup instead of O(N) iteration
   - Automatic index building on first search
   - Incremental index updates on new chunks
   - Multi-word queries use intersection (AND logic)
   - Files: `store/chunks.py`

2. **Fast Top-K Vector Search** ✅
   - Switched from full sort to `np.argpartition()` for top-K selection
   - O(N) performance instead of O(N log N)
   - Maintains deterministic tie-breaking
   - Files: `store/vectors.py`

3. **Tests** ✅
   - Added comprehensive test suite in `tests/vectorgit/test_inverted_index.py`
   - Tests for index building, search, tokenization
   - Tests for multi-word queries and large corpus
   - All tests passing (7 new tests)

#### Remaining Work:
4. **mtime Check (Incremental Ingest)** ⏳ NOT IMPLEMENTED
   - Need to store `last_modified_timestamp` in manifest
   - On ingest, compare `os.stat(file).st_mtime` with stored value
   - Skip re-parsing files that haven't changed
   - **Estimated effort**: 2-3 hours
   - **Files to modify**: `store/chunks.py`
   - **Implementation notes**:
     ```python
     # In ChunkManager:
     # - Add file_mtimes: Dict[str, float] = {}
     # - Store in manifest: "file_mtimes": {...}
     # - In ingest_file: check if mtime matches before parsing
     # - Update mtime after successful ingest
     ```

### ⏳ Phase 1.4: Quality Upgrades (NOT IMPLEMENTED)

**Goal**: Better search accuracy and citation

#### Remaining Work:
1. **Hybrid Search (Reciprocal Rank Fusion)** ⏳ NOT IMPLEMENTED
   - Combine vector search + keyword search results
   - Use RRF scoring: score = 1 / (rank + 60)
   - Re-rank by summing scores from both methods
   - **Estimated effort**: 4-6 hours
   - **Files to modify**: `tool/vectorgit.py`
   - **Implementation notes**:
     ```python
     # In VectorGit.query_async():
     # 1. Get top 20 from vector_store.search()
     # 2. Get top 20 from chunk_manager.search_chunks()
     # 3. Score each with RRF: 1/(rank+60)
     # 4. Combine scores for chunks in both lists
     # 5. Return top K by combined score
     ```

2. **Contextual Embeddings** ⏳ NOT IMPLEMENTED
   - Wrap code in template before embedding
   - Template: "File: X\nType: Y\nName: Z\n---\n{code}"
   - Helps model understand code context
   - **Estimated effort**: 1-2 hours
   - **Files to modify**: `tool/vectorgit.py` (in `ingest_async`)
   - **Implementation notes**:
     ```python
     # In ingest_async, before gateway.embed():
     # Format each text with context:
     # text = f"File: {chunk_meta.source_path}\n"
     # text += f"Type: {chunk_meta.chunk_type}\n"
     # text += f"Name: {chunk_meta.name or 'N/A'}\n"
     # text += f"---\n{content}"
     ```

3. **Explainer Upgrade** ⏳ NOT IMPLEMENTED
   - Improve `explain()` prompt to force synthesis
   - Ask model to cite chunk IDs explicitly
   - Ask model to identify missing information
   - **Estimated effort**: 2-3 hours
   - **Files to modify**: `tool/vectorgit.py` (in `explain`)
   - **Implementation notes**:
     ```python
     # Update system_prompt in explain():
     # "You have been provided with N code chunks.
     # Evaluate if these chunks actually answer the question.
     # If yes, write the answer citing [CITATION chunk_id].
     # If no, list exactly what file paths you would need."
     ```

4. **Tests** ⏳ NOT IMPLEMENTED
   - Add tests for hybrid search behavior
   - Add tests for contextual embeddings format
   - Add tests for improved explain prompts
   - **Estimated effort**: 3-4 hours

## Quick Reference

### What's Working Now:
- ✅ Crash-safe atomic writes
- ✅ Corruption detection and self-healing
- ✅ Fast O(1) keyword search with inverted index
- ✅ Fast O(N) vector top-K search with argpartition
- ✅ All existing tests passing + 13 new tests

### What's Next (Priority Order):
1. **Incremental Ingest (mtime)** - Quick win for performance
2. **Hybrid Search (RRF)** - Big quality improvement
3. **Contextual Embeddings** - Better embedding quality
4. **Explainer Upgrade** - Better user experience

### Testing:
```bash
# Run all vectorgit tests
pytest tests/vectorgit/ -v

# Run specific test suites
pytest tests/vectorgit/test_atomic_writes.py -v
pytest tests/vectorgit/test_inverted_index.py -v
```

### Key Files Modified:
- `store/vectors.py` - Atomic writes, corruption detection, fast search
- `store/chunks.py` - Atomic writes, inverted index, tokenization
- `tool/vectorgit.py` - Self-healing, corruption handling
- `tests/vectorgit/test_atomic_writes.py` - New tests (6 tests)
- `tests/vectorgit/test_inverted_index.py` - New tests (7 tests)

## Architecture Notes

### Atomic Write Pattern:
```python
# Write to temporary file
temp_path = Path(str(target_path) + '.tmp')
write_data_to(temp_path)

# Flush to disk
with open(temp_path, 'rb') as f:
    os.fsync(f.fileno())

# Atomic replace (never partial state)
os.replace(temp_path, target_path)
```

### Inverted Index Pattern:
```python
# Build: token -> [chunk_ids]
inverted_index = {}
for chunk_id, content in chunks.items():
    tokens = tokenize(content)
    for token in tokens:
        inverted_index[token].append(chunk_id)

# Search: O(1) lookup + intersection
tokens = tokenize(query)
candidates = intersection([inverted_index[t] for t in tokens])
```

### Self-Healing Pattern:
```python
try:
    vector_store = VectorStore(path)
except CorruptedIndexError:
    if auto_heal:
        logger.warning("Rebuilding...")
        rebuild_vectors_from_chunks()
    else:
        raise
```

## Performance Impact

### Before Phase 1.2:
- Keyword search: O(N) - iterate all chunks
- Vector search: O(N log N) - full sort
- No crash safety - risk of data loss

### After Phase 1.2/1.3:
- Keyword search: O(1) - inverted index lookup
- Vector search: O(N) - argpartition for top-K
- Crash safe - atomic writes + auto-recovery
- **Expected speedup**: 10-100x for keyword search on large repos

## Migration Notes

No breaking changes. The new features are backward compatible:
- Existing vector stores will work (corruption detection on load)
- Inverted index builds automatically on first search
- Auto-healing is opt-in (default: enabled)
- Atomic writes are transparent to users

## Future Considerations

### Phase 2 (Future):
- External vector database (Qdrant, Postgres+pgvector)
- Compressed inverted index (for 100K+ chunks)
- Query caching layer
- Distributed search for multi-machine setups

### Performance Monitoring:
Consider adding metrics for:
- Search latency (p50, p95, p99)
- Index build time
- Corruption recovery events
- Cache hit rates

---

**Last Updated**: December 2024  
**Version**: Phase 1.2/1.3 Complete, Phase 1.4 Pending  
**Total New Tests**: 13 (all passing)  
**Test Coverage**: Atomic writes, corruption, self-healing, inverted index
