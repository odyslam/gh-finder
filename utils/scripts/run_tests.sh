#!/bin/bash
# Interactive test runner for GitHub Finder

echo "🧪 GitHub Finder Test Runner"
echo "=========================="
echo ""
echo "Select a test to run:"
echo "1) Simple PR Analysis Test (quick)"
echo "2) Comprehensive Test Suite (thorough)"
echo "3) Run both tests"
echo "4) Run ALL tests with summary (recommended)"
echo "5) Run tests with pytest"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "Running Simple PR Analysis Test..."
        uv run tests/test_pr_analysis.py
        ;;
    2)
        echo "Running Comprehensive Test Suite..."
        uv run tests/test_single_analysis.py
        ;;
    3)
        echo "Running Simple PR Analysis Test first..."
        uv run tests/test_pr_analysis.py
        
        echo ""
        echo "Now running Comprehensive Test Suite..."
        uv run tests/test_single_analysis.py
        ;;
    4)
        echo "Running all tests with comprehensive summary..."
        uv run run_all_tests.py
        ;;
    5)
        echo "Running tests with pytest..."
        if command -v pytest &> /dev/null; then
            pytest tests/
        else
            echo "pytest not found. Installing..."
            uv pip install pytest pytest-asyncio
            pytest tests/
        fi
        ;;
    *)
        echo "Invalid choice. Please run again and select 1-5."
        exit 1
        ;;
esac 