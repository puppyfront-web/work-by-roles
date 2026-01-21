"""
Dialog Manager for multi-turn conversation support.
Following Single Responsibility Principle - handles dialog state and context management only.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import json


class DialogState(Enum):
    """Dialog state enum"""
    INITIAL = "initial"
    CLARIFYING = "clarifying"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AmbiguityType(Enum):
    """Types of ambiguity that need clarification"""
    MISSING_SCOPE = "missing_scope"  # 范围不明确
    UNCLEAR_REQUIREMENTS = "unclear_requirements"  # 需求不清晰
    TECHNICAL_AMBIGUITY = "technical_ambiguity"  # 技术选型模糊
    PRIORITY_UNCLEAR = "priority_unclear"  # 优先级不明确
    MISSING_CONTEXT = "missing_context"  # 缺少上下文
    MULTIPLE_INTERPRETATIONS = "multiple_interpretations"  # 多种解释


@dataclass
class DialogTurn:
    """A single turn in the dialog"""
    id: str
    role: str  # "user" | "system" | "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    intent: Optional[Dict[str, Any]] = None  # Recognized intent for this turn
    clarifications: List[str] = field(default_factory=list)  # Questions asked
    answers: Dict[str, str] = field(default_factory=dict)  # User's answers
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = f"turn_{uuid.uuid4().hex[:8]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "intent": self.intent,
            "clarifications": self.clarifications,
            "answers": self.answers,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DialogTurn':
        """Create from dictionary"""
        return cls(
            id=data.get("id", ""),
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            intent=data.get("intent"),
            clarifications=data.get("clarifications", []),
            answers=data.get("answers", {}),
            metadata=data.get("metadata", {})
        )


@dataclass
class ClarificationQuestion:
    """A clarification question to ask the user"""
    id: str
    question: str
    ambiguity_type: AmbiguityType
    options: List[str] = field(default_factory=list)  # Optional multiple choice
    required: bool = True
    default_value: Optional[str] = None
    answered: bool = False
    answer: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "ambiguity_type": self.ambiguity_type.value,
            "options": self.options,
            "required": self.required,
            "default_value": self.default_value,
            "answered": self.answered,
            "answer": self.answer
        }


@dataclass 
class ConversationContext:
    """Accumulated context from the conversation"""
    original_goal: str = ""
    refined_goal: str = ""
    identified_features: List[str] = field(default_factory=list)
    technical_requirements: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    scope: Dict[str, Any] = field(default_factory=dict)
    priority: str = "normal"
    clarifications: Dict[str, str] = field(default_factory=dict)  # Question ID -> Answer
    confidence_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_goal": self.original_goal,
            "refined_goal": self.refined_goal,
            "identified_features": self.identified_features,
            "technical_requirements": self.technical_requirements,
            "constraints": self.constraints,
            "scope": self.scope,
            "priority": self.priority,
            "clarifications": self.clarifications,
            "confidence_score": self.confidence_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        return cls(
            original_goal=data.get("original_goal", ""),
            refined_goal=data.get("refined_goal", ""),
            identified_features=data.get("identified_features", []),
            technical_requirements=data.get("technical_requirements", {}),
            constraints=data.get("constraints", []),
            scope=data.get("scope", {}),
            priority=data.get("priority", "normal"),
            clarifications=data.get("clarifications", {}),
            confidence_score=data.get("confidence_score", 0.0)
        )


class DialogManager:
    """
    Manages multi-turn dialog state and context.
    
    This class is responsible for:
    1. Tracking conversation history
    2. Managing dialog state
    3. Accumulating context from multiple turns
    4. Tracking pending clarifications
    5. Determining when enough information has been gathered
    """
    
    # Confidence threshold for proceeding without clarification
    CONFIDENCE_THRESHOLD = 0.7
    
    # Maximum clarification rounds before proceeding anyway
    MAX_CLARIFICATION_ROUNDS = 3
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize DialogManager.
        
        Args:
            session_id: Optional session ID (generated if not provided)
        """
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self.history: List[DialogTurn] = []
        self.context = ConversationContext()
        self.state = DialogState.INITIAL
        self.pending_questions: List[ClarificationQuestion] = []
        self.clarification_round = 0
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
    
    def add_user_turn(self, content: str, intent: Optional[Dict[str, Any]] = None) -> DialogTurn:
        """
        Add a user message to the dialog history.
        
        Args:
            content: User's message content
            intent: Optional recognized intent
            
        Returns:
            The created DialogTurn
        """
        turn = DialogTurn(
            id=f"turn_{len(self.history)}",
            role="user",
            content=content,
            intent=intent
        )
        self.history.append(turn)
        self.last_activity = datetime.now()
        
        # Update context based on user input
        if self.state == DialogState.INITIAL:
            self.context.original_goal = content
            self.state = DialogState.CLARIFYING
        
        return turn
    
    def add_system_turn(
        self, 
        content: str, 
        clarifications: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DialogTurn:
        """
        Add a system/assistant message to the dialog history.
        
        Args:
            content: System's message content
            clarifications: Optional list of clarification questions asked
            metadata: Optional additional metadata
            
        Returns:
            The created DialogTurn
        """
        turn = DialogTurn(
            id=f"turn_{len(self.history)}",
            role="system",
            content=content,
            clarifications=clarifications or [],
            metadata=metadata or {}
        )
        self.history.append(turn)
        self.last_activity = datetime.now()
        
        return turn
    
    def add_clarification_question(
        self,
        question: str,
        ambiguity_type: AmbiguityType,
        options: Optional[List[str]] = None,
        required: bool = True,
        default_value: Optional[str] = None
    ) -> ClarificationQuestion:
        """
        Add a clarification question to ask the user.
        
        Args:
            question: The question to ask
            ambiguity_type: Type of ambiguity being addressed
            options: Optional multiple choice options
            required: Whether an answer is required
            default_value: Optional default value
            
        Returns:
            The created ClarificationQuestion
        """
        q = ClarificationQuestion(
            id=f"q_{len(self.pending_questions)}_{uuid.uuid4().hex[:4]}",
            question=question,
            ambiguity_type=ambiguity_type,
            options=options or [],
            required=required,
            default_value=default_value
        )
        self.pending_questions.append(q)
        return q
    
    def answer_clarification(self, question_id: str, answer: str) -> bool:
        """
        Record an answer to a clarification question.
        
        Args:
            question_id: ID of the question being answered
            answer: The user's answer
            
        Returns:
            True if the question was found and answered
        """
        for q in self.pending_questions:
            if q.id == question_id:
                q.answered = True
                q.answer = answer
                self.context.clarifications[question_id] = answer
                return True
        return False
    
    def answer_all_pending(self, answers: Dict[str, str]) -> int:
        """
        Answer multiple pending questions at once.
        
        Args:
            answers: Dictionary mapping question IDs to answers
            
        Returns:
            Number of questions answered
        """
        answered = 0
        for qid, answer in answers.items():
            if self.answer_clarification(qid, answer):
                answered += 1
        return answered
    
    def get_pending_questions(self) -> List[ClarificationQuestion]:
        """Get all unanswered required questions"""
        return [q for q in self.pending_questions if not q.answered and q.required]
    
    def has_pending_questions(self) -> bool:
        """Check if there are unanswered required questions"""
        return len(self.get_pending_questions()) > 0
    
    def needs_clarification(self, intent_result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determine if clarification is needed based on intent and context.
        
        Args:
            intent_result: Optional intent recognition result
            
        Returns:
            True if clarification is needed
        """
        # Already at max rounds, proceed anyway
        if self.clarification_round >= self.MAX_CLARIFICATION_ROUNDS:
            return False
        
        # Have pending unanswered questions
        if self.has_pending_questions():
            return True
        
        # Check confidence from intent result
        if intent_result:
            confidence = intent_result.get("confidence", 0.0)
            if confidence < self.CONFIDENCE_THRESHOLD:
                return True
            
            # Check if intent is unknown
            intent_type = intent_result.get("intent_type")
            if intent_type and str(intent_type).lower() == "unknown":
                return True
        
        # Check context confidence
        if self.context.confidence_score < self.CONFIDENCE_THRESHOLD:
            return True
        
        return False
    
    def update_context(self, updates: Dict[str, Any]):
        """
        Update conversation context with new information.
        
        Args:
            updates: Dictionary of context updates
        """
        if "refined_goal" in updates:
            self.context.refined_goal = updates["refined_goal"]
        if "features" in updates:
            self.context.identified_features.extend(updates["features"])
        if "requirements" in updates:
            self.context.technical_requirements.update(updates["requirements"])
        if "constraints" in updates:
            self.context.constraints.extend(updates["constraints"])
        if "scope" in updates:
            self.context.scope.update(updates["scope"])
        if "priority" in updates:
            self.context.priority = updates["priority"]
        if "confidence" in updates:
            self.context.confidence_score = updates["confidence"]
    
    def get_context_summary(self) -> str:
        """
        Get a summary of the conversation context for LLM prompts.
        
        Returns:
            Formatted context summary string
        """
        parts = []
        
        if self.context.original_goal:
            parts.append(f"原始目标: {self.context.original_goal}")
        
        if self.context.refined_goal:
            parts.append(f"细化目标: {self.context.refined_goal}")
        
        if self.context.identified_features:
            features = ", ".join(self.context.identified_features[:5])  # Limit to 5
            parts.append(f"识别的功能: {features}")
        
        if self.context.technical_requirements:
            reqs = json.dumps(self.context.technical_requirements, ensure_ascii=False)
            parts.append(f"技术要求: {reqs}")
        
        if self.context.constraints:
            constraints = ", ".join(self.context.constraints[:3])
            parts.append(f"约束条件: {constraints}")
        
        if self.context.clarifications:
            clarified = len(self.context.clarifications)
            parts.append(f"已澄清问题: {clarified}个")
        
        return "\n".join(parts)
    
    def get_dialog_history_text(self, max_turns: int = 10) -> str:
        """
        Get dialog history as formatted text for LLM prompts.
        
        Args:
            max_turns: Maximum number of turns to include
            
        Returns:
            Formatted dialog history string
        """
        recent_turns = self.history[-max_turns:] if len(self.history) > max_turns else self.history
        
        lines = []
        for turn in recent_turns:
            role_label = "用户" if turn.role == "user" else "系统"
            lines.append(f"[{role_label}]: {turn.content}")
            
            if turn.clarifications:
                for q in turn.clarifications:
                    lines.append(f"  - 澄清问题: {q}")
        
        return "\n".join(lines)
    
    def mark_confirmed(self):
        """Mark the dialog as confirmed and ready for execution"""
        self.state = DialogState.CONFIRMED
        self.clarification_round = 0
        
        # Use refined goal if available, otherwise original
        if not self.context.refined_goal:
            self.context.refined_goal = self.context.original_goal
    
    def mark_executing(self):
        """Mark the dialog as executing"""
        self.state = DialogState.EXECUTING
    
    def mark_completed(self):
        """Mark the dialog as completed"""
        self.state = DialogState.COMPLETED
    
    def mark_cancelled(self):
        """Mark the dialog as cancelled"""
        self.state = DialogState.CANCELLED
    
    def start_clarification_round(self):
        """Start a new clarification round"""
        self.clarification_round += 1
        # Clear pending questions that were answered
        self.pending_questions = [q for q in self.pending_questions if not q.answered]
    
    def is_ready_to_execute(self) -> bool:
        """
        Check if the dialog has gathered enough information to execute.
        
        Returns:
            True if ready to proceed with execution
        """
        if self.state == DialogState.CONFIRMED:
            return True
        
        if self.state in (DialogState.EXECUTING, DialogState.COMPLETED, DialogState.CANCELLED):
            return False
        
        # Check if we have minimum required info
        has_goal = bool(self.context.original_goal or self.context.refined_goal)
        no_pending = not self.has_pending_questions()
        
        # Confidence threshold check
        confidence = self.context.confidence_score
        threshold = self.CONFIDENCE_THRESHOLD
        high_confidence = confidence >= threshold
        
        # Max rounds check
        max_rounds_reached = self.clarification_round >= self.MAX_CLARIFICATION_ROUNDS
        
        return bool(has_goal and no_pending and (high_confidence or max_rounds_reached))
    
    def get_final_goal(self) -> str:
        """Get the final refined goal for execution"""
        return self.context.refined_goal or self.context.original_goal
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert dialog manager state to dictionary for serialization"""
        return {
            "session_id": self.session_id,
            "history": [turn.to_dict() for turn in self.history],
            "context": self.context.to_dict(),
            "state": self.state.value,
            "pending_questions": [q.to_dict() for q in self.pending_questions],
            "clarification_round": self.clarification_round,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DialogManager':
        """Create DialogManager from dictionary"""
        manager = cls(session_id=data.get("session_id"))
        manager.history = [DialogTurn.from_dict(t) for t in data.get("history", [])]
        manager.context = ConversationContext.from_dict(data.get("context", {}))
        manager.state = DialogState(data.get("state", "initial"))
        manager.clarification_round = data.get("clarification_round", 0)
        manager.created_at = datetime.fromisoformat(data.get("created_at", datetime.now().isoformat()))
        manager.last_activity = datetime.fromisoformat(data.get("last_activity", datetime.now().isoformat()))
        
        # Restore pending questions
        for q_data in data.get("pending_questions", []):
            q = ClarificationQuestion(
                id=q_data["id"],
                question=q_data["question"],
                ambiguity_type=AmbiguityType(q_data["ambiguity_type"]),
                options=q_data.get("options", []),
                required=q_data.get("required", True),
                default_value=q_data.get("default_value"),
                answered=q_data.get("answered", False),
                answer=q_data.get("answer")
            )
            manager.pending_questions.append(q)
        
        return manager
    
    def clear(self):
        """Clear all dialog state"""
        self.history = []
        self.context = ConversationContext()
        self.state = DialogState.INITIAL
        self.pending_questions = []
        self.clarification_round = 0
        self.last_activity = datetime.now()
