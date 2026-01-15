"""
Agent Message Bus for inter-agent communication.
Following Single Responsibility Principle - handles message passing only.
"""

from typing import Dict, List, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

from .exceptions import WorkflowError


@dataclass
class AgentMessage:
    """Agent 间消息"""
    from_agent: str
    to_agent: str  # "*" for broadcast
    message_type: str  # "request", "response", "notification", "context_share"
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = ""
    
    def __post_init__(self):
        """Generate message ID if not provided"""
        if not self.message_id:
            self.message_id = f"{self.from_agent}_{self.to_agent}_{self.timestamp.timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """Create from dictionary"""
        return cls(
            message_id=data.get("message_id", ""),
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            message_type=data["message_type"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))
        )


class AgentMessageBus:
    """
    Agent 间消息总线
    
    提供 agent 之间的消息传递、上下文共享和广播功能。
    支持消息持久化（可选）。
    """
    
    def __init__(self, persist_messages: bool = False, messages_dir: Optional[Path] = None):
        """
        Initialize Agent Message Bus.
        
        Args:
            persist_messages: If True, persist messages to disk
            messages_dir: Directory to store messages (default: .workflow/messages/)
        """
        self.messages: Dict[str, List[AgentMessage]] = defaultdict(list)
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self.persist_messages = persist_messages
        self.messages_dir = messages_dir
        
        if persist_messages and messages_dir:
            messages_dir.mkdir(parents=True, exist_ok=True)
    
    def publish(
        self, 
        from_agent: str, 
        to_agent: str, 
        message_type: str,
        content: Dict[str, Any]
    ) -> str:
        """
        Publish a message to a specific agent.
        
        Args:
            from_agent: Source agent ID
            to_agent: Target agent ID (use "*" for broadcast)
            message_type: Type of message ("request", "response", "notification", "context_share")
            content: Message content
            
        Returns:
            Message ID
        """
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content
        )
        
        if to_agent == "*":
            # Broadcast to all agents
            for agent_id in self.messages.keys():
                if agent_id != from_agent:
                    self.messages[agent_id].append(message)
        else:
            self.messages[to_agent].append(message)
        
        # Persist if enabled
        if self.persist_messages and self.messages_dir:
            self._persist_message(message)
        
        return message.message_id
    
    def subscribe(self, agent_id: str) -> List[AgentMessage]:
        """
        Subscribe to messages (get all unread messages for an agent).
        
        Args:
            agent_id: Agent ID to get messages for
            
        Returns:
            List of unread messages (messages are removed after reading)
        """
        messages = self.messages.get(agent_id, [])
        # Clear messages after reading
        self.messages[agent_id] = []
        return messages
    
    def peek_messages(self, agent_id: str) -> List[AgentMessage]:
        """
        Peek at messages without removing them.
        
        Args:
            agent_id: Agent ID to peek messages for
            
        Returns:
            List of unread messages (messages are NOT removed)
        """
        return self.messages.get(agent_id, [])
    
    def share_context(self, agent_id: str, context: Dict[str, Any]):
        """
        Share context with other agents.
        
        Args:
            agent_id: Agent ID sharing the context
            context: Context data to share
        """
        self.contexts[agent_id] = context
    
    def get_context(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get shared context from an agent.
        
        Args:
            agent_id: Agent ID to get context for
            
        Returns:
            Shared context or None if not found
        """
        return self.contexts.get(agent_id)
    
    def get_all_contexts(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all shared contexts.
        
        Returns:
            Dictionary mapping agent IDs to their contexts
        """
        return self.contexts.copy()
    
    def broadcast(
        self, 
        from_agent: str, 
        message_type: str, 
        content: Dict[str, Any]
    ) -> List[str]:
        """
        Broadcast a message to all agents.
        
        Args:
            from_agent: Source agent ID
            message_type: Type of message
            content: Message content
            
        Returns:
            List of message IDs (one per recipient)
        """
        return [self.publish(from_agent, "*", message_type, content)]
    
    def clear_messages(self, agent_id: Optional[str] = None):
        """
        Clear messages for an agent or all agents.
        
        Args:
            agent_id: Agent ID to clear messages for (None to clear all)
        """
        if agent_id:
            self.messages[agent_id] = []
        else:
            self.messages.clear()
    
    def clear_contexts(self, agent_id: Optional[str] = None):
        """
        Clear contexts for an agent or all agents.
        
        Args:
            agent_id: Agent ID to clear context for (None to clear all)
        """
        if agent_id:
            self.contexts.pop(agent_id, None)
        else:
            self.contexts.clear()
    
    def get_message_count(self, agent_id: str) -> int:
        """
        Get the number of unread messages for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Number of unread messages
        """
        return len(self.messages.get(agent_id, []))
    
    def _persist_message(self, message: AgentMessage):
        """Persist a message to disk"""
        if not self.messages_dir:
            return
        
        # Create a file for each message
        message_file = self.messages_dir / f"{message.message_id}.json"
        with open(message_file, 'w', encoding='utf-8') as f:
            json.dump(message.to_dict(), f, indent=2, ensure_ascii=False)
    
    def load_persisted_messages(self, agent_id: str) -> List[AgentMessage]:
        """
        Load persisted messages for an agent.
        
        Args:
            agent_id: Agent ID to load messages for
            
        Returns:
            List of messages
        """
        if not self.messages_dir or not self.messages_dir.exists():
            return []
        
        messages = []
        for message_file in self.messages_dir.glob("*.json"):
            try:
                with open(message_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    message = AgentMessage.from_dict(data)
                    # Only load messages for this agent
                    if message.to_agent == agent_id or message.to_agent == "*":
                        messages.append(message)
            except Exception:
                # Skip invalid message files
                continue
        
        return messages

