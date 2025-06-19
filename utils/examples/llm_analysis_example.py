#!/usr/bin/env python3
"""
Example: Using GitHub Profile Finder with LLM Analysis

This script demonstrates how to generate LLM-friendly output for analyzing
developer profiles with AI assistance.
"""

import subprocess
import sys

def main():
    print("GitHub Profile Finder - LLM Analysis Example")
    print("=" * 80)
    
    if len(sys.argv) < 2:
        print("❌ Please provide your GitHub token as an argument")
        print("Usage: python llm_analysis_example.py YOUR_GITHUB_TOKEN")
        sys.exit(1)
    
    token = sys.argv[1]
    
    print("\n🎯 This example will:")
    print("1. Analyze top Rust/EVM repositories")
    print("2. Generate a detailed report for LLM analysis")
    print("3. Save it to a markdown file you can paste into Claude/GPT")
    
    # Create a minimal config for demonstration
    demo_config = """
# Demo configuration - Top Rust/EVM projects
repositories = [
    # Tier 0 - Highest priority
    [
        { name = "paradigmxyz/reth", label = "Reth" },
        { name = "bluealloy/revm", label = "REVM" }
    ]
]
"""
    
    with open("demo_config.toml", "w") as f:
        f.write(demo_config)
    
    print("\n📋 Running analysis on key repositories...")
    print("This will find developers who have forked these projects")
    print("(Add --analyze-prs flag to find PR contributors instead)\n")
    
    # Run the analysis with LLM output
    cmd = [
        "python", "-m", "gh_finder.main",
        "--config", "demo_config.toml",
        "--token", token,
        "--limit", "20",  # Limit to 20 users per repo for demo
        "--llm-output", "auto",  # Auto-generate filename
        "--verbose"
    ]
    
    subprocess.run(cmd)
    
    print("\n✅ Analysis complete!")
    print("\n📝 Next steps:")
    print("1. Look for the generated llm_analysis_*.md file")
    print("2. Copy its contents into Claude, GPT-4, or your preferred LLM")
    print("3. Ask the LLM to analyze the candidates and provide recommendations")
    print("\nExample prompts for the LLM:")
    print("- 'Which developers would be the best fit for contributing to a Rust EVM implementation?'")
    print("- 'Identify developers who show strong systems programming skills'")
    print("- 'Which candidates have the most relevant experience for low-level optimization work?'")
    print("- 'Find developers who might be interested in remote work opportunities'")

if __name__ == "__main__":
    main() 