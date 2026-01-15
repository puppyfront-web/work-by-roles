"""
Forwarding module for backward compatibility.
"""
import sys
import os
from pathlib import Path

# Add the project root to sys.path if not already there
# to allow importing from work_by_roles
root = Path(__file__).parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from work_by_roles.core.engine import *

