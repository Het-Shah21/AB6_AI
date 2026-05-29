import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    JSON,
    Float,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped

from src.db.engine import Base


class AIWisdomStore(Base):
    __tablename__ = "ai_wisdom_store"
    __table_args__ = {"schema": "ab6_learning_data"}

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    concept_id: Mapped[str] = Column(String(100), nullable=False)
    intervention_type: Mapped[str] = Column(String(50), nullable=False)
    profile_segment = Column(JSON, nullable=False, default=dict)
    alpha: Mapped[float] = Column(Float, nullable=False, default=1.0)
    beta_param: Mapped[float] = Column(
        Float, nullable=False, default=1.0
    )
    total_trials: Mapped[int] = Column(
        Integer, nullable=False, default=0
    )
    success_rate: Mapped[float] = Column(
        Float, nullable=False, default=0.5
    )
    insight_text: Mapped[str | None] = Column(Text, nullable=True)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
