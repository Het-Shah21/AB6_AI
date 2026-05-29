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


class AIConceptEdge(Base):
    __tablename__ = "ai_concept_edges"
    __table_args__ = (
        UniqueConstraint(
            "from_concept_id",
            "to_concept_id",
            "edge_type",
            name="uq_concept_edge",
        ),
        {"schema": "ab6_learning_data"},
    )

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    from_concept_id: Mapped[str] = Column(
        String(100),
        ForeignKey("ab6_learning_data.ai_concepts.id"),
        nullable=False,
    )
    to_concept_id: Mapped[str] = Column(
        String(100),
        ForeignKey("ab6_learning_data.ai_concepts.id"),
        nullable=False,
    )
    edge_type: Mapped[str] = Column(
        String(50), nullable=False, default="prerequisite"
    )
    weight: Mapped[float] = Column(Float, default=1.0)
    source: Mapped[str] = Column(String(50), default="auto")
