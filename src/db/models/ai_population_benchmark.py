import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Float,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped

from src.db.engine import Base


class AIPopulationBenchmark(Base):
    __tablename__ = "ai_population_benchmarks"
    __table_args__ = {"schema": "ab6_learning_data"}

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    concept_id: Mapped[str] = Column(
        String(100), unique=True, nullable=False
    )
    avg_mastery: Mapped[float | None] = Column(Float, nullable=True)
    median_mastery: Mapped[float | None] = Column(Float, nullable=True)
    p25_mastery: Mapped[float | None] = Column(Float, nullable=True)
    p75_mastery: Mapped[float | None] = Column(Float, nullable=True)
    avg_attempts: Mapped[float | None] = Column(Float, nullable=True)
    avg_time_to_master: Mapped[float | None] = Column(
        Float, nullable=True
    )
    common_prerequisite_gaps = Column(ARRAY(String), nullable=True)
    sample_size: Mapped[int] = Column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
