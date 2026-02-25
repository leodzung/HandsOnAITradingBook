# Documentation Cleanup Plan

## Problem
We have **104 markdown files** which violates harness engineering principles.

## Harness Engineering Principle
> "If you need documentation to explain how to use a system, the system isn't well-designed."

Documentation should be:
- ✅ **Executable** (CONSTRAINTS.yml, not markdown)
- ✅ **Self-documenting code** (good names, clear structure)
- ✅ **Git commits** (historical record)
- ❌ NOT 104 markdown files that get stale

## Cleanup Strategy

### Phase 1: Consolidate into README.md

Create ONE comprehensive README.md with:
- Quick start (5 minutes to running)
- Architecture diagram
- Key concepts (PriceFetcher, PositionManager, etc.)
- How to use constraint validation
- Development workflow

### Phase 2: Extract Critical Info to Code

Move implementation details to:
- Inline code comments (for "why" not "what")
- Docstrings in functions/classes
- Type hints and clear naming

### Phase 3: Delete Redundant Files

**Delete these categories:**
1. **Completion summaries** (info in git commits)
   - *_COMPLETE.md files
   - *_SUMMARY.md files
   - *_IMPLEMENTATION.md files

2. **Fix documentation** (info in git commits)
   - *_FIX.md files
   - *_ISSUE*.md files
   - *_DIAGNOSIS.md files

3. **Usage guides** (info in README or code comments)
   - *_USAGE.md files
   - *_GUIDE.md files
   - *_EXPLAINED.md files

4. **Duplicate documentation**
   - Multiple files on same topic
   - Keep only most recent/comprehensive

### Phase 4: Keep Only Essential Docs

**Final state (5-7 files):**
1. README.md - Comprehensive quick start + architecture
2. CONSTRAINTS.yml - Machine-readable constraints (executable!)
3. CONTRIBUTING.md - How to contribute (if open source)
4. CHANGELOG.md - High-level changes (optional)
5. .gitignore - What not to commit
6. LICENSE - If applicable

## Benefits

✅ **Less maintenance** - 5 files instead of 104
✅ **Single source of truth** - No contradictions
✅ **Self-documenting** - Code explains itself
✅ **Executable constraints** - CONSTRAINTS.yml enforces rules
✅ **Git as documentation** - Commit messages tell the story

## Implementation

### Step 1: Create comprehensive README.md
Extract essential info from all docs into ONE file

### Step 2: Move implementation details to code
Add comments/docstrings where needed

### Step 3: Delete redundant markdown files
```bash
# Backup first
mkdir -p archive/old_docs
mv *.md archive/old_docs/
mv archive/old_docs/README.md .
mv archive/old_docs/CONSTRAINTS.yml .
```

### Step 4: Update MEMORY.md
Remove references to deleted docs, point to:
- README.md for architecture
- CONSTRAINTS.yml for rules
- Git commits for history
- Code comments for implementation details

## Next Steps

1. Review this plan
2. Create comprehensive README.md
3. Execute cleanup (backup first!)
4. Update MEMORY.md
5. Commit cleanup

## Harness Engineering Alignment

After cleanup:
- ✅ Machine-readable constraints (CONSTRAINTS.yml)
- ✅ Self-documenting code
- ✅ Minimal documentation (README.md only)
- ✅ Git commits as historical record
- ✅ No stale docs to maintain
