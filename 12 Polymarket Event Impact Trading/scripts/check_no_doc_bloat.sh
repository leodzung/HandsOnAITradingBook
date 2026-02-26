#!/bin/bash
#
# Check for Documentation Bloat (OPS-003)
#
# Enforces: Only README.md, CONSTRAINTS.yml, and IMPROVEMENT_CHECKLIST.md allowed
# Forbidden: *COMPLETE.md, *SUMMARY.md, *GUIDE.md, docs/*.md, etc.
#
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Checking for documentation bloat (OPS-003)..."

# Allowed markdown files
ALLOWED=(
    "README.md"
    "CONSTRAINTS.yml"
    "IMPROVEMENT_CHECKLIST.md"
)

# Find all .md files (excluding archive, .git, node_modules, .pytest_cache)
FOUND_MD_FILES=$(find . -name "*.md" -not -path "./archive/*" -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./.pytest_cache/*" -not -path "./.claude/*" | sort)

# Check each found file
VIOLATIONS=0
for file in $FOUND_MD_FILES; do
    # Remove leading ./
    file_clean="${file#./}"
    
    # Check if it's in allowed list
    is_allowed=0
    for allowed in "${ALLOWED[@]}"; do
        if [[ "$file_clean" == "$allowed" ]]; then
            is_allowed=1
            break
        fi
    done
    
    if [[ $is_allowed -eq 0 ]]; then
        echo "❌ VIOLATION: Unauthorized markdown file: $file_clean"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Check for forbidden patterns
FORBIDDEN_PATTERNS=(
    "*COMPLETE.md"
    "*SUMMARY.md"
    "*GUIDE.md"
    "*IMPLEMENTATION*.md"
    "docs/*.md"
)

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    matches=$(find . -name "$pattern" -not -path "./archive/*" -not -path "./.git/*" -not -path "./.pytest_cache/*" -not -path "./.claude/*" 2>/dev/null || true)
    if [[ -n "$matches" ]]; then
        echo "❌ VIOLATION: Forbidden pattern '$pattern' matched:"
        echo "$matches"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Report
if [[ $VIOLATIONS -eq 0 ]]; then
    echo "✅ OPS-003 PASS: No documentation bloat detected"
    echo "   Allowed files:"
    for allowed in "${ALLOWED[@]}"; do
        if [[ -f "$allowed" ]]; then
            echo "     - $allowed"
        fi
    done
    exit 0
else
    echo ""
    echo "❌ OPS-003 FAIL: $VIOLATIONS documentation bloat violation(s)"
    echo ""
    echo "Reminder: Code + tests + git commits are the documentation."
    echo "If you need markdown docs to explain it, redesign it."
    exit 1
fi
