# Hardening Plan - Feasibility Assessment

## Executive Summary

**TL;DR**: The hardening plan is feasible and well-structured. The current approach is sound, but I recommend a slightly different prioritization based on the codebase analysis.

## Assessment Overview

After reviewing the entire codebase, I've assessed each hardening goal for:
1. **Feasibility** - Can it be done with the current architecture?
2. **Impact** - How much does it improve reliability/debuggability?
3. **Effort** - How much work is required?
4. **Dependencies** - What must be done first?

## Findings by Goal

### ✅ Goal 3: Smoke Runner Script
**Status**: COMPLETE  
**Feasibility**: ✅ Trivial - Done!  
**Impact**: 🔥🔥🔥 High - Fast feedback loop  
**Effort**: 🟢 Low - 1-2 hours  
**Assessment**: This was the right first step. Having `./smoke_test.sh` means we can validate changes quickly.

---

### 🔥 Goal 1: Tool-Call Traceability
**Status**: Needs Enhancement  
**Feasibility**: ✅ Easy - Infrastructure exists  
**Impact**: 🔥🔥🔥 High - Critical for debugging  
**Effort**: 🟢 Low - 2-3 hours  

**Current State**:
- ✅ `tool_call_id` exists in all the right places
- ✅ `run_id` exists for run-level tracing
- ⚠️ Logging is inconsistent - some places log, others don't

**Recommendation**: **DO THIS NEXT**
This is high-impact, low-effort. Add structured logging in 3 places:
1. `flow/loops.py` - When tool is called
2. `tool/bases.py` - When tool executes
3. `flow/loops.py` - When result is returned

**Better Approach**:
Instead of scattered logging, create a `TraceLogger` class:
```python
class TraceLogger:
    def __init__(self, run_id: str):
        self.run_id = run_id
    
    def log_tool_call(self, tool_call: ToolCall):
        logger.info(f"[run_id={self.run_id}] [tool_call_id={tool_call.id}] CALL Tool={tool_call.name}")
    
    def log_tool_result(self, result: ToolResult):
        logger.info(f"[run_id={self.run_id}] [tool_call_id={result.tool_call_id}] RESULT success={result.success}")
```
This makes tracing consistent and grep-able.

---

### ✅ Goal 2: Workspace Anchoring
**Status**: Already Strong  
**Feasibility**: ✅ Complete - Just needs tests  
**Impact**: 🔥🔥 Medium - Already working well  
**Effort**: 🟢 Low - 1-2 hours for tests  

**Current State**:
- ✅ `core/sandb.py` enforces workspace isolation perfectly
- ✅ Workspace uses absolute paths (not relative to cwd)
- ✅ All file tools should use workspace (need to verify)

**Recommendation**: **Low Priority**
The implementation is already solid. Just add a test that changes `os.chdir()` and verifies workspace still works.

**Better Approach**: None needed - current approach is excellent.

---

### 🔧 Goal 4: Deterministic Chunk IDs
**Status**: Mostly Done, Needs Verification  
**Feasibility**: ✅ Easy - Already hash-based  
**Impact**: 🔥🔥 Medium - Important for citations  
**Effort**: 🟢 Low - 1-2 hours  

**Current State**:
- ✅ Chunk IDs use content hashing (`chunk_{hash}`)
- ⚠️ Hash includes file path - may change on rename
- ⚠️ No test proving stability

**Recommendation**: **Medium Priority**
Add a test that ingests twice and compares chunk_ids. Then decide: should path be in hash?

**Better Approach**: Consider **content-only hashing**
```python
chunk_hash = hashlib.sha256(chunk_content.encode()).hexdigest()[:16]
chunk_id = f"chunk_{chunk_hash}"
```
This makes chunk_id stable even if file moves. Trade-off: two identical functions in different files get same chunk_id (but that might be okay - they're the same code!).

---

### 🔧 Goal 5: Patch Validation
**Status**: Good Foundation, Needs Enhancement  
**Feasibility**: ✅ Easy - Framework exists  
**Impact**: 🔥🔥 Medium - Prevents bad patches  
**Effort**: 🟡 Medium - 3-4 hours  

**Current State**:
- ✅ `core/patch.py` has validation framework
- ✅ Checks diff format, file existence
- ⚠️ Validation is advisory (warns but doesn't block)
- ⚠️ No comprehensive test suite

**Recommendation**: **Medium Priority**
This is already pretty good. The main gap is test coverage.

**Better Approach**: Add validation levels
```python
class ValidationLevel(Enum):
    STRICT = "strict"    # Block invalid patches
    WARN = "warn"        # Warn but allow
    PERMISSIVE = "permissive"  # Just log

def validate_patch(patch_id: str, level: ValidationLevel = ValidationLevel.WARN):
    # ...
```
This lets humans choose strictness based on context.

---

### ⚠️ Goal 6: Judge Enforcement
**Status**: Needs Careful Consideration  
**Feasibility**: ✅ Easy technically, ⚠️ Complex in practice  
**Impact**: 🔥 Low-Medium - Helpful but can be noisy  
**Effort**: 🟡 Medium - 4-6 hours (includes tuning)  

**Current State**:
- ✅ Judge system is well-implemented
- ✅ Catches many workflow issues
- ⚠️ Judge is optional (can be disabled)
- ⚠️ Judgments are advisory only

**Recommendation**: **CAREFUL - Don't Rush This**
Making judge mandatory could cause false positives to block valid workflows.

**Better Approach**: **Three-tier system**
```python
class JudgmentSeverity(Enum):
    INFO = "info"        # FYI only, don't surface
    WARNING = "warning"  # Surface to model in tool result
    ERROR = "error"      # Block operation, force model to acknowledge

# INFO: "You didn't run tests yet" (don't nag)
# WARNING: "Code was written but tests weren't run" (suggest next step)
# ERROR: "Attempted to write outside workspace" (block it!)
```

Only `ERROR` severity blocks. `WARNING` appears in tool results. `INFO` is silent.

**Why This Matters**: The judge can be wrong. For example:
- Agent writes code, then immediately writes tests (judge sees write before test finishes)
- Agent uses a test framework judge doesn't recognize
- Agent is doing exploratory work (no tests needed yet)

Making judge too strict will frustrate users. Keep it advisory with escalation.

---

### 🔧 Goal 7: Error Shaping
**Status**: Framework Exists, Needs Adoption  
**Feasibility**: ✅ Easy - Just needs migration  
**Impact**: 🔥🔥🔥 High - Better debugging  
**Effort**: 🟡 Medium - 4-6 hours (audit all tools)  

**Current State**:
- ✅ `BlockedBy` taxonomy exists
- ✅ `create_tool_error()` helper exists
- ⚠️ Most tools don't use it yet
- ⚠️ Error messages inconsistent

**Recommendation**: **DO SOON**
This is high-impact for debugging. Consistent errors make it obvious what went wrong.

**Better Approach**: **Gradual migration with validator**
1. Create a test that validates all tool errors have `BlockedBy`
2. Fix tools one-by-one to pass the test
3. Mark test as `pytest.mark.xfail` initially, remove marker when all pass

Example test:
```python
def test_all_tools_use_blocked_by_taxonomy():
    """Verify all tools return errors with BlockedBy taxonomy."""
    registry = create_default_registry()
    
    for tool in registry.get_tools():
        # Try to make tool fail (invalid args, etc.)
        result = await tool.execute({})
        
        if not result.success:
            assert "blocked_by:" in result.error.lower() or \
                   "[blocked_by:" in result.error.lower(), \
                   f"Tool {tool.name} error missing BlockedBy: {result.error}"
```

This test will fail initially but gives you a checklist.

---

### ⚠️ Goal 8: Performance Guardrails
**Status**: Framework Exists, Needs Enforcement  
**Feasibility**: ⚠️ Moderate - Some complexity  
**Impact**: 🔥🔥 Medium - Prevents crashes  
**Effort**: 🔴 High - 6-8 hours  

**Current State**:
- ✅ `check_resources()` circuit breaker exists
- ✅ Resource limits configurable
- ⚠️ Not all expensive operations use it
- ⚠️ No timeout enforcement
- ⚠️ No CPU throttling

**Recommendation**: **Later - After Other Goals**
This is important but complex. The resource checks are already pretty good.

**Better Approach**: **Incremental hardening**

Phase 1 (Easy): Audit expensive tools
```bash
# Find tools that do expensive operations
grep -r "execute" tool/*.py | grep -E "shell|pyexe|fetch"
```
Add `workspace.check_resources()` at the start of each.

Phase 2 (Medium): Add timeout wrapper
```python
async def execute_with_timeout(tool_call: ToolCall, timeout: int = 30) -> ToolResult:
    try:
        return await asyncio.wait_for(
            self.execute(tool_call.arguments),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        return ToolResult(
            tool_call_id=tool_call.id,
            output="",
            error=f"Tool timed out after {timeout}s",
            success=False
        )
```

Phase 3 (Hard): CPU throttling for shell commands
This requires `resource` module (Unix only) or process groups. Skip for now.

---

## Recommended Prioritization

Based on feasibility and impact, here's the **better order**:

### Phase 1: Foundation (2-3 days)
1. ✅ **Smoke Runner** - DONE
2. 🔥 **Tool-Call Traceability** - High impact, easy
3. 🔧 **Error Shaping** - High impact, medium effort

**Why**: These three give you the best debugging experience. When things break, you can trace exactly what happened and why.

### Phase 2: Reliability (2-3 days)
4. 🔧 **Workspace Anchoring Tests** - Quick verification
5. 🔧 **Deterministic Chunk IDs** - Verify stability
6. 🔧 **Patch Validation** - Enhance tests

**Why**: These ensure the system behaves consistently and predictably.

### Phase 3: Safeguards (2-3 days)
7. ⚠️ **Judge Enforcement** - Make it smarter, not just mandatory
8. ⚠️ **Performance Guardrails** - Add timeouts and limits

**Why**: These prevent problems but need careful tuning to avoid false positives.

---

## Alternative Approach: Incremental Hardening

Instead of implementing all 8 goals, consider **continuous hardening**:

1. Add `./smoke_test.sh` ✅ DONE
2. Every time you add a feature, add a smoke test check for it
3. Every time you fix a bug, add regression test to smoke suite
4. Every time error is confusing, improve error shaping for that tool
5. Every time debugging is hard, improve tracing for that path

This way, hardening happens naturally as you build, rather than as a separate project.

---

## Is There a Better Way?

**Question**: Should we do all 8 goals, or focus on a subset?

**Answer**: Focus on **Phase 1 only** (traceability + error shaping), then move to Phase 0.8.

**Reasoning**:
- The system is already pretty solid (good workspace isolation, patch protocol, judge)
- The biggest pain point is debugging - "what tool failed and why?"
- Phase 0.8 (VectorGit) will stress-test the system in new ways
- Better to harden based on real pain points than theoretical ones

**Recommended Next Steps**:
1. ✅ Smoke test - DONE
2. 🔥 Add tool-call traceability (2-3 hours)
3. 🔧 Migrate 3-5 most-used tools to error shaping (2-3 hours)
4. 📋 Document what you learned in HARDENING.md
5. ⏭️ Move to Phase 0.8 and see what breaks

Then, after Phase 0.8, you'll know:
- Which tools are slow (need timeouts)
- Which errors are confusing (need better shaping)
- Which workflows the judge gets wrong (need tuning)

**This is agile hardening**: harden what hurts, not what might hurt someday.

---

## Conclusion

**The plan is good.** The goals are well-chosen and the tests are concrete.

**The approach is sound.** Phase 1 → Phase 2 → Phase 3 makes sense.

**The better way**: Do Phase 1 (traceability + error shaping), then move to Phase 0.8. Let real usage drive the rest of the hardening.

**Why**: You've built a solid foundation. Don't over-engineer before you have real problems. Get to Phase 0.8, stress-test the system, then circle back and harden what actually breaks.

**You're ready.** The hardening plan is your roadmap. You can execute all 8 goals now, or just do Phase 1 and keep building. Either way, you'll be fine.

---

## Final Recommendation

**For a smarter agent**: Implement Phase 1 (goals 1, 3, 7) this week, then start Phase 0.8.

**For maximum reliability**: Implement all 8 goals before Phase 0.8.

**My vote**: Phase 1 only, then Phase 0.8. Real usage will reveal what else needs hardening.
