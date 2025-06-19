"""
Run context management for capturing and storing run information
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

class TeeOutput:
    """Class to duplicate stdout to a log file"""
    def __init__(self, log_file):
        self.terminal = sys.stdout
        self.log_file = log_file
        self.log = open(log_file, 'w', encoding='utf-8')
        
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
        
    def flush(self):
        self.terminal.flush()
        self.log.flush()
        
    def close(self):
        self.log.close()

class RunContext:
    """Manages a single run of the tool with its own directory and logging"""
    def __init__(self):
        # Create runs directory if it doesn't exist
        Path("./runs").mkdir(exist_ok=True)
        
        # Create a timestamp-based directory for this run
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = Path(f"./runs/{self.timestamp}")
        self.run_dir.mkdir(exist_ok=True)
        
        # Create checkpoints directory
        self.checkpoint_dir = self.run_dir / "checkpoints"
        self.checkpoint_dir.mkdir(exist_ok=True)
        
        # Set up log file
        self.log_file = self.run_dir / "output.log"
        self.tee = TeeOutput(self.log_file)
        sys.stdout = self.tee
        
        # Set up other file paths
        self.ai_prompt_file = self.run_dir / "ai_prompt.txt"
        self.config_file_copy = self.run_dir / "config.toml"
        self.profiles_file = self.run_dir / "profiles.json"
        
        print(f"Run started at: {self.timestamp}")
        print(f"Output being logged to: {self.log_file}")
        
    def save_config(self, original_config_path):
        """Save a copy of the config file used for this run"""
        if original_config_path and Path(original_config_path).exists():
            shutil.copy2(original_config_path, self.config_file_copy)
            print(f"Config file copied to: {self.config_file_copy}")
        
    def cleanup(self):
        """Clean up resources at the end of a run"""
        sys.stdout = sys.__stdout__
        self.tee.close()
        print(f"Run completed. All output saved to: {self.log_file}")

# Global run context for module access
current_run = None 