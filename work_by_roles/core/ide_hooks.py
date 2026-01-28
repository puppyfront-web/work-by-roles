"""
IDE Hooks System - Cross-platform IDE integration hooks.
Provides hooks for different IDEs to trigger workflow execution without relying on IDE-specific features.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from .exceptions import WorkflowError


class IDEType(Enum):
    """Supported IDE types"""
    VS_CODE = "vscode"
    CURSOR = "cursor"
    PYCHARM = "pycharm"
    NEOVIM = "neovim"
    VIM = "vim"
    UNKNOWN = "unknown"


class IDEHooksManager:
    """Manages IDE hooks for cross-platform workflow execution"""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self.workflow_dir = self.workspace_path / ".workflow"
        self.hooks_dir = self.workflow_dir / "hooks"
        self.hooks_dir.mkdir(parents=True, exist_ok=True)
    
    def detect_ide(self) -> IDEType:
        """Detect current IDE environment"""
        env = os.environ
        
        # Check for Cursor
        if env.get('CURSOR_APP') or env.get('CURSOR'):
            return IDEType.CURSOR
        
        term_program = env.get('TERM_PROGRAM', '').lower()
        if 'cursor' in term_program:
            return IDEType.CURSOR
        
        # Check for VS Code
        if env.get('VSCODE_PID') or env.get('VSCODE_INJECTION'):
            return IDEType.VS_CODE
        
        if term_program == 'vscode':
            return IDEType.VS_CODE
        
        # Check for PyCharm
        if env.get('PYCHARM_HOSTED') or 'pycharm' in env.get('IDE', '').lower():
            return IDEType.PYCHARM
        
        # Check for Neovim/Vim
        if env.get('NVIM') or env.get('NVIM_LISTEN_ADDRESS'):
            return IDEType.NEOVIM
        
        if env.get('VIM'):
            return IDEType.VIM
        
        return IDEType.UNKNOWN
    
    def install_hooks(self, ide_type: Optional[IDEType] = None) -> Dict[str, Any]:
        """
        Install hooks for specified IDE or auto-detect.
        
        Args:
            ide_type: Optional IDE type, if None will auto-detect
            
        Returns:
            Dict with installation results
        """
        if ide_type is None:
            ide_type = self.detect_ide()
        
        results = {
            "ide": ide_type.value,
            "installed": [],
            "failed": []
        }
        
        if ide_type == IDEType.VS_CODE or ide_type == IDEType.CURSOR:
            self._install_vscode_hooks(results)
        
        if ide_type == IDEType.PYCHARM:
            self._install_pycharm_hooks(results)
        
        if ide_type == IDEType.NEOVIM or ide_type == IDEType.VIM:
            self._install_neovim_hooks(results)
        
        # Install generic hooks (work for any IDE)
        self._install_generic_hooks(results)
        
        return results
    
    def _install_vscode_hooks(self, results: Dict[str, Any]) -> None:
        """Install VS Code/Cursor hooks (tasks.json)"""
        vscode_dir = self.workspace_path / ".vscode"
        vscode_dir.mkdir(exist_ok=True)
        
        tasks_file = vscode_dir / "tasks.json"
        
        # Load existing tasks or create new
        if tasks_file.exists():
            try:
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    tasks_config = json.load(f)
            except:
                tasks_config = {"version": "2.0.0", "tasks": []}
        else:
            tasks_config = {"version": "2.0.0", "tasks": []}
        
        # Add workflow tasks if not exist
        existing_labels = {task.get("label", "") for task in tasks_config.get("tasks", [])}
        
        workflow_tasks = [
            {
                "label": "Workflow: Team Execute",
                "type": "shell",
                "command": "workflow",
                "args": ["wfauto", "--intent", "${input:intent}"],
                "problemMatcher": [],
                "presentation": {
                    "reveal": "always",
                    "panel": "dedicated"
                }
            },
            {
                "label": "Workflow: Auto Execute",
                "type": "shell",
                "command": "workflow",
                "args": ["wfauto"],
                "problemMatcher": [],
                "presentation": {
                    "reveal": "always",
                    "panel": "dedicated"
                }
            }
        ]
        
        for task in workflow_tasks:
            if task["label"] not in existing_labels:
                tasks_config.setdefault("tasks", []).append(task)
        
        # Add input prompt for intent
        if "inputs" not in tasks_config:
            tasks_config["inputs"] = []
        
        intent_input = {
            "id": "intent",
            "type": "promptString",
            "description": "Enter your intent/goal for the workflow"
        }
        
        if not any(inp.get("id") == "intent" for inp in tasks_config["inputs"]):
            tasks_config["inputs"].append(intent_input)
        
        try:
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_config, f, indent=2, ensure_ascii=False)
            results["installed"].append(f"VS Code tasks.json: {tasks_file}")
        except Exception as e:
            results["failed"].append(f"VS Code tasks.json: {e}")
    
    def _install_pycharm_hooks(self, results: Dict[str, Any]) -> None:
        """Install PyCharm hooks (run configurations)"""
        idea_dir = self.workspace_path / ".idea"
        idea_dir.mkdir(exist_ok=True)
        run_configs_dir = idea_dir / "runConfigurations"
        run_configs_dir.mkdir(exist_ok=True)
        
        configs = [
            {
                "name": "Workflow Team Execute",
                "type": "python",
                "request": "launch",
                "program": "${workspaceFolder}/.venv/bin/workflow",
                "args": ["wfauto", "--intent", "${input:INTENT}"],
                "console": "integratedTerminal",
                "justMyCode": False
            },
            {
                "name": "Workflow Auto Execute",
                "type": "python",
                "request": "launch",
                "program": "${workspaceFolder}/.venv/bin/workflow",
                "args": ["wfauto"],
                "console": "integratedTerminal",
                "justMyCode": False
            }
        ]
        
        for config in configs:
            config_file = run_configs_dir / f"{config['name'].replace(' ', '_')}.xml"
            try:
                # PyCharm uses XML format
                xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="{config['name']}" type="PythonConfigurationType" factoryName="Python">
    <module name="" />
    <option name="INTERPRETER_OPTIONS" value="" />
    <option name="PARENT_ENVS" value="true" />
    <envs />
    <option name="SDK_HOME" value="" />
    <option name="WORKING_DIRECTORY" value="$PROJECT_DIR$" />
    <option name="IS_MODULE_SDK" value="true" />
    <option name="ADD_CONTENT_ROOTS" value="true" />
    <option name="ADD_SOURCE_ROOTS" value="true" />
    <EXTENSION ID="PythonCoverageRunConfigurationExtension" runner="coverage.py" />
    <option name="SCRIPT_NAME" value="workflow" />
    <option name="PARAMETERS" value="{' '.join(config['args'])}" />
    <option name="SHOW_COMMAND_LINE" value="false" />
    <option name="EMULATE_TERMINAL" value="false" />
    <option name="MODULE_MODE" value="false" />
    <option name="REDIRECT_INPUT" value="false" />
    <option name="INPUT_FILE" value="" />
    <method v="2" />
  </configuration>
</component>"""
                config_file.write_text(xml_content, encoding='utf-8')
                results["installed"].append(f"PyCharm run config: {config_file}")
            except Exception as e:
                results["failed"].append(f"PyCharm run config {config['name']}: {e}")
    
    def _install_neovim_hooks(self, results: Dict[str, Any]) -> None:
        """Install Neovim/Vim hooks (keybindings)"""
        nvim_config = self.hooks_dir / "neovim_hooks.lua"
        vim_config = self.hooks_dir / "vim_hooks.vim"
        
        # Neovim Lua config
        nvim_content = """-- Workflow Hooks for Neovim
-- Add to your init.lua or source this file

local function workflow_execute(intent)
    local cmd = "workflow wfauto"
    if intent and intent ~= "" then
        cmd = cmd .. " --intent '" .. intent .. "'"
    end
    
    vim.cmd("!" .. cmd)
end

-- Keybindings (add to your keymap config)
-- vim.keymap.set("n", "<leader>wt", function()
--     vim.ui.input({prompt = "Intent: "}, function(input)
--         workflow_execute(input)
--     end)
-- end, {desc = "Workflow: Team Execute"})
--
-- vim.keymap.set("n", "<leader>wa", function()
--     workflow_execute()
-- end, {desc = "Workflow: Auto Execute"})
"""
        
        # Vim config
        vim_content = """\" Workflow Hooks for Vim
\" Source this file or add to your .vimrc

function! WorkflowExecute(intent)
    let cmd = "!workflow wfauto"
    if a:intent != ""
        let cmd = cmd . " --intent '" . a:intent . "'"
    endif
    execute cmd
endfunction

\" Keybindings (uncomment to use)
\" nnoremap <leader>wt :call WorkflowExecute(input("Intent: "))<CR>
\" nnoremap <leader>wa :call WorkflowExecute("")<CR>
"""
        
        try:
            nvim_config.write_text(nvim_content, encoding='utf-8')
            results["installed"].append(f"Neovim hooks: {nvim_config}")
        except Exception as e:
            results["failed"].append(f"Neovim hooks: {e}")
        
        try:
            vim_config.write_text(vim_content, encoding='utf-8')
            results["installed"].append(f"Vim hooks: {vim_config}")
        except Exception as e:
            results["failed"].append(f"Vim hooks: {e}")
    
    def _install_generic_hooks(self, results: Dict[str, Any]) -> None:
        """Install generic hooks (shell scripts, aliases)"""
        # Shell script for workflow execution
        script_file = self.hooks_dir / "workflow-hook.sh"
        script_content = """#!/bin/bash
# Workflow Hook Script
# Usage: ./workflow-hook.sh [intent]

INTENT="${1:-}"
if [ -n "$INTENT" ]; then
    workflow wfauto --intent "$INTENT"
else
    workflow wfauto
fi
"""
        
        try:
            script_file.write_text(script_content, encoding='utf-8')
            script_file.chmod(0o755)
            results["installed"].append(f"Generic hook script: {script_file}")
        except Exception as e:
            results["failed"].append(f"Generic hook script: {e}")
        
        # Aliases file
        aliases_file = self.hooks_dir / "aliases.sh"
        aliases_content = """# Workflow Aliases
# Source this file: source .workflow/hooks/aliases.sh

alias wt='workflow wfauto --intent'
alias wa='workflow wfauto'
"""
        
        try:
            aliases_file.write_text(aliases_content, encoding='utf-8')
            results["installed"].append(f"Aliases file: {aliases_file}")
        except Exception as e:
            results["failed"].append(f"Aliases file: {e}")
    
    def list_hooks(self) -> Dict[str, List[str]]:
        """List installed hooks"""
        hooks = {
            "vscode": [],
            "pycharm": [],
            "neovim": [],
            "vim": [],
            "generic": []
        }
        
        # Check VS Code
        vscode_tasks = self.workspace_path / ".vscode" / "tasks.json"
        if vscode_tasks.exists():
            hooks["vscode"].append(str(vscode_tasks))
        
        # Check PyCharm
        idea_dir = self.workspace_path / ".idea" / "runConfigurations"
        if idea_dir.exists():
            hooks["pycharm"] = [str(f) for f in idea_dir.glob("*.xml")]
        
        # Check Neovim/Vim
        if (self.hooks_dir / "neovim_hooks.lua").exists():
            hooks["neovim"].append(str(self.hooks_dir / "neovim_hooks.lua"))
        
        if (self.hooks_dir / "vim_hooks.vim").exists():
            hooks["vim"].append(str(self.hooks_dir / "vim_hooks.vim"))
        
        # Check generic
        if (self.hooks_dir / "workflow-hook.sh").exists():
            hooks["generic"].append(str(self.hooks_dir / "workflow-hook.sh"))
        
        if (self.hooks_dir / "aliases.sh").exists():
            hooks["generic"].append(str(self.hooks_dir / "aliases.sh"))
        
        return hooks
