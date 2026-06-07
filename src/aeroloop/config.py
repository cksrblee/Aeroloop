import os
from pathlib import Path

class AeroLoopConfig:
    """
    Centralized configuration management for AeroLoop.
    Handles environment variables, output directory generation, and resource paths.
    """
    def __init__(self):
        # Base settings
        self.base_output_dir = os.getenv("AEROLOOP_OUTPUT_DIR", "results")
        self.default_user_id = os.getenv("AEROLOOP_USER_ID", "default_user")
        
        # Orchestrator limits
        self.max_workflow_iterations = int(os.getenv("AEROLOOP_MAX_ITERATIONS", "20"))

    def get_user_dir(self, user_id: str = None) -> Path:
        """Returns the base directory for a specific user."""
        uid = user_id or self.default_user_id
        path = Path(self.base_output_dir) / uid
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_run_dir(self, run_id: str, user_id: str = None) -> Path:
        """
        Returns the directory for a specific run.
        Format: {base_output_dir}/{user_id}/{run_id}/
        """
        uid = user_id or self.default_user_id
        path = Path(self.base_output_dir) / uid / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_vector_db_dir(self) -> Path:
        """
        Returns the persistent directory path for the Vector DB (Chroma).
        Format: {base_output_dir}/vector_db/
        """
        path = Path(self.base_output_dir) / "vector_db"
        path.mkdir(parents=True, exist_ok=True)
        return path

# Global singleton instance
config = AeroLoopConfig()
