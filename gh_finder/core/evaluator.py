"""
Profile evaluation and scoring
"""

import datetime
from typing import Dict, List, Any, Optional, Tuple

from ..models.profile import GitHubProfile, ProfileEvaluation

class ProfileEvaluator:
    """Evaluates and scores GitHub profiles"""
    
    def __init__(self, verbose: bool = False):
        """Initialize the profile evaluator
        
        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
        
    def _get_tier_multiplier(self, tier: int, max_tier: int = 8) -> float:
        """Calculate a multiplier based on repository tier
        
        Lower tier (more important) = higher multiplier.
        
        Args:
            tier: Repository tier (0 is highest priority)
            max_tier: Maximum tier value for scaling
            
        Returns:
            float: Multiplier value
        """
        if tier is None or not isinstance(tier, int) or tier < 0:
            return 0.5  # Default to a low multiplier if tier is unknown
        
        # Example: Tier 0 -> 5x, Tier 1 -> 4x, ..., Tier 4 -> 1x, Tier 5+ -> 0.5x
        multiplier = max(0.5, (max_tier // 2 + 1) - tier)
        return multiplier
        
    def evaluate_profile(self, profile: GitHubProfile) -> ProfileEvaluation:
        """Evaluate a GitHub profile and assign scores
        
        Args:
            profile: GitHub profile to evaluate
            
        Returns:
            ProfileEvaluation: Evaluation results
        """
        # Initialize evaluation object
        evaluation = ProfileEvaluation(
            total_score=0,
            category="Unknown"
        )
        
        # Calculate individual scores
        self._calculate_followers_score(profile, evaluation)
        self._calculate_repos_score(profile, evaluation)
        self._calculate_account_age_score(profile, evaluation)
        self._calculate_activity_score(profile, evaluation)
        self._calculate_language_score(profile, evaluation)
        self._calculate_pr_merger_score(profile, evaluation)
        self._calculate_cross_repo_score(profile, evaluation)
        self._calculate_openness_score(profile, evaluation)
        
        # Calculate total score (weighted sum)
        # Updated weights to emphasize Rust and PR merges
        evaluation.total_score = (
            evaluation.followers_score * 0.05 +    # Reduced from 0.15
            evaluation.repos_score * 0.05 +        # Reduced from 0.15
            evaluation.account_age_score * 0.05 +  # Reduced from 0.10
            evaluation.activity_score * 0.10 +     # Same
            evaluation.rust_score * 0.30 +         # Increased from 0.15
            evaluation.pr_merger_score * 0.30 +    # Increased from 0.20
            evaluation.cross_repo_score * 0.10 +   # Same
            evaluation.openness_score * 0.05       # Same
        )
        
        # Categorize profile
        self._categorize_profile(profile, evaluation)
        
        # Store evaluation in profile
        profile.evaluation = evaluation
        
        return evaluation
    
    def _calculate_followers_score(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Calculate score based on number of followers
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        followers = profile.followers
        
        # Simpler and more subdued scale - max 10 points
        # Using min to cap the score
        evaluation.followers_score = min(followers * 0.05, 10)
    
    def _calculate_repos_score(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Calculate score based on number of public repositories
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        repos = profile.public_repos
        
        # Simpler and more subdued scale - max 10 points
        # Using min to cap the score
        evaluation.repos_score = min(repos * 0.1, 10)
    
    def _calculate_account_age_score(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Calculate score based on account age
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        if not profile.created_at:
            evaluation.account_age_score = 0
            return
            
        try:
            created_date = datetime.datetime.fromisoformat(profile.created_at.replace("Z", "+00:00"))
            now = datetime.datetime.now(datetime.timezone.utc)
            age_days = (now - created_date).days
            
            # More gradual scaling based on days
            # Max 10 points, approximately 1 point per 6 months (180 days)
            evaluation.account_age_score = min(age_days / 180, 10)
            
        except Exception:
            evaluation.account_age_score = 0
    
    def _calculate_activity_score(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Calculate score based on activity indicators
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        # Start with base score based on profile update recency
        score = 0
        
        # Check profile updated_at for recency
        if profile.updated_at:
            try:
                updated_date = datetime.datetime.fromisoformat(profile.updated_at.replace("Z", "+00:00"))
                now = datetime.datetime.now(datetime.timezone.utc)
                days_since_update = (now - updated_date).days
                
                # More gradual drop, max 5 points for recency
                recency_score = max(0, 5 - (days_since_update * 0.05))
                score += recency_score
            except Exception:
                pass  # Ignore date parsing errors
                
        # Having a profile README is an activity signal
        if profile.profile_readme_found:
            score += 1
            
        # Recent passion project activity
        if profile.passion_project_signal:
            score += 2
            
        # Recent activity spike is a strong signal
        if profile.recent_activity_spike_signal:
            score += 2
            
        # Cap at 10
        evaluation.activity_score = min(10, score)
    
    def _calculate_language_score(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Calculate score based on programming language usage
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        # Stronger emphasis on Rust
        
        # Check for Rust in top languages
        rust_percentage = 0
        rust_prominence = "None"
        rust_score = 0
        
        # First check if Rust is the primary language (first in the list)
        if profile.languages_detailed and profile.languages_detailed[0].name.lower() == "rust":
            rust_prominence = "Primary"
            rust_score = 10  # Max score for Rust as primary language
            
        else:
            # Not primary, check if present and at what percentage
            for lang in profile.languages_detailed:
                if lang.name.lower() == "rust":
                    rust_percentage = lang.percentage
                    
                    # Categorize Rust prominence
                    if rust_percentage >= 30:
                        rust_prominence = "Prominent"
                        rust_score = 7
                    elif rust_percentage >= 10:
                        rust_prominence = "Secondary"
                        rust_score = 3
                    else:
                        rust_prominence = "Minor"
                        rust_score = 1
                    
                    break
            
            # Apply penalty if Rust is not found at all
            if rust_prominence == "None":
                rust_score = -5  # Penalty for no Rust (scaled to 10-point system)
        
        evaluation.rust_score = rust_score
        evaluation.rust_prominence = rust_prominence
    
    def _calculate_pr_merger_score(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Calculate score based on PR merger status with tier weighting
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        # Set raw PR count
        evaluation.raw_pr_count = profile.prs_merged
        
        # Set merger flag
        evaluation.is_pr_merger = profile.is_merger
        
        # Convert PR details
        if profile.prs_merged_details:
            evaluation.merged_pr_details = [
                {
                    "repo": pr.repo,
                    "pr_count": pr.pr_count,
                    "tier": pr.tier
                }
                for pr in profile.prs_merged_details
            ]
            
            # Extract tiers
            evaluation.pr_tiers = [pr.tier for pr in profile.prs_merged_details]
            evaluation.highest_pr_tier = min(evaluation.pr_tiers) if evaluation.pr_tiers else None
        
        # Calculate score based on PR merger status with tier weighting
        if not profile.is_merger:
            # Not a merger
            evaluation.pr_merger_score = 0
        else:
            # Calculate weighted score based on tier and count
            weighted_score = 0
            
            for pr in profile.prs_merged_details:
                tier_multiplier = self._get_tier_multiplier(pr.tier)
                pr_contribution_score = pr.pr_count * 2 * tier_multiplier  # Base 2 points per PR, scaled by tier
                weighted_score += pr_contribution_score
                
            # Cap at 10 for consistency with other scores
            evaluation.pr_merger_score = min(10, weighted_score)
    
    def _calculate_cross_repo_score(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Calculate score based on cross-repository activity with tier weighting
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        # Count distinct repositories
        evaluation.cross_repo_count = len(profile.repos_appeared_in)
        
        # Calculate tier-weighted score
        weighted_score = 0
        
        # Keep track of distinct repos by tier
        tier_repos = {}
        
        # Process all cross-repo details
        for cr in profile.cross_repo_details:
            # Get the tier or default to lowest
            tier = cr.tier if hasattr(cr, 'tier') else 99
            
            # Keep track of repos by tier
            if tier not in tier_repos:
                tier_repos[tier] = set()
            tier_repos[tier].add(cr.repo)
            
            # Calculate tier multiplier
            tier_multiplier = self._get_tier_multiplier(tier)
            
            # Add weighted score for this repo appearance
            weighted_score += 1 * tier_multiplier  # Base 1 point per repo, scaled by tier
            
        # Add bonus for appearing in multiple repositories
        if evaluation.cross_repo_count > 1:
            weighted_score *= 1.2  # 20% bonus for multiple repos
            
        # Add extra bonus for appearing in multiple high-tier repositories
        high_tier_count = sum(len(repos) for tier, repos in tier_repos.items() if tier <= 2)
        if high_tier_count > 1:
            weighted_score *= 1.5  # 50% bonus for multiple high-tier repos
            
        # Cap at 10 for consistency with other scores
        evaluation.cross_repo_score = min(10, weighted_score)
    
    def _calculate_openness_score(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Calculate score based on openness to work signals
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        # Check for all signals
        has_bio_signals = len(profile.bio_keywords_found) > 0
        has_readme_signals = len(profile.readme_keywords_found) > 0
        has_activity_spike = profile.recent_activity_spike_signal
        has_passion_project = profile.passion_project_signal
        
        # Calculate score
        score = 0
        
        # Bio signals are strongest
        if has_bio_signals:
            score += 6
            evaluation.explicit_interest_details.extend([f"Bio: {kw}" for kw in profile.bio_keywords_found])
            
        # README signals are next strongest
        if has_readme_signals:
            score += 5
            evaluation.explicit_interest_details.extend([f"README: {kw}" for kw in profile.readme_keywords_found])
            
        # Activity spike is a moderate signal
        if has_activity_spike:
            score += 3
            evaluation.explicit_interest_details.append("Recent activity spike")
            
        # Passion project is a weak signal
        if has_passion_project:
            score += 2
            evaluation.explicit_interest_details.append("Recent passion project activity")
            
        # Cap at 10
        evaluation.openness_score = min(10, score)
        
        # Set flag if any openness signals were found
        evaluation.has_openness_signals = (score > 0)
    
    def _categorize_profile(self, profile: GitHubProfile, evaluation: ProfileEvaluation) -> None:
        """Categorize the profile based on evaluation scores
        
        Args:
            profile: GitHub profile to evaluate
            evaluation: Evaluation object to update
        """
        # Updated categorization logic focusing on Rust and high-tier contributions
        
        # Check for Rust primary and tier 0/1 contributions
        if (evaluation.rust_prominence == "Primary" and 
            evaluation.is_pr_merger and 
            evaluation.highest_pr_tier is not None and
            evaluation.highest_pr_tier <= 1):
            # Top tier contributor
            category = "Tier 0/1 Rust Core Contributor"
            
        # Check for strong contribution across repos    
        elif (evaluation.is_pr_merger and 
              evaluation.raw_pr_count >= 3 and
              evaluation.cross_repo_count > 1):
            category = "Core Target Repo Contributor"
            
        # Check for primary Rust users with high scores
        elif (evaluation.rust_prominence == "Primary" and 
              evaluation.total_score > 7):
            category = "Strong Rust Developer (High Potential)"
            
        # Check for very high scores regardless of language
        elif evaluation.total_score > 8:
            category = "Top Developer"
            
        # Check for cross-repo Rust developers
        elif (evaluation.rust_prominence in ["Primary", "Prominent"] and
              evaluation.cross_repo_count > 1):
            category = "Cross-Target Rust Contributor"
            
        # Check for promising developers
        elif evaluation.total_score > 5:
            category = "Promising Developer"
            
        # Default category
        else:
            category = "Regular Developer"
            
        # Modify category based on openness signals
        if evaluation.has_openness_signals:
            # Add "Hiring Interest" to category
            category = f"{category} (Hiring Interest)"
            
        evaluation.category = category 