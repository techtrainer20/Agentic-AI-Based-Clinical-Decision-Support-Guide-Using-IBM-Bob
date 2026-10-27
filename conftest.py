"""
conftest.py – project-root pytest configuration.
Adds the workspace root to sys.path so 'import app' works from any
directory pytest is invoked from.
"""

import sys
from pathlib import Path

# Insert the project root (this file's directory) at the front of sys.path.
sys.path.insert(0, str(Path(__file__).parent))
