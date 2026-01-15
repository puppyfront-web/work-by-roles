"""
Checkpoint manager for workflow state recovery.
"""

import uuid
import yaml
import json
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .models import Checkpoint, ExecutionState
from .workflow_progress_manager import WorkflowProgressManager, WorkflowProgress


class CheckpointManager:
    """Manages workflow checkpoints for state recovery"""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.checkpoints_dir = workspace_path / ".workflow" / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    def create_checkpoint(
        self,
        workflow_id: str,
        execution_state: ExecutionState,
        progress_manager: Optional[WorkflowProgressManager] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        stage_id: Optional[str] = None,
        context_snapshot: Optional[Dict[str, Any]] = None,
        output_files: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Checkpoint:
        """
        Create a checkpoint for workflow state recovery.
        
        Args:
            workflow_id: Workflow ID
            execution_state: Current execution state
            progress_manager: Optional progress manager to capture progress
            name: Optional checkpoint name (auto-generated if not provided)
            description: Optional checkpoint description
            stage_id: Optional current stage ID
            context_snapshot: Optional context snapshot
            output_files: Optional list of output files
            metadata: Optional metadata
            
        Returns:
            Created checkpoint
        """
        checkpoint_id = f"checkpoint_{uuid.uuid4().hex[:12]}"
        
        if not name:
            if stage_id:
                name = f"Checkpoint at {stage_id}"
            else:
                name = f"Checkpoint {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Capture progress data if progress manager provided
        progress_data = None
        if progress_manager and progress_manager.current_progress:
            progress_data = progress_manager.current_progress.to_dict()
        
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            name=name,
            description=description,
            created_at=datetime.now(),
            workflow_id=workflow_id,
            stage_id=stage_id,
            execution_state=execution_state,
            progress_data=progress_data,
            context_snapshot=context_snapshot or {},
            output_files=output_files or [],
            metadata=metadata or {}
        )
        
        # Save checkpoint
        self._save_checkpoint(checkpoint)
        
        return checkpoint
    
    def list_checkpoints(self, workflow_id: Optional[str] = None) -> List[Checkpoint]:
        """
        List all checkpoints, optionally filtered by workflow_id.
        
        Args:
            workflow_id: Optional workflow ID to filter by
            
        Returns:
            List of checkpoints
        """
        checkpoints = []
        
        # If workflow_id specified, only check that workflow's directory
        if workflow_id:
            workflow_dir = self.checkpoints_dir / workflow_id
            if workflow_dir.exists():
                checkpoint_files = list(workflow_dir.glob("*.yaml"))
            else:
                return []
        else:
            # Check all workflow directories
            checkpoint_files = []
            for workflow_dir in self.checkpoints_dir.iterdir():
                if workflow_dir.is_dir():
                    checkpoint_files.extend(workflow_dir.glob("*.yaml"))
        
        for checkpoint_file in checkpoint_files:
            # Skip state and progress files (they're part of checkpoint data)
            if checkpoint_file.name.endswith("_state.yaml") or checkpoint_file.name.endswith("_progress.json"):
                continue
            
            try:
                checkpoint = self._load_checkpoint(checkpoint_file)
                if checkpoint:
                    checkpoints.append(checkpoint)
            except Exception as e:
                warnings.warn(f"Failed to load checkpoint from {checkpoint_file}: {e}")
                continue
        
        # Sort by creation time, most recent first
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return checkpoints
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """
        Get checkpoint by ID.
        
        Args:
            checkpoint_id: Checkpoint ID
            
        Returns:
            Checkpoint or None if not found
        """
        # Search all workflow directories
        for workflow_dir in self.checkpoints_dir.iterdir():
            if not workflow_dir.is_dir():
                continue
            
            checkpoint_file = workflow_dir / f"{checkpoint_id}.yaml"
            if checkpoint_file.exists():
                return self._load_checkpoint(checkpoint_file)
        
        return None
    
    def get_latest_checkpoint(self, workflow_id: str) -> Optional[Checkpoint]:
        """
        Get the latest checkpoint for a workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Latest checkpoint or None if not found
        """
        checkpoints = self.list_checkpoints(workflow_id)
        return checkpoints[0] if checkpoints else None
    
    def restore_from_checkpoint(
        self,
        checkpoint_id: str,
        engine: Any,
        progress_manager: Optional[WorkflowProgressManager] = None
    ) -> Dict[str, Any]:
        """
        Restore workflow state from a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint ID to restore from
            engine: WorkflowEngine instance
            progress_manager: Optional progress manager to restore progress
            
        Returns:
            Dict with restoration result
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint '{checkpoint_id}' not found")
        
        # Restore execution state
        if checkpoint.execution_state and engine.executor:
            engine.executor.state = checkpoint.execution_state
            engine.save_state()
        
        # Restore progress if progress manager provided
        if progress_manager and checkpoint.progress_data:
            try:
                progress = WorkflowProgress.from_dict(checkpoint.progress_data)
                progress_manager.current_progress = progress
                progress_manager._save_progress()
            except Exception as e:
                warnings.warn(f"Failed to restore progress: {e}")
        
        return {
            "checkpoint_id": checkpoint_id,
            "workflow_id": checkpoint.workflow_id,
            "stage_id": checkpoint.stage_id,
            "restored_at": datetime.now().isoformat(),
            "execution_state_restored": checkpoint.execution_state is not None,
            "progress_restored": checkpoint.progress_data is not None
        }
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return False
        
        # Delete checkpoint files
        workflow_dir = self.checkpoints_dir / checkpoint.workflow_id
        checkpoint_file = workflow_dir / f"{checkpoint_id}.yaml"
        state_file = workflow_dir / f"{checkpoint_id}_state.yaml"
        progress_file = workflow_dir / f"{checkpoint_id}_progress.json"
        
        deleted = False
        for file in [checkpoint_file, state_file, progress_file]:
            if file.exists():
                try:
                    file.unlink()
                    deleted = True
                except Exception as e:
                    warnings.warn(f"Failed to delete {file}: {e}")
        
        return deleted
    
    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to disk"""
        workflow_dir = self.checkpoints_dir / checkpoint.workflow_id
        workflow_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_file = workflow_dir / f"{checkpoint.checkpoint_id}.yaml"
        
        try:
            # Save main checkpoint data
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                yaml.dump(checkpoint.to_dict(), f, default_flow_style=False, allow_unicode=True)
            
            # Optionally save state and progress separately for easier access
            if checkpoint.execution_state:
                state_file = workflow_dir / f"{checkpoint.checkpoint_id}_state.yaml"
                with open(state_file, 'w', encoding='utf-8') as f:
                    yaml.dump(checkpoint.execution_state.to_dict(), f, default_flow_style=False, allow_unicode=True)
            
            if checkpoint.progress_data:
                progress_file = workflow_dir / f"{checkpoint.checkpoint_id}_progress.json"
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(checkpoint.progress_data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            raise RuntimeError(f"Failed to save checkpoint: {e}") from e
    
    def _load_checkpoint(self, checkpoint_file: Path) -> Optional[Checkpoint]:
        """Load checkpoint from file"""
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if not data:
                    return None
                return Checkpoint.from_dict(data)
        except Exception as e:
            warnings.warn(f"Failed to load checkpoint from {checkpoint_file}: {e}")
            return None

