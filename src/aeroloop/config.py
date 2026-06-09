import os
import yaml
from pathlib import Path

class AeroLoopConfig:
    """
    Centralized configuration management for AeroLoop.
    Handles environment variables, app.yaml config, output directory generation, and resource paths.
    """
    def __init__(self):
        # Load from app.yaml first
        self.config_data = {}
        config_path = Path(__file__).parent.parent.parent / "configs" / "app.yaml"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config_data = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")

        # Helper to get config with fallback
        def get_cfg(section, key, env_key, default):
            val = self.config_data.get(section, {}).get(key)
            if val is not None:
                return val
            return os.getenv(env_key, default)

        # Base settings
        self.base_output_dir = get_cfg("workflow", "base_output_dir", "AEROLOOP_OUTPUT_DIR", "results")
        self.default_user_id = get_cfg("workflow", "default_user_id", "AEROLOOP_USER_ID", "default_user")
        
        # Orchestrator limits
        self.max_workflow_iterations = int(get_cfg("workflow", "recursion_limit", "AEROLOOP_MAX_ITERATIONS", 20))

        # LLM Settings
        self.llm_model_name = get_cfg("llm", "model_name", "AEROLOOP_LLM_MODEL", "gpt-5.4-mini")
        self.llm_temperature = float(get_cfg("llm", "temperature", "AEROLOOP_LLM_TEMP", 0.0))

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
