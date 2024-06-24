import os
import pytest
import yaml
from pathlib import Path
import subprocess


dir_path = Path(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def config():
    config_file = dir_path / "../config-template.yml"
    with open(config_file) as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)
        return conf


@pytest.fixture(scope="function")
def smtp_server():
    debug_server_process = subprocess.Popen(
        [
            "aiosmtpd",
            "-n",
            "-l",
            f"localhost:8025",
        ]
    )
    yield debug_server_process
    debug_server_process.kill()
