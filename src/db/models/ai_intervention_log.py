import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    JSON,
    ForeignKey,
    Integer,
    Float,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped

from src.db.engine import Base


class AIInterventionLog(Base):
    __tablename__ = "ai_intervention_log"
    __table_args__ = {"schema": "ab6_learning_data"}

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("ab6_user_data.user_details.id"),
        nullable=False,
    )
    session_id: Mapped[str] = Column(String, nullable=False)
    cycle_number: Mapped[int] = Column(Integer, nullable=False)
    diagnosed_concepts = Column(ARRAY(String), nullable=False)
    engagement_score: Mapped[float | None] = Column(Float, nullable=True)
    intervention_type: Mapped[str] = Column(String(50), nullable=False)
    intervention_data = Column(JSON, nullable=False)
    was_exploration: Mapped[bool] = Column(
        Boolean, nullable=False, default=False
    )
    arm_id: Mapped[str | None] = Column(String(100), nullable=True)
    next_challenge_score: Mapped[float | None] = Column(
        Float, nullable=True
    )
    score_delta: Mapped[float | None] = Column(Float, nullable=True)
    effectiveness_label: Mapped[str | None] = Column(
        String(20), nullable=True
    )
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=datetime.utcnow
    )
