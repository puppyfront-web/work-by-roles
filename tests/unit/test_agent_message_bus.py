"""
Unit tests for AgentMessageBus.
"""
import pytest
from pathlib import Path

from work_by_roles.core.agent_message_bus import AgentMessageBus, AgentMessage


class TestAgentMessageBus:
    """Test AgentMessageBus functionality."""
    
    def test_message_bus_initialization(self, temp_workspace):
        """Test initializing AgentMessageBus."""
        messages_dir = temp_workspace / ".workflow" / "messages"
        bus = AgentMessageBus(persist_messages=False, messages_dir=messages_dir)
        
        assert bus.persist_messages is False
        assert bus.messages_dir == messages_dir
        assert bus.messages == {}
        assert bus.contexts == {}
    
    def test_publish_message(self, message_bus):
        """Test publishing a message."""
        message_id = message_bus.publish(
            from_agent="agent1",
            to_agent="agent2",
            message_type="request",
            content={"question": "test"}
        )
        
        assert message_id != ""
        assert len(message_bus.messages["agent2"]) == 1
        assert message_bus.messages["agent2"][0].from_agent == "agent1"
        assert message_bus.messages["agent2"][0].to_agent == "agent2"
        assert message_bus.messages["agent2"][0].message_type == "request"
    
    def test_subscribe_messages(self, message_bus):
        """Test subscribing to messages."""
        # Publish messages
        message_bus.publish("agent1", "agent2", "request", {"msg": "1"})
        message_bus.publish("agent1", "agent2", "request", {"msg": "2"})
        
        # Subscribe (should get and clear messages)
        messages = message_bus.subscribe("agent2")
        
        assert len(messages) == 2
        assert messages[0].content["msg"] == "1"
        assert messages[1].content["msg"] == "2"
        
        # Messages should be cleared after subscription
        assert len(message_bus.messages.get("agent2", [])) == 0
    
    def test_peek_messages(self, message_bus):
        """Test peeking at messages without removing them."""
        message_bus.publish("agent1", "agent2", "request", {"msg": "1"})
        
        messages = message_bus.peek_messages("agent2")
        
        assert len(messages) == 1
        # Messages should still be there
        assert len(message_bus.messages.get("agent2", [])) == 1
    
    def test_broadcast_message(self, message_bus):
        """Test broadcasting messages to all agents."""
        # Create some agents by publishing to them first
        message_bus.publish("agent1", "agent2", "notification", {})
        message_bus.publish("agent1", "agent3", "notification", {})
        
        # Broadcast
        message_bus.broadcast("agent1", "notification", {"broadcast": True})
        
        # Check all agents received the broadcast
        assert len(message_bus.peek_messages("agent2")) >= 1
        assert len(message_bus.peek_messages("agent3")) >= 1
    
    def test_share_context(self, message_bus):
        """Test sharing context."""
        context = {"goal": "test goal", "inputs": {"test": "data"}}
        
        message_bus.share_context("agent1", context)
        
        retrieved = message_bus.get_context("agent1")
        assert retrieved == context
        assert retrieved["goal"] == "test goal"
    
    def test_get_all_contexts(self, message_bus):
        """Test getting all contexts."""
        message_bus.share_context("agent1", {"goal": "goal1"})
        message_bus.share_context("agent2", {"goal": "goal2"})
        
        all_contexts = message_bus.get_all_contexts()
        
        assert len(all_contexts) == 2
        assert all_contexts["agent1"]["goal"] == "goal1"
        assert all_contexts["agent2"]["goal"] == "goal2"
    
    def test_clear_messages(self, message_bus):
        """Test clearing messages."""
        message_bus.publish("agent1", "agent2", "request", {})
        message_bus.publish("agent1", "agent3", "request", {})
        
        assert len(message_bus.messages.get("agent2", [])) > 0
        
        message_bus.clear_messages("agent2")
        
        assert len(message_bus.messages.get("agent2", [])) == 0
        assert len(message_bus.messages.get("agent3", [])) > 0
        
        message_bus.clear_messages()
        
        assert len(message_bus.messages) == 0
    
    def test_clear_contexts(self, message_bus):
        """Test clearing contexts."""
        message_bus.share_context("agent1", {"goal": "goal1"})
        message_bus.share_context("agent2", {"goal": "goal2"})
        
        message_bus.clear_contexts("agent1")
        
        assert message_bus.get_context("agent1") is None
        assert message_bus.get_context("agent2") is not None
        
        message_bus.clear_contexts()
        
        assert len(message_bus.contexts) == 0
    
    def test_get_message_count(self, message_bus):
        """Test getting message count."""
        assert message_bus.get_message_count("agent2") == 0
        
        message_bus.publish("agent1", "agent2", "request", {})
        message_bus.publish("agent1", "agent2", "request", {})
        
        assert message_bus.get_message_count("agent2") == 2
    
    def test_broadcast_to_all_agents(self, message_bus):
        """Test broadcast sends to all agents except sender."""
        # Create agents
        message_bus.publish("agent1", "agent2", "notification", {})
        message_bus.publish("agent1", "agent3", "notification", {})
        
        # Broadcast from agent1
        message_bus.broadcast("agent1", "notification", {"test": True})
        
        # Check agent2 and agent3 received it
        agent2_messages = message_bus.peek_messages("agent2")
        agent3_messages = message_bus.peek_messages("agent3")
        
        # Should have at least one broadcast message
        assert len(agent2_messages) >= 1
        assert len(agent3_messages) >= 1
        
        # Verify broadcast content
        broadcast_found = False
        for msg in agent2_messages + agent3_messages:
            if msg.to_agent == "*" and msg.content.get("test"):
                broadcast_found = True
                break
        assert broadcast_found

