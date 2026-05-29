import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped

from src.db.engine import Base


class AIConcept(Base):
    __tablename__ = "ai_concepts"
    __table_args__ = {"schema": "ab6_learning_data"}

    id: Mapped[str] = Column(String(100), primary_key=True)
    name: Mapped[str] = Column(String(255), nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)
    domain: Mapped[str | None] = Column(String(100), nullable=True)
    difficulty: Mapped[float] = Column(Float, default=0.5)
    embedding = Column(Vector(1536), nullable=True)
    source_type: Mapped[str | None] = Column(String(50), nullable=True)
    source_id: Mapped[str | None] = Column(String(100), nullable=True)
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=datetime.utcnow
    )
