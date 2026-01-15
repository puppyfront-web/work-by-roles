"""
State storage for persisting workflow execution state.
Following Single Responsibility Principle - handles state persistence only.
"""

import yaml
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .models import ExecutionState


class StateStorage(ABC):
    """Abstract base class for state storage backends"""
    
    @abstractmethod
    def save(self, state: ExecutionState, path: Path) -> None:
        """Save execution state to storage"""
        pass
    
    @abstractmethod
    def load(self, path: Path) -> Optional[ExecutionState]:
        """Load execution state from storage, returns None if not found"""
        pass
    
    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Check if state exists at path"""
        pass


class FileStateStorage(StateStorage):
    """File-based state storage implementation"""
    
    def save(self, state: ExecutionState, path: Path) -> None:
        """Save execution state to YAML file"""
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = state.to_dict()
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            # Graceful degradation: log warning but don't interrupt workflow
            warnings.warn(f"Failed to save state to {path}: {e}", UserWarning)
    
    def load(self, path: Path) -> Optional[ExecutionState]:
        """Load execution state from YAML file"""
        if not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data is None:
                    return None
                return ExecutionState.from_dict(data)
        except Exception as e:
            # Graceful degradation: log warning and return None
            warnings.warn(f"Failed to load state from {path}: {e}. Starting with fresh state.", UserWarning)
            return None
    
    def exists(self, path: Path) -> bool:
        """Check if state file exists"""
        return path.exists()

