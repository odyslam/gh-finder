#!/usr/bin/env python3
"""
Show evaluator weights and decision criteria in a human-readable format.

This script displays the scoring components, weights, and categorization criteria
used by the ProfileEvaluator to help understand how profiles are scored.
"""

import sys
import os
from typing import Dict, List
from tabulate import tabulate

# Add parent directory to path to allow importing from gh_finder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from gh_finder.core.evaluator import ProfileEvaluator

def show_weights():
    """Display the weights used in the ProfileEvaluator"""
    print("\n=== GitHub Finder Profile Evaluation System ===\n")
    
    # Score weights
    weights = [
        ["Followers Score", "5%", "0.05 points per follower (max 10)"],
        ["Repositories Score", "5%", "0.1 points per repo (max 10)"],
        ["Account Age Score", "5%", "1 point per 6 months (max 10)"],
        ["Activity Score", "10%", "Based on profile updates, README, passion projects"],
        ["Rust Language Score", "30%", "Heavy emphasis on Rust usage"],
        ["PR Merger Score", "30%", "Weighted by repository tier importance"],
        ["Cross-Repo Score", "10%", "Activity across multiple repositories"],
        ["Openness Score", "5%", "Signals of hiring interest"]
    ]
    
    print("Scoring Components and Weights:")
    print(tabulate(weights, headers=["Component", "Weight", "Description"], tablefmt="grid"))
    
    # Repository tier system
    tiers = [
        [0, "5x", "Highest priority repositories"],
        [1, "4x", "Very high priority repositories"],
        [2, "3x", "High priority repositories"],
        [3, "2x", "Medium priority repositories"],
        [4, "1x", "Regular priority repositories"],
        ["5+", "0.5x", "Lower priority repositories"]
    ]
    
    print("\nRepository Tier Multipliers:")
    print(tabulate(tiers, headers=["Tier", "Multiplier", "Description"], tablefmt="grid"))
    
    # Rust language scoring
    rust_scoring = [
        ["Primary", "Rust is the most used language", "+10 points"],
        ["Prominent", "Rust usage ≥ 30%", "+7 points"],
        ["Secondary", "Rust usage ≥ 10%", "+3 points"],
        ["Minor", "Some Rust usage", "+1 point"],
        ["None", "No Rust usage", "-5 points"]
    ]
    
    print("\nRust Language Scoring (30% weight):")
    print(tabulate(rust_scoring, headers=["Category", "Criteria", "Score"], tablefmt="grid"))
    
    # PR merger scoring
    print("\nPR Merger Scoring (30% weight):")
    print("- Base score: 2 points per PR")
    print("- Multiplied by tier multiplier (e.g., 5x for tier 0 repos)")
    print("- Capped at 10 points")
    
    # Cross-repo activity
    print("\nCross-Repository Activity (10% weight):")
    print("- 1 point per repo, multiplied by tier multiplier")
    print("- 20% bonus for activity across multiple repos")
    print("- 50% bonus for activity across multiple high-tier repos (tier ≤ 2)")
    
    # Openness signals
    openness = [
        ["Bio keywords", "+6 points", "Hiring interest keywords in bio"],
        ["README keywords", "+5 points", "Hiring interest keywords in profile README"],
        ["Recent activity spike", "+3 points", "Sudden increase in activity"],
        ["Recent passion project", "+2 points", "Recently created personal projects"]
    ]
    
    print("\nOpenness Signals (5% weight):")
    print(tabulate(openness, headers=["Signal", "Score", "Description"], tablefmt="grid"))
    
    # Profile categories
    categories = [
        ["Tier 0/1 Rust Core Contributor", "Primary Rust user with PRs merged to tier 0/1 repos"],
        ["Core Target Repo Contributor", "Multiple PRs merged across different target repos"],
        ["Strong Rust Developer (High Potential)", "Primary Rust user with high total score (>7)"],
        ["Top Developer", "Very high overall score (>8) regardless of language"],
        ["Cross-Target Rust Contributor", "Primary/prominent Rust user active across repos"],
        ["Promising Developer", "Good overall score (>5)"],
        ["Regular Developer", "Default category"]
    ]
    
    print("\nProfile Categories:")
    print(tabulate(categories, headers=["Category", "Criteria"], tablefmt="grid"))
    
    # Note about hiring interest
    print("\nNote: '(Hiring Interest)' is added to any category when openness signals are detected")

if __name__ == "__main__":
    show_weights()