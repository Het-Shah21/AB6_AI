import uuid

from sqlalchemy import (
    Column,
    String,
    Float,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped

from src.db.engine import Base


class AIConceptMapping(Base):
    __tablename__ = "ai_concept_mappings"
    __table_args__ = (
        UniqueConstraint(
            "concept_id",
            "entity_type",
            "entity_id",
            name="uq_concept_mapping",
        ),
        {"schema": "ab6_learning_data"},
    )

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    concept_id: Mapped[str] = Column(
        String(100),
        ForeignKey("ab6_learning_data.ai_concepts.id"),
        nullable=False,
    )
    entity_type: Mapped[str] = Column(String(50), nullable=False)
    entity_id: Mapped[str] = Column(String(100), nullable=False)
    relevance: Mapped[float] = Column(Float, default=1.0)
