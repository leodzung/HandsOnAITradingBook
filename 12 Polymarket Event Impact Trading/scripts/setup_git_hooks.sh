#!/bin/bash
# Setup script for constraint validation git hooks
#
# This script installs pre-commit hooks that automatically validate
# constraints before allowing commits. This prevents constraint violations
# from being committed to the repository.
#
# Usage:
#   ./scripts/setup_git_hooks.sh

set -e

echo "🔧 Setting up constraint validation git hooks..."

# Check if we're in the right directory
if [ ! -f "CONSTRAINTS.yml" ]; then
    echo "❌ Error: CONSTRAINTS.yml not found. Run this from the project root."
    exit 1
fi

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
fi

# Install the hooks
echo "📌 Installing pre-commit hooks..."
cd .. # Move to repository root
pre-commit install

echo ""
echo "✅ Git hooks installed successfully!"
echo ""
echo "The following hooks will now run before each commit:"
echo "  1. Validate System Constraints (CONSTRAINTS.yml)"
echo "  2. Run Structural Tests (tests/structural/)"
echo ""
echo "To run hooks manually:"
echo "  pre-commit run --all-files"
echo ""
echo "To skip hooks for a specific commit (use sparingly):"
echo "  git commit --no-verify"
echo ""
echo "To uninstall hooks:"
echo "  pre-commit uninstall"
