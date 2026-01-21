import pytest
from unittest.mock import MagicMock
from work_by_roles.core.intent_handler import IntentHandler
from work_by_roles.core.enums import IntentType

class SimpleEngine:
    def __init__(self, workspace_path):
        self.workspace_path = workspace_path
        self.role_manager = MagicMock()
        self.role_manager.roles = {}
        self.role_manager.skill_library = {}
        self.workflow = MagicMock()
        self.workflow.stages = []

@pytest.fixture
def mock_engine(tmp_path):
    return SimpleEngine(tmp_path)

def test_multi_turn_interaction_flow(mock_engine):
    handler = IntentHandler(mock_engine)
    
    # 1. Initial vague request - use an input that triggers ambiguities
    res1 = handler.handle_with_session("我想做个东西")
    session_id = res1["session_id"]
    assert res1["needs_clarification"]
    assert len(res1["clarification_questions"]) > 0
    
    # 2. Provide answers to ALL pending questions to make it ready
    answers = {}
    for q in res1["clarification_questions"]:
        answers[q["id"]] = "补充信息"
    
    res2 = handler.clarify(session_id, answers)
    
    # 3. Check updated state
    status = handler.get_session_status(session_id)
    assert "补充信息" in status["refined_goal"]
    
    # 4. Confirm session
    res3 = handler.confirm_session(session_id)
    assert res3["confirmed"]
    assert res3["intent"]["intent_type"] == IntentType.FEATURE_REQUEST

def test_session_persistence(mock_engine):
    # Set workspace path for session persistence
    workspace = mock_engine.workspace_path
    handler = IntentHandler(mock_engine, persist_sessions=True)
    
    # Check persist_dir
    assert handler.session_store.persist_dir == workspace / ".workflow" / "sessions"
    
    res = handler.handle_with_session("Test persistence")
    session_id = res["session_id"]
    
    # Check session in memory
    assert session_id in handler.session_store.sessions
    
    # Check file exists
    session_file = workspace / ".workflow" / "sessions" / f"{session_id}.json"
    if not session_file.exists():
        print(f"\nDEBUG: Session file not found at {session_file}")
        # Check if directory exists
        print(f"DEBUG: Directory exists: {(workspace / '.workflow' / 'sessions').exists()}")
        # Check contents of directory
        if (workspace / '.workflow' / 'sessions').exists():
            print(f"DEBUG: Directory contents: {list((workspace / '.workflow' / 'sessions').iterdir())}")
    
    assert session_file.exists()
