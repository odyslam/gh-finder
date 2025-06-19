#!/bin/bash
# Quick test runner for gh-finder

echo "🧪 Running all gh-finder tests..."
echo ""

# Run the comprehensive test suite
uv run run_all_tests.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed! The tool is ready to use."
    echo ""
    echo "To run gh-finder:"
    echo "  uv run gh_finder.py --config repos_config.toml --analyze-prs"
else
    echo ""
    echo "❌ Some tests failed. Please check the output above."
    exit 1
fi 