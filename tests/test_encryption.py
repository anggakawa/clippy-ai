import pytest
from tempfile import TemporaryDirectory
import os
from main import save_config, load_config

def test_full_cycle():
    # Create a temporary directory for testing
    with TemporaryDirectory() as temp_dir:
        # Store the original config path if it exists in main.py
        original_config_path = os.environ.get('CONFIG_PATH', None)
        
        try:
            # Set the config path to use the temporary directory
            temp_config_path = os.path.join(temp_dir, 'config.json')
            os.environ['CONFIG_PATH'] = temp_config_path
            
            # Perform the test
            test_token = "test_token_123"
            save_config(test_token)
            assert load_config()["api_token"] == test_token
            
        finally:
            # Restore the original config path
            if original_config_path:
                os.environ['CONFIG_PATH'] = original_config_path
            else:
                os.environ.pop('CONFIG_PATH', None)