"""
AI Prompt Generator

Generates structured markdown prompts from GitHub profile data for use with AI assistants.
"""

from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any, Optional


def generate_ai_prompt(profiles: List[Dict[str, Any]], output_file: Optional[str] = None) -> str:
    """
    Generate a structured AI prompt from GitHub profile data
    
    Args:
        profiles: List of profile dictionaries with evaluation data
        output_file: Optional path to save the prompt to a file (can be string or Path object)
        
    Returns:
        str: The generated prompt text
    """
    if not profiles:
        print("❌ No profiles to generate AI prompt")
        return ""
        
    # Detailed debug output
    print(f"🔍 generate_ai_prompt called with {len(profiles)} profiles")
    print(f"🔍 Output file path: {output_file}")
    
    # Categorize profiles
    categories = defaultdict(list)
    for profile in profiles:
        if 'evaluation' in profile:
            categories[profile['evaluation']['category']].append(profile)
            
    # Sort each category by score
    for category in categories:
        categories[category].sort(key=lambda p: p['evaluation'].get('total_score', 0), reverse=True)
        
    # Start building the prompt
    prompt = "# GitHub Developer Analysis\n\n"
    prompt += f"I've analyzed {len(profiles)} GitHub profiles and identified promising developers.\n"
    prompt += "Please review these candidates and help determine who might be good potential hires:\n\n"
    
    # Generate content for each category
    category_order = [
        cat for cat, _ in sorted(categories.items(), 
                                 key=lambda x: (0 if "Outstanding" in x[0] else 
                                              1 if "Excellent" in x[0] else 
                                              2 if "Very Good" in x[0] else 
                                              3 if "Good" in x[0] else 
                                              4 if "Average" in x[0] else 5))
    ]
    
    # Go through each category
    for category in category_order:
        profiles = categories[category]
        prompt += f"## {category} ({len(profiles)} developers)\n\n"
        
        # Add top profiles from each category (up to 5)
        for profile in profiles[:5]:
            name = profile.get('name') or profile.get('username')
            prompt += f"### {name} (Score: {profile['evaluation']['total_score']:.1f})\n"
            prompt += f"- **GitHub Profile**: https://github.com/{profile['username']}\n"
            
            # Add basic profile info
            if profile.get('location'):
                prompt += f"- **Location**: {profile['location']}\n"
            if profile.get('company'):
                prompt += f"- **Company**: {profile['company']}\n"
            if profile.get('email'):
                prompt += f"- **Email**: {profile['email']}\n"
            if profile.get('blog'):
                prompt += f"- **Blog/Website**: {profile['blog']}\n"
            if profile.get('twitter_username'):
                prompt += f"- **Twitter**: @{profile['twitter_username']}\n"
            
            # Add GitHub stats
            prompt += f"- **GitHub Stats**: {profile.get('followers', 0)} followers, {profile.get('public_repos', 0)} repositories\n"
            
            # Add openness signals
            if profile['evaluation'].get('has_openness_signals'):
                prompt += "- **Hiring Signals**: "
                signals = []
                
                if profile.get('explicit_interest_signal'):
                    signals.append("Explicitly open to new opportunities")
                
                if profile.get('recent_activity_spike_signal'):
                    signals.append("Recent activity spike (potential job seeking)")
                
                if profile['evaluation'].get('explicit_interest_details'):
                    for detail in profile['evaluation']['explicit_interest_details']:
                        signals.append(detail)
                        
                prompt += ", ".join(signals) + "\n"
            
            # Add PR merger information
            if profile.get('is_merger'):
                prompt += f"- **Pull Requests**: Merged {profile.get('prs_merged', 0)} PRs"
                if profile['evaluation'].get('highest_pr_tier'):
                    tier_text = ""
                    if profile['evaluation']['highest_pr_tier'] == 1:
                        tier_text = "(Tier 1 - Core Contributor)"
                    elif profile['evaluation']['highest_pr_tier'] == 2:
                        tier_text = "(Tier 2 - Key Contributor)"
                    elif profile['evaluation']['highest_pr_tier'] == 3:
                        tier_text = "(Tier 3 - Regular Contributor)"
                    elif profile['evaluation']['highest_pr_tier'] == 4:
                        tier_text = "(Tier 4 - Occasional Contributor)"
                    
                    prompt += f" {tier_text}\n"
                else:
                    prompt += "\n"
            
            # Add languages
            if profile.get('languages'):
                prompt += f"- **Top Languages**: {', '.join(profile['languages'][:5])}\n"
            
            # Add bio
            if profile.get('bio'):
                prompt += f"- **Bio**: {profile['bio']}\n"
            
            # Add top repositories
            if profile.get('top_repos'):
                prompt += "- **Notable Repositories**:\n"
                for i, repo in enumerate(profile['top_repos'][:3]):
                    stars = f"⭐ {repo.get('stars', 0)}" if repo.get('stars', 0) > 0 else ""
                    prompt += f"  - [{repo.get('name', '')}]({repo.get('url', '')}) {stars} - {repo.get('description', '') or 'No description'}\n"
            
            prompt += "\n"
    
    # Add analysis instructions
    prompt += """
## Request for Analysis

Based on these profiles, please help me:

1. Identify the most promising candidates for technical roles
2. Highlight any candidates who have explicitly shown interest in new opportunities
3. Point out any notable skills or accomplishments that stand out
4. Recommend specific candidates to prioritize for outreach

Thank you!
"""

    # Save the prompt to file if path provided
    if output_file:
        try:
            # Convert Path to string if needed
            file_path = Path(output_file)
            
            print(f"🔍 Saving AI prompt to: {file_path} (absolute: {file_path.absolute()})")
            print(f"🔍 Parent directory: {file_path.parent}")
            print(f"🔍 Parent exists: {file_path.parent.exists()}")
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"🔍 After mkdir - Parent exists: {file_path.parent.exists()}")
            
            # Write prompt to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
                print(f"🔍 Write operation successful")
            
            # Verify the file exists after writing
            print(f"🔍 After write - File exists: {file_path.exists()}")
            if file_path.exists():
                print(f"🔍 File size: {file_path.stat().st_size} bytes")
                print(f"🔍 File permissions: {oct(file_path.stat().st_mode)[-3:]}")
            
            print(f"\n✅ AI prompt saved to {file_path}")
            print(f"   File size: {file_path.stat().st_size} bytes")
            print("You can use this file with your preferred AI assistant for in-depth candidate analysis.")
        except Exception as e:
            print(f"❌ Error saving AI prompt: {str(e)}")
            print(f"   Path provided: {output_file}")
            print(f"   Directory exists: {Path(output_file).parent.exists()}")
            import traceback
            traceback.print_exc()

    return prompt


def save_ai_prompt(prompt: str, file_path: str) -> bool:
    """
    Save the AI prompt to a file
    
    Args:
        prompt: The prompt text to save
        file_path: Path to save the file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write prompt to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        return True
    except Exception as e:
        print(f"❌ Error saving AI prompt: {str(e)}")
        return False 