"""
LLM Client Loader for loading LLM clients from environment variables and configuration files.

Supports generic LLM client interfaces:
- complete(prompt: str, max_tokens: int) -> str
- chat(messages: List[Dict]) -> str
- callable: client(prompt: str) -> str
"""

import os
import importlib
from pathlib import Path
from typing import Optional, Any, Dict
import warnings

from .exceptions import WorkflowError
from .schema_loader import SchemaLoader


class LLMClientLoader:
    """
    Load LLM client from environment variables or configuration file.
    
    Priority: environment variables > configuration file > None
    """
    
    def __init__(self, workspace_path: Path):
        """
        Initialize LLM client loader.
        
        Args:
            workspace_path: Workspace root path
        """
        self.workspace_path = Path(workspace_path)
        self.config_file = self.workspace_path / ".workflow" / "config.yaml"
    
    def load(self) -> Optional[Any]:
        """
        Load LLM client from environment variables or configuration file.
        
        Returns:
            LLM client instance or None if not configured
        """
        # Try environment variables first
        client = self._load_from_env()
        if client:
            return client
        
        # Try configuration file
        client = self._load_from_config()
        if client:
            return client
        
        return None
    
    def _load_from_env(self) -> Optional[Any]:
        """Load LLM client from environment variables"""
        # Check for OpenAI API key
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            base_url = os.getenv("OPENAI_BASE_URL")
            model = os.getenv("LLM_MODEL")
            return self._create_openai_client(openai_key, model=model, base_url=base_url)
        
        # Check for Anthropic API key
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            model = os.getenv("LLM_MODEL")
            return self._create_anthropic_client(anthropic_key, model=model)
        
        # Check for generic LLM provider
        provider = os.getenv("LLM_PROVIDER")
        api_key = os.getenv("LLM_API_KEY")
        if provider and api_key:
            base_url = os.getenv("LLM_BASE_URL")
            model = os.getenv("LLM_MODEL")
            if provider.lower() == "openai":
                return self._create_openai_client(api_key, model=model, base_url=base_url)
            elif provider.lower() == "anthropic":
                return self._create_anthropic_client(api_key, model=model)
        
        return None
    
    def _load_from_config(self) -> Optional[Any]:
        """Load LLM client from configuration file"""
        if not self.config_file.exists():
            return None
        
        try:
            config_data = SchemaLoader.load_yaml(self.config_file)
            llm_config = config_data.get("llm")
            if not llm_config:
                return None
            
            provider = llm_config.get("provider", "").lower()
            api_key = llm_config.get("api_key")
            
            # If api_key is not in config, try to get from environment
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            
            if not api_key:
                return None
            
            # Get base_url from config or environment
            base_url = llm_config.get("base_url") or os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL")
            
            # Create client based on provider
            if provider == "openai":
                return self._create_openai_client(
                    api_key, 
                    model=llm_config.get("model"),
                    base_url=base_url
                )
            elif provider == "anthropic":
                return self._create_anthropic_client(api_key, model=llm_config.get("model"))
            elif provider == "custom":
                return self._create_custom_client(llm_config.get("custom", {}))
            else:
                # Default: try OpenAI if api_key is provided
                if api_key:
                    return self._create_openai_client(
                        api_key, 
                        model=llm_config.get("model"),
                        base_url=base_url
                    )
        
        except Exception as e:
            warnings.warn(f"Failed to load LLM config from {self.config_file}: {e}")
            return None
        
        return None
    
    def _create_openai_client(
        self, 
        api_key: str, 
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> Optional[Any]:
        """
        Create OpenAI client
        
        Args:
            api_key: API key
            model: Model name (optional)
            base_url: Base URL for API endpoint (optional, for custom endpoints)
        """
        try:
            import openai
            # Try OpenAI v1.x (new API)
            try:
                # Build client kwargs
                client_kwargs = {"api_key": api_key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                
                client = openai.OpenAI(**client_kwargs)
                model = model or os.getenv("LLM_MODEL", "gpt-4")
                
                # Create a wrapper that matches our interface
                class OpenAIWrapper:
                    def __init__(self, client, model):
                        self.client = client
                        self.model = model
                    
                    def complete(self, prompt: str, max_tokens: int = 4096) -> str:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=max_tokens
                        )
                        return response.choices[0].message.content
                    
                    def chat(self, messages):
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages
                        )
                        return response.choices[0].message.content
                
                return OpenAIWrapper(client, model)
            except AttributeError:
                # Fallback to older OpenAI API
                openai.api_key = api_key
                if base_url:
                    openai.api_base = base_url
                model = model or os.getenv("LLM_MODEL", "gpt-4")
                
                class OpenAIWrapper:
                    def __init__(self, model):
                        self.model = model
                    
                    def complete(self, prompt: str, max_tokens: int = 4096) -> str:
                        response = openai.ChatCompletion.create(
                            model=self.model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=max_tokens
                        )
                        return response.choices[0].message.content
                    
                    def chat(self, messages):
                        response = openai.ChatCompletion.create(
                            model=self.model,
                            messages=messages
                        )
                        return response.choices[0].message.content
                
                return OpenAIWrapper(model)
        except ImportError:
            warnings.warn("OpenAI package not installed. Install with: pip install openai")
            return None
        except Exception as e:
            warnings.warn(f"Failed to create OpenAI client: {e}")
            return None
    
    def _create_anthropic_client(self, api_key: str, model: Optional[str] = None) -> Optional[Any]:
        """Create Anthropic client"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            model = model or os.getenv("LLM_MODEL", "claude-3-opus-20240229")
            
            class AnthropicWrapper:
                def __init__(self, client, model):
                    self.client = client
                    self.model = model
                
                def complete(self, prompt: str, max_tokens: int = 4096) -> str:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.content[0].text
                
                def chat(self, messages):
                    # Convert messages format if needed
                    if isinstance(messages, list) and len(messages) > 0:
                        # Extract content from last message
                        last_msg = messages[-1]
                        if isinstance(last_msg, dict):
                            prompt = last_msg.get("content", "")
                        else:
                            prompt = str(last_msg)
                    else:
                        prompt = str(messages)
                    
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.content[0].text
            
            return AnthropicWrapper(client, model)
        except ImportError:
            warnings.warn("Anthropic package not installed. Install with: pip install anthropic")
            return None
        except Exception as e:
            warnings.warn(f"Failed to create Anthropic client: {e}")
            return None
    
    def _create_custom_client(self, custom_config: Dict[str, Any]) -> Optional[Any]:
        """Create custom LLM client from configuration"""
        if not custom_config:
            return None
        
        module_path = custom_config.get("module")
        class_name = custom_config.get("class")
        kwargs = custom_config.get("kwargs", {})
        
        if not module_path or not class_name:
            return None
        
        try:
            module = importlib.import_module(module_path)
            client_class = getattr(module, class_name)
            client = client_class(**kwargs)
            return client
        except Exception as e:
            warnings.warn(f"Failed to create custom LLM client: {e}")
            return None

