"""
GitHub profile models and types
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

@dataclass
class Repository:
    """GitHub repository information"""
    name: str
    url: str
    description: Optional[str] = None
    stars: int = 0
    language: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class LanguageDetail:
    """Details about a programming language usage"""
    name: str
    bytes: int
    percentage: float

@dataclass
class MergedPRDetail:
    """Details about a user's merged PRs in a repository"""
    repo: str
    pr_count: int
    pr_ids: List[int] = field(default_factory=list)
    tier: int = 99

@dataclass
class CrossRepoDetail:
    """Details about a user's appearance in a repository"""
    repo: str
    tier: int = 99

@dataclass
class ProfileEvaluation:
    """Evaluation of a developer profile"""
    total_score: float
    category: str
    followers_score: float = 0
    repos_score: float = 0
    account_age_score: float = 0
    activity_score: float = 0
    rust_score: float = 0
    rust_prominence: str = "None"
    pr_merger_score: float = 0
    raw_pr_count: int = 0
    merged_pr_details: List[Dict] = field(default_factory=list)
    pr_tiers: List[int] = field(default_factory=list)
    is_pr_merger: bool = False
    highest_pr_tier: Optional[int] = None
    cross_repo_score: float = 0
    cross_repo_count: int = 0
    openness_score: float = 0
    has_openness_signals: bool = False
    explicit_interest_details: List[str] = field(default_factory=list)

class GitHubProfile:
    """GitHub user profile data"""
    
    def __init__(self, username: str = ""):
        """Initialize a new GitHub profile
        
        Args:
            username: GitHub username
        """
        # Basic information
        self.username = username
        self.name = None
        self.company = None
        self.blog = None
        self.location = None
        self.email = None
        self.hireable = None
        self.bio = None
        self.twitter_username = None
        self.profile_url = f"https://github.com/{username}" if username else None
        
        # Stats
        self.public_repos = 0
        self.public_gists = 0
        self.followers = 0
        self.following = 0
        self.created_at = None
        self.updated_at = None
        
        # Openness and hiring signals
        self.open_to_work = False
        self.open_to_hire = False
        self.profile_readme_found = False
        self.bio_keywords_found: List[str] = []  # Initialize for bio analysis
        self.readme_keywords_found: List[str] = [] # Initialize for readme analysis (if used)
        self.explicit_interest_signal: bool = False # Initialize for openness signals
        self.recent_activity_spike_signal: bool = False # Initialize for activity signals
        self.passion_project_signal: bool = False # Initialize for activity/project signals
        self.employer_name: Optional[str] = None # Initialize for employer analysis
        self.employer_domain_match_target_repo: bool = False # Initialize for employer analysis
        
        # Language stats
        self.languages = []
        self.languages_detailed = []
        
        # Repository information
        self.repos = []
        self.top_repos = []
        
        # Contributor and project statistics
        self.repos_appeared_in = []
        self.merged_at = {}
        self.cross_repo_details = []
        self.prs_merged_details = []
        self.is_merger = False
        self.prs_merged = 0
        
        # Match ranking
        self.match_score = 0
        self.scoring_details = {}
        
        # Evaluation
        self.evaluation = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GitHubProfile':
        """Create a GitHubProfile from a dictionary
        
        Args:
            data: Dictionary containing profile data
            
        Returns:
            GitHubProfile: Structured profile object
        """
        # Ensure data is a valid dictionary
        if not data or not isinstance(data, dict):
            # Return a minimal valid profile with just a username
            return cls(username="unknown_user")
            
        # Extract username with fallbacks
        username = data.get('username', data.get('login', 'unknown_user'))
        if not username or not isinstance(username, str):
            username = "unknown_user"
            
        # Extract basic profile data with proper type validation
        profile = cls(username=username)
        
        # Set basic profile fields
        profile.name = data.get('name')
        profile.company = data.get('company')
        profile.blog = data.get('blog')
        profile.location = data.get('location')
        profile.email = data.get('email')
        profile.bio = data.get('bio')
        profile.twitter_username = data.get('twitter_username')
        profile.public_repos = int(data.get('public_repos', 0)) if isinstance(data.get('public_repos'), (int, float)) else 0
        profile.followers = int(data.get('followers', 0)) if isinstance(data.get('followers'), (int, float)) else 0
        profile.following = int(data.get('following', 0)) if isinstance(data.get('following'), (int, float)) else 0
        profile.created_at = data.get('created_at')
        profile.updated_at = data.get('updated_at')
        
        # Set profile URL if not provided
        if 'profile_url' in data:
            profile.profile_url = data.get('profile_url')
        elif profile.username:
            profile.profile_url = f"https://github.com/{profile.username}"
            
        # Add languages if available, ensuring it's a valid list
        if 'languages' in data and isinstance(data.get('languages'), list):
            profile.languages = [str(lang) for lang in data.get('languages', []) if lang]
        else:
            profile.languages = []
            
        # Add detailed language information if available
        if 'languages_detailed' in data and isinstance(data.get('languages_detailed'), list):
            lang_details = []
            for lang_data in data.get('languages_detailed', []):
                if isinstance(lang_data, dict):
                    try:
                        name = lang_data.get('name', '')
                        if not name or not isinstance(name, str):
                            continue
                            
                        bytes_count = int(lang_data.get('bytes', 0)) if isinstance(lang_data.get('bytes'), (int, float)) else 0
                        percentage = float(lang_data.get('percentage', 0)) if isinstance(lang_data.get('percentage'), (int, float)) else 0
                        
                        lang_details.append(LanguageDetail(
                            name=name,
                            bytes=bytes_count,
                            percentage=percentage
                        ))
                    except (ValueError, TypeError):
                        # Skip problematic language entries
                        continue
            profile.languages_detailed = lang_details
        else:
            profile.languages_detailed = []
            
        # Add repositories if available
        if 'top_repos' in data and isinstance(data.get('top_repos'), list):
            repos = []
            for repo_data in data.get('top_repos', []):
                if isinstance(repo_data, dict):
                    try:
                        name = repo_data.get('name', '')
                        if not name or not isinstance(name, str):
                            continue
                            
                        url = repo_data.get('url', '')
                        if not url or not isinstance(url, str):
                            url = f"https://github.com/{profile.username}/{name}"
                            
                        repos.append(Repository(
                            name=name,
                            url=url,
                            description=repo_data.get('description') if isinstance(repo_data.get('description'), (str, type(None))) else None,
                            stars=int(repo_data.get('stars', 0)) if isinstance(repo_data.get('stars'), (int, float)) else 0,
                            language=repo_data.get('language') if isinstance(repo_data.get('language'), (str, type(None))) else None,
                            updated_at=repo_data.get('updated_at') if isinstance(repo_data.get('updated_at'), (str, type(None))) else None
                        ))
                    except (ValueError, TypeError):
                        # Skip problematic repository entries
                        continue
            profile.top_repos = repos
        else:
            profile.top_repos = []
            
        # Add PR merger information with validation
        profile.is_merger = bool(data.get('is_merger', False))
        profile.prs_merged = int(data.get('prs_merged', 0)) if isinstance(data.get('prs_merged'), (int, float)) else 0
        
        if 'prs_merged_details' in data and isinstance(data.get('prs_merged_details'), list):
            pr_details = []
            for pr_data in data.get('prs_merged_details', []):
                if isinstance(pr_data, dict):
                    try:
                        repo = pr_data.get('repo', '')
                        if not repo or not isinstance(repo, str):
                            continue
                            
                        pr_count = int(pr_data.get('pr_count', 0)) if isinstance(pr_data.get('pr_count'), (int, float)) else 0
                        
                        # Validate pr_ids is a list
                        pr_ids = []
                        if 'pr_ids' in pr_data and isinstance(pr_data.get('pr_ids'), list):
                            pr_ids = [int(pr_id) for pr_id in pr_data.get('pr_ids', []) if isinstance(pr_id, (int, float))]
                            
                        tier = int(pr_data.get('tier', 99)) if isinstance(pr_data.get('tier'), (int, float)) else 99
                        
                        pr_details.append(MergedPRDetail(
                            repo=repo,
                            pr_count=pr_count,
                            pr_ids=pr_ids,
                            tier=tier
                        ))
                    except (ValueError, TypeError):
                        # Skip problematic PR detail entries
                        continue
            profile.prs_merged_details = pr_details
        else:
            profile.prs_merged_details = []
            
        # Add cross-repository information
        if 'cross_repo_details' in data and isinstance(data.get('cross_repo_details'), list):
            cross_details = []
            for cross_data in data.get('cross_repo_details', []):
                if isinstance(cross_data, dict):
                    try:
                        repo = cross_data.get('repo', '')
                        if not repo or not isinstance(repo, str):
                            continue
                            
                        tier = int(cross_data.get('tier', 99)) if isinstance(cross_data.get('tier'), (int, float)) else 99
                        
                        cross_details.append(CrossRepoDetail(
                            repo=repo,
                            tier=tier
                        ))
                    except (ValueError, TypeError):
                        # Skip problematic cross-repo entries
                        continue
            profile.cross_repo_details = cross_details
        else:
            profile.cross_repo_details = []
            
        # Add repos appeared in with validation
        if 'repos_appeared_in' in data and isinstance(data.get('repos_appeared_in'), list):
            profile.repos_appeared_in = [str(repo) for repo in data.get('repos_appeared_in', []) if repo and isinstance(repo, str)]
        else:
            profile.repos_appeared_in = []
        
        # Add openness signals with validation
        if 'bio_keywords_found' in data and isinstance(data.get('bio_keywords_found'), list):
            profile.bio_keywords_found = [str(kw) for kw in data.get('bio_keywords_found', []) if kw and isinstance(kw, str)]
        else:
            profile.bio_keywords_found = []
            
        if 'readme_keywords_found' in data and isinstance(data.get('readme_keywords_found'), list):
            profile.readme_keywords_found = [str(kw) for kw in data.get('readme_keywords_found', []) if kw and isinstance(kw, str)]
        else:
            profile.readme_keywords_found = []
            
        # Set boolean flags with validation
        profile.explicit_interest_signal = bool(data.get('explicit_interest_signal', False))
        profile.profile_readme_found = bool(data.get('profile_readme_found', False))
        profile.recent_activity_spike_signal = bool(data.get('recent_activity_spike_signal', False))
        profile.passion_project_signal = bool(data.get('passion_project_signal', False))
        
        # Set string and boolean employer fields with validation
        profile.employer_name = str(data.get('employer_name', '')) if data.get('employer_name') else ''
        profile.employer_domain_match_target_repo = bool(data.get('employer_domain_match_target_repo', False))
        
        # Add evaluation if available
        if 'evaluation' in data and isinstance(data.get('evaluation'), dict):
            eval_data = data.get('evaluation', {})
            
            try:
                # Validate required numeric fields
                total_score = float(eval_data.get('total_score', 0)) if isinstance(eval_data.get('total_score'), (int, float)) else 0
                
                # Validate category string
                category = str(eval_data.get('category', 'Unknown')) if eval_data.get('category') else 'Unknown'
                
                profile.evaluation = ProfileEvaluation(
                    total_score=total_score,
                    category=category,
                    followers_score=float(eval_data.get('followers_score', 0)) if isinstance(eval_data.get('followers_score'), (int, float)) else 0,
                    repos_score=float(eval_data.get('repos_score', 0)) if isinstance(eval_data.get('repos_score'), (int, float)) else 0,
                    account_age_score=float(eval_data.get('account_age_score', 0)) if isinstance(eval_data.get('account_age_score'), (int, float)) else 0,
                    activity_score=float(eval_data.get('activity_score', 0)) if isinstance(eval_data.get('activity_score'), (int, float)) else 0,
                    rust_score=float(eval_data.get('rust_score', 0)) if isinstance(eval_data.get('rust_score'), (int, float)) else 0,
                    rust_prominence=str(eval_data.get('rust_prominence', 'None')) if eval_data.get('rust_prominence') else 'None',
                    pr_merger_score=float(eval_data.get('pr_merger_score', 0)) if isinstance(eval_data.get('pr_merger_score'), (int, float)) else 0,
                    raw_pr_count=int(eval_data.get('raw_pr_count', 0)) if isinstance(eval_data.get('raw_pr_count'), (int, float)) else 0,
                    merged_pr_details=eval_data.get('merged_pr_details', []) if isinstance(eval_data.get('merged_pr_details'), list) else [],
                    pr_tiers=eval_data.get('pr_tiers', []) if isinstance(eval_data.get('pr_tiers'), list) else [],
                    is_pr_merger=bool(eval_data.get('is_pr_merger', False)),
                    highest_pr_tier=int(eval_data.get('highest_pr_tier')) if isinstance(eval_data.get('highest_pr_tier'), (int, float)) else None,
                    cross_repo_score=float(eval_data.get('cross_repo_score', 0)) if isinstance(eval_data.get('cross_repo_score'), (int, float)) else 0,
                    cross_repo_count=int(eval_data.get('cross_repo_count', 0)) if isinstance(eval_data.get('cross_repo_count'), (int, float)) else 0,
                    openness_score=float(eval_data.get('openness_score', 0)) if isinstance(eval_data.get('openness_score'), (int, float)) else 0,
                    has_openness_signals=bool(eval_data.get('has_openness_signals', False)),
                    explicit_interest_details=eval_data.get('explicit_interest_details', []) if isinstance(eval_data.get('explicit_interest_details'), list) else []
                )
            except (ValueError, TypeError) as e:
                # If evaluation creation fails, create a minimal valid evaluation
                profile.evaluation = ProfileEvaluation(
                    total_score=0,
                    category="Unknown",
                    followers_score=0,
                    repos_score=0
                )
            
        return profile
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the profile to a dictionary
        
        Returns:
            Dict: Dictionary representation of the profile
        """
        # Start with basic profile data
        data = {
            'username': self.username,
            'name': self.name,
            'bio': self.bio,
            'company': self.company,
            'location': self.location,
            'email': self.email,
            'blog': self.blog,
            'twitter_username': self.twitter_username,
            'public_repos': self.public_repos,
            'followers': self.followers,
            'following': self.following,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'profile_url': self.profile_url
        }
        
        # Add languages
        data['languages'] = self.languages
        
        # Add detailed language information
        if self.languages_detailed:
            data['languages_detailed'] = [
                {
                    'name': lang.name,
                    'bytes': lang.bytes,
                    'percentage': lang.percentage
                }
                for lang in self.languages_detailed
            ]
            
        # Add repositories
        if self.top_repos:
            data['top_repos'] = [
                {
                    'name': repo.name,
                    'url': repo.url,
                    'description': repo.description,
                    'stars': repo.stars,
                    'language': repo.language,
                    'updated_at': repo.updated_at
                }
                for repo in self.top_repos
            ]
            
        # Add PR merger information
        data['is_merger'] = self.is_merger
        data['prs_merged'] = self.prs_merged
        
        if self.prs_merged_details:
            data['prs_merged_details'] = [
                {
                    'repo': pr.repo,
                    'pr_count': pr.pr_count,
                    'pr_ids': pr.pr_ids,
                    'tier': pr.tier
                }
                for pr in self.prs_merged_details
            ]
            
        # Add cross-repository information
        if self.cross_repo_details:
            data['cross_repo_details'] = [
                {
                    'repo': cr.repo,
                    'tier': cr.tier
                }
                for cr in self.cross_repo_details
            ]
            
        # Add repos appeared in
        data['repos_appeared_in'] = self.repos_appeared_in
        
        # Add openness signals
        data['bio_keywords_found'] = self.bio_keywords_found
        data['readme_keywords_found'] = self.readme_keywords_found
        data['explicit_interest_signal'] = self.explicit_interest_signal
        data['profile_readme_found'] = self.profile_readme_found
        data['recent_activity_spike_signal'] = self.recent_activity_spike_signal
        data['passion_project_signal'] = self.passion_project_signal
        data['employer_name'] = self.employer_name
        data['employer_domain_match_target_repo'] = self.employer_domain_match_target_repo
        
        # Add evaluation if available
        if self.evaluation:
            data['evaluation'] = {
                'total_score': self.evaluation.total_score,
                'category': self.evaluation.category,
                'followers_score': self.evaluation.followers_score,
                'repos_score': self.evaluation.repos_score,
                'account_age_score': self.evaluation.account_age_score,
                'activity_score': self.evaluation.activity_score,
                'rust_score': self.evaluation.rust_score,
                'rust_prominence': self.evaluation.rust_prominence,
                'pr_merger_score': self.evaluation.pr_merger_score,
                'raw_pr_count': self.evaluation.raw_pr_count,
                'merged_pr_details': self.evaluation.merged_pr_details,
                'pr_tiers': self.evaluation.pr_tiers,
                'is_pr_merger': self.evaluation.is_pr_merger,
                'highest_pr_tier': self.evaluation.highest_pr_tier,
                'cross_repo_score': self.evaluation.cross_repo_score,
                'cross_repo_count': self.evaluation.cross_repo_count,
                'openness_score': self.evaluation.openness_score,
                'has_openness_signals': self.evaluation.has_openness_signals,
                'explicit_interest_details': self.evaluation.explicit_interest_details
            }
            
        return data 