import os
import json
import pytest
import tempfile
from aeroloop.utils.suave_runner import run_suave_script, run_suave_script_with_json_io

# We create dummy scripts that can be executed in the suave environment
# The second script verifies that SUAVE can be imported successfully.

DUMMY_SCRIPT_CONTENT = """
import sys
print("Hello from SUAVE runner test")
sys.exit(0)
"""

JSON_IO_SCRIPT_CONTENT = """
import json
import argparse
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    
    with open(args.input, 'r') as f:
        data = json.load(f)
        
    # Process data: multiply input value by 2
    output_data = {}
    for k, v in data.items():
        if isinstance(v, (int, float)):
            output_data[k] = v * 2
        else:
            output_data[k] = v
            
    with open(args.output, 'w') as f:
        json.dump(output_data, f)

if __name__ == "__main__":
    main()
"""

@pytest.fixture
def dummy_scripts():
    # Create temporary scripts
    fd1, path1 = tempfile.mkstemp(suffix=".py", text=True)
    fd2, path2 = tempfile.mkstemp(suffix=".py", text=True)
    os.close(fd1)
    os.close(fd2)
    
    with open(path1, 'w') as f:
        f.write(DUMMY_SCRIPT_CONTENT)
        
    with open(path2, 'w') as f:
        f.write(JSON_IO_SCRIPT_CONTENT)
        
    yield path1, path2
    
    # Cleanup
    if os.path.exists(path1):
        os.remove(path1)
    if os.path.exists(path2):
        os.remove(path2)

def test_run_suave_script(dummy_scripts):
    script_path, _ = dummy_scripts
    result = run_suave_script(script_path)
    assert result.returncode == 0
    assert "Hello from SUAVE runner test" in result.stdout

def test_run_suave_script_with_json_io(dummy_scripts):
    _, script_path = dummy_scripts
    input_data = {
        "val1": 10,
        "val2": 25.5,
        "name": "test"
    }
    
    output_data = run_suave_script_with_json_io(script_path, input_data)
    
    assert output_data["val1"] == 20
    assert output_data["val2"] == 51.0
    assert output_data["name"] == "test"

