import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped

from src.db.engine import Base


class AILearnerProfile(Base):
    __tablename__ = "ai_learner_profiles"
    __table_args__ = {"schema": "ab6_learning_data"}

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("ab6_user_data.user_details.id"),
        unique=True,
        nullable=False,
    )
    mastery_map = Column(JSON, nullable=False, default=dict)
    learning_style = Column(JSON, nullable=False, default=dict)
    engagement_history = Column(JSON, nullable=False, default=list)
    intervention_log = Column(JSON, nullable=False, default=list)
    struggle_patterns = Column(JSON, nullable=False, default=dict)
    prior_baseline = Column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
