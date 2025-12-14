# Next Steps: Completing Phase 1.2-1.4

## Quick Start

This document provides concrete implementation steps for completing the remaining features.

## Priority 1: mtime-based Incremental Ingest (2-3 hours)

### Goal
Skip re-parsing files that haven't changed since last ingest.

### Implementation Steps

1. **Update ChunkMetadata in `store/chunks.py`**:
```python
# Add to ChunkManager.__init__:
self.file_mtimes: Dict[str, float] = {}  # source_path -> mtime

# In save_manifest():
data = {
    # ... existing fields ...
    "file_mtimes": self.file_mtimes,
}

# In _load_manifest():
self.file_mtimes = data.get("file_mtimes", {})
```

2. **Add mtime check in `ingest_file()`**:
```python
def ingest_file(self, file_path: str) -> int:
    try:
        path = Path(file_path)
        source_path = str(path.resolve())
        
        # ... existing validation ...
        
        # Phase 1.2: Check mtime for incremental ingest
        current_mtime = path.stat().st_mtime
        stored_mtime = self.file_mtimes.get(source_path)
        
        if stored_mtime is not None and stored_mtime == current_mtime:
            logger.debug(f"Skipping unchanged file: {file_path}")
            return 0  # No new chunks
        
        # ... rest of existing logic ...
        
        # Update mtime after successful ingest
        self.file_mtimes[source_path] = current_mtime
```

3. **Add test in `tests/vectorgit/test_incremental_ingest.py`**:
```python
def test_skip_unchanged_files():
    """Test that unchanged files are skipped on re-ingest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ChunkManager(...)
        
        file1 = Path(tmpdir) / "test.py"
        file1.write_text("def foo(): pass")
        
        # First ingest
        count1 = manager.ingest_file(str(file1))
        assert count1 > 0
        
        # Second ingest without changes
        count2 = manager.ingest_file(str(file1))
        assert count2 == 0  # Skipped
        
        # Modify file
        file1.write_text("def bar(): pass")
        count3 = manager.ingest_file(str(file1))
        assert count3 > 0  # Re-ingested
```

### Expected Impact
- 10-100x faster re-ingestion of large repos
- Instant updates when only a few files change

---

## Priority 2: Hybrid Search with RRF (4-6 hours)

### Goal
Combine vector search (concepts) with keyword search (specifics) for better accuracy.

### Implementation Steps

1. **Add RRF scoring function in `tool/vectorgit.py`**:
```python
def _reciprocal_rank_fusion(
    self,
    results_a: List[Dict[str, Any]],
    results_b: List[Dict[str, Any]],
    k: int = 60
) -> List[Dict[str, Any]]:
    """Combine two result lists using Reciprocal Rank Fusion.
    
    Args:
        results_a: First result list
        results_b: Second result list
        k: Constant for RRF (default: 60)
        
    Returns:
        Re-ranked combined results
    """
    scores: Dict[str, float] = {}
    chunks: Dict[str, Dict[str, Any]] = {}
    
    # Score from first list
    for rank, result in enumerate(results_a, start=1):
        chunk_id = result["chunk_id"]
        scores[chunk_id] = scores.get(chunk_id, 0) + (1.0 / (rank + k))
        chunks[chunk_id] = result
    
    # Score from second list
    for rank, result in enumerate(results_b, start=1):
        chunk_id = result["chunk_id"]
        scores[chunk_id] = scores.get(chunk_id, 0) + (1.0 / (rank + k))
        chunks[chunk_id] = result
    
    # Sort by combined score
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    
    # Return top results with scores
    results = []
    for chunk_id, score in ranked:
        chunk = chunks[chunk_id].copy()
        chunk["hybrid_score"] = score
        results.append(chunk)
    
    return results
```

2. **Update `query_async()` to use hybrid search**:
```python
async def query_async(
    self, 
    query_text: str, 
    gateway: Optional[EmbeddingGateway] = None,
    top_k: int = 8,
    use_hybrid: bool = True  # New parameter
) -> List[Dict[str, Any]]:
    """Query using hybrid search (vector + keyword) if enabled."""
    
    # Get keyword results
    keyword_results = self.chunk_manager.search_chunks(query_text, k=20)
    
    # Get vector results if gateway provided
    if gateway:
        try:
            query_vec = await gateway.embed_single(query_text)
            if query_vec:
                vector_results = self.vector_store.search(query_vec, k=20)
                # Hydrate
                vector_results_full = []
                for chunk_id, score in vector_results:
                    chunk = self.chunk_manager.get_chunk(chunk_id)
                    if chunk:
                        chunk["score"] = score
                        vector_results_full.append(chunk)
                
                # Phase 1.4: Hybrid search with RRF
                if use_hybrid and vector_results_full:
                    results = self._reciprocal_rank_fusion(
                        vector_results_full,
                        keyword_results
                    )
                    return results[:top_k]
                
                return vector_results_full[:top_k]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
    
    return keyword_results[:top_k]
```

3. **Add tests in `tests/vectorgit/test_hybrid_search.py`**:
```python
def test_rrf_combines_results():
    """Test that RRF properly combines vector and keyword results."""
    # Setup with files that match differently on vector vs keyword
    # Assert that hybrid results include best from both

def test_hybrid_better_than_single():
    """Test that hybrid search finds results missed by single methods."""
    # Create scenario where vector finds "login" but keyword finds "authenticate"
    # Query for "user authentication"
    # Assert hybrid finds both
```

### Expected Impact
- 20-40% improvement in search relevance
- Better handling of synonyms and related concepts
- More precise results for specific queries

---

## Priority 3: Contextual Embeddings (1-2 hours)

### Goal
Add metadata context to embeddings for better understanding.

### Implementation Steps

1. **Update embedding formatting in `tool/vectorgit.py`**:
```python
async def ingest_async(self, repo_path: str, gateway: Optional[EmbeddingGateway] = None) -> int:
    # ... existing code ...
    
    if ids_to_embed:
        logger.info(f"Embedding {len(ids_to_embed)} chunks...")
        try:
            # Phase 1.4: Contextual embeddings
            formatted_texts = []
            for i, chunk_id in enumerate(ids_to_embed):
                chunk_meta = self.chunk_manager.chunks[chunk_id]
                chunk_data = self.chunk_manager.get_chunk(chunk_id)
                content = chunk_data.get("content", "")
                
                # Format with context
                text = f"File: {chunk_meta.source_path}\n"
                text += f"Type: {chunk_meta.chunk_type}\n"
                if chunk_meta.name:
                    text += f"Name: {chunk_meta.name}\n"
                text += f"---\n{content}"
                
                formatted_texts.append(text)
            
            vectors = await gateway.embed(formatted_texts)
            # ... rest of existing code ...
```

2. **Add version marker to detect format change**:
```python
# In VectorStore metadata:
self.metadata["embedding_format"] = "contextual_v1"  # Track format version

# On load, check format:
if self.metadata.get("embedding_format") != "contextual_v1":
    logger.warning("Embeddings use old format, consider re-embedding")
```

### Expected Impact
- 10-20% improvement in semantic search accuracy
- Better understanding of code structure
- More relevant results for conceptual queries

---

## Priority 4: Improved Explain Prompts (2-3 hours)

### Goal
Make AI responses more accurate and cite sources properly.

### Implementation Steps

1. **Update system prompt in `tool/vectorgit.py`**:
```python
async def explain(self, query_text: str, gateway: ModelGateway, top_k: int = 8) -> str:
    # ... retrieve chunks ...
    
    # Phase 1.4: Improved system prompt
    system_prompt = (
        "You are an expert coding assistant analyzing retrieved code chunks.\n\n"
        "INSTRUCTIONS:\n"
        "1. Evaluate if the provided chunks actually answer the user's question\n"
        "2. If YES:\n"
        "   - Write a clear answer synthesizing information from the chunks\n"
        "   - Cite sources using the format: [CITATION chunk_id]\n"
        "   - Explain your reasoning\n"
        "3. If NO:\n"
        "   - Explain what's missing\n"
        "   - List specific file paths or code elements needed\n"
        "   - Suggest what to search for next\n\n"
        "RULES:\n"
        "- Only use information from provided chunks\n"
        "- Always cite chunk IDs for claims\n"
        "- Be specific about what you found or didn't find\n"
        "- If uncertain, say so\n"
    )
    
    user_prompt = (
        f"Question: {query_text}\n\n"
        f"Retrieved Chunks ({len(chunks)} total):\n\n"
        f"{context_str}\n\n"
        f"Analysis:"
    )
    
    # ... rest of existing code ...
```

2. **Add response parsing helper**:
```python
def _parse_citations(self, response: str) -> List[str]:
    """Extract cited chunk IDs from response."""
    import re
    pattern = r'\[CITATION (chunk_[a-f0-9]+)\]'
    citations = re.findall(pattern, response)
    return citations

def _validate_citations(self, response: str, available_chunks: List[str]) -> bool:
    """Check if all citations are valid."""
    citations = self._parse_citations(response)
    invalid = [c for c in citations if c not in available_chunks]
    if invalid:
        logger.warning(f"Invalid citations: {invalid}")
        return False
    return True
```

### Expected Impact
- More accurate answers
- Better source attribution
- Clearer indication when information is missing
- Easier to verify AI responses

---

## Testing Strategy

### For Each Feature:
1. Write tests first (TDD approach)
2. Implement feature
3. Run specific test: `pytest tests/vectorgit/test_<feature>.py -v`
4. Run full suite: `pytest tests/vectorgit/ -v`
5. Run smoke test: `bash smoke_test.sh`

### Test Coverage Goals:
- Unit tests for new functions
- Integration tests for workflows
- Performance tests for scale
- Edge case tests for robustness

---

## Validation Checklist

Before considering Phase 1 complete:

- [ ] All tests pass (pytest)
- [ ] Smoke test passes
- [ ] Performance benchmarks show improvements
- [ ] Documentation updated
- [ ] Code review completed
- [ ] No regressions in existing functionality

---

## Future Enhancements (Phase 2+)

### After Phase 1.4:
1. **Query Caching**: Cache recent query results
2. **Batch Processing**: Parallel ingest for large repos
3. **Index Compression**: Reduce memory for 100K+ chunks
4. **Streaming Results**: Yield results as they're found
5. **Query Expansion**: Auto-expand queries with synonyms
6. **Relevance Feedback**: Learn from user interactions

### External Integrations:
1. **Vector Databases**: Qdrant, Postgres+pgvector
2. **Search Engines**: Elasticsearch, Meilisearch
3. **Monitoring**: Prometheus metrics, Grafana dashboards
4. **Analytics**: Track search patterns, improve ranking

---

## Questions? Issues?

- Check `PHASE_1_ROADMAP.md` for architecture details
- Run `pytest tests/vectorgit/ -v` to verify system health
- See memory store for additional context: `store_memory` tool

**Remember**: Make obvious mature changes, leave clear docs for what's next!
