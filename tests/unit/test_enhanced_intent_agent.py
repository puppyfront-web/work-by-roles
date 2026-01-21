import pytest
from unittest.mock import MagicMock
from work_by_roles.core.intent_agent import IntentAgent
from work_by_roles.core.enums import IntentType
from work_by_roles.core.dialog_manager import AmbiguityType

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.role_manager.roles = {}
    engine.role_manager.skill_library = {}
    return engine

def test_detect_ambiguities(mock_engine):
    agent = IntentAgent(mock_engine)
    
    # Test vague input - avoid using scope indicators like "功能"
    vague_input = "做一些大概的东西"
    intent_result = {"intent_type": IntentType.FEATURE_REQUEST, "confidence": 0.5}
    ambiguities = agent.detect_ambiguities(vague_input, intent_result)
    
    amb_types = [a[0] for a in ambiguities]
    assert AmbiguityType.UNCLEAR_REQUIREMENTS in amb_types
    assert AmbiguityType.MISSING_SCOPE in amb_types

def test_generate_clarification_questions(mock_engine):
    agent = IntentAgent(mock_engine)
    ambiguities = [(AmbiguityType.MISSING_SCOPE, "Missing scope")]
    
    questions = agent.generate_clarification_questions(ambiguities, "test input")
    assert len(questions) > 0
    assert "功能属于哪个系统" in questions[0][0] or "边界" in questions[0][0]

def test_interactive_recognize_new_session(mock_engine):
    agent = IntentAgent(mock_engine)
    user_input = "实现用户登录"
    
    result = agent.interactive_recognize(user_input)
    assert "session_id" in result
    assert result["intent"]["intent_type"] == IntentType.FEATURE_REQUEST
    assert "needs_clarification" in result

def test_refine_goal_from_answers(mock_engine):
    agent = IntentAgent(mock_engine)
    agent.interactive_recognize("Build a site")
    
    # Simulate pending question
    q = agent.dialog_manager.pending_questions[0]
    answers = {q.id: "Using Django"}
    
    refined = agent._refine_goal_from_answers(answers)
    assert "Build a site" in refined
    assert "Using Django" in refined
