import pytest
from work_by_roles.core.dialog_manager import (
    DialogManager, DialogTurn, DialogState, 
    AmbiguityType, ConversationContext
)

def test_dialog_manager_initial_state():
    dm = DialogManager(session_id="test_session")
    assert dm.session_id == "test_session"
    assert dm.state == DialogState.INITIAL
    assert len(dm.history) == 0
    assert not dm.has_pending_questions()

def test_add_user_turn():
    dm = DialogManager()
    dm.add_user_turn("I want to build a website")
    assert len(dm.history) == 1
    assert dm.history[0].role == "user"
    assert dm.history[0].content == "I want to build a website"
    assert dm.context.original_goal == "I want to build a website"
    assert dm.state == DialogState.CLARIFYING

def test_clarification_questions():
    dm = DialogManager()
    dm.add_user_turn("Build something")
    
    q = dm.add_clarification_question(
        "What do you want to build?", 
        AmbiguityType.MISSING_SCOPE
    )
    
    assert len(dm.pending_questions) == 1
    assert dm.has_pending_questions()
    assert not q.answered
    
    dm.answer_clarification(q.id, "A blog")
    assert q.answered
    assert q.answer == "A blog"
    assert not dm.has_pending_questions()
    assert dm.context.clarifications[q.id] == "A blog"

def test_ready_to_execute():
    dm = DialogManager()
    dm.add_user_turn("Build a blog")
    dm.update_context({"confidence": 0.8})
    
    # Ready if confidence is high and no pending questions
    assert dm.is_ready_to_execute()
    
    # Not ready if pending questions
    q = dm.add_clarification_question("What tech?", AmbiguityType.TECHNICAL_AMBIGUITY)
    assert not dm.is_ready_to_execute()
    
    # Ready after answering
    dm.answer_all_pending({q.id: "Python"})
    # Need to manually call start_clarification_round to clear answered from pending in real flow
    dm.start_clarification_round() 
    assert dm.is_ready_to_execute()

def test_serialization():
    dm = DialogManager(session_id="session_123")
    dm.add_user_turn("Goal")
    dm.add_clarification_question("Q", AmbiguityType.MISSING_SCOPE)
    
    data = dm.to_dict()
    assert data["session_id"] == "session_123"
    assert len(data["history"]) == 1
    assert len(data["pending_questions"]) == 1
    
    dm2 = DialogManager.from_dict(data)
    assert dm2.session_id == "session_123"
    assert dm2.context.original_goal == "Goal"
    assert len(dm2.pending_questions) == 1
    assert dm2.pending_questions[0].question == "Q"
