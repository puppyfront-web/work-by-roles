from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Any, Optional

class BaseValidator(ABC):
    """Base class for all quality gate validators."""
    
    @abstractmethod
    def validate(self, gate: Any, stage: Any, workspace_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a quality gate.
        
        Args:
            gate: The quality gate configuration.
            stage: The workflow stage.
            workspace_path: Path to the workspace root.
            
        Returns:
            Tuple of (passed: bool, errors: List[str])
        """
        pass

