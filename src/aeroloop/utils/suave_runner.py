import subprocess
import json
import os
import tempfile
from typing import Any, Dict

def run_suave_script(script_path: str, args: list = None, env_name: str = "suave") -> subprocess.CompletedProcess:
    """
    Run a python script in the specified conda environment.
    
    Args:
        script_path (str): The path to the python script to run.
        args (list, optional): Additional arguments to pass to the script. Defaults to None.
        env_name (str, optional): The name of the conda environment to use. Defaults to "suave".
        
    Returns:
        subprocess.CompletedProcess: The result of the subprocess run.
    """
    if args is None:
        args = []
        
    cmd = ["conda", "run", "-n", env_name, "python", script_path] + args
    
    # Run the command and capture output
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=os.environ.copy()
    )
    
    if result.returncode != 0:
        print(f"Error running SUAVE script: {result.stderr}")
        
    return result

def run_suave_script_with_json_io(script_path: str, input_data: Dict[str, Any], temp_dir: str = "/tmp", env_name: str = "suave") -> Dict[str, Any]:
    """
    Run a SUAVE script, passing input and output via temporary JSON files.
    
    Args:
        script_path (str): The path to the SUAVE script.
        input_data (dict): The input data to pass to the script.
        temp_dir (str, optional): Directory to store temporary I/O files. Defaults to "/tmp".
        env_name (str, optional): The name of the conda environment. Defaults to "suave".
        
    Returns:
        dict: The output data from the SUAVE script.
    """
    # Create temp files for input and output
    fd_in, input_file = tempfile.mkstemp(suffix=".json", dir=temp_dir, text=True)
    fd_out, output_file = tempfile.mkstemp(suffix=".json", dir=temp_dir, text=True)
    
    os.close(fd_in)
    os.close(fd_out)
    
    try:
        # Write input data
        with open(input_file, 'w') as f:
            json.dump(input_data, f)
            
        # Run script with file paths as arguments
        result = run_suave_script(script_path, args=["--input", input_file, "--output", output_file], env_name=env_name)
        
        if result.returncode != 0:
            raise RuntimeError(f"SUAVE script execution failed:\n{result.stderr}\n{result.stdout}")
            
        # Read output data
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            with open(output_file, 'r') as f:
                output_data = json.load(f)
            return output_data
        else:
            return {}
            
    finally:
        # Cleanup temp files
        if os.path.exists(input_file):
            os.remove(input_file)
        if os.path.exists(output_file):
            os.remove(output_file)
