"""Initial AI schema

Revision ID: 0001
Revises:
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ab6_learning_data")

    op.create_table(
        "ai_learner_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ab6_user_data.user_details.id"),
                  unique=True, nullable=False),
        sa.Column("mastery_map", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("learning_style", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("engagement_history", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("intervention_log", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("struggle_patterns", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("prior_baseline", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="ab6_learning_data",
    )

    op.create_table(
        "ai_intervention_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ab6_user_data.user_details.id"),
                  nullable=False),
        sa.Column("session_id", sa.String, nullable=False),
        sa.Column("cycle_number", sa.Integer, nullable=False),
        sa.Column("diagnosed_concepts", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("engagement_score", sa.Float, nullable=True),
        sa.Column("intervention_type", sa.String(50), nullable=False),
        sa.Column("intervention_data", sa.JSON, nullable=False),
        sa.Column("was_exploration", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("arm_id", sa.String(100), nullable=True),
        sa.Column("next_challenge_score", sa.Float, nullable=True),
        sa.Column("score_delta", sa.Float, nullable=True),
        sa.Column("effectiveness_label", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="ab6_learning_data",
    )
    op.create_index("idx_intervention_user", "ai_intervention_log",
                    ["user_id"], schema="ab6_learning_data")
    op.create_index("idx_intervention_type", "ai_intervention_log",
                    ["intervention_type"], schema="ab6_learning_data")

    op.create_table(
        "ai_wisdom_store",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("concept_id", sa.String(100), nullable=False),
        sa.Column("intervention_type", sa.String(50), nullable=False),
        sa.Column("profile_segment", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("alpha", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("beta_param", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("total_trials", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("insight_text", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="ab6_learning_data",
    )
    op.create_unique_constraint(
        "uq_wisdom_unique", "ai_wisdom_store",
        ["concept_id", "intervention_type", "profile_segment"],
        schema="ab6_learning_data",
    )

    op.create_table(
        "ai_concepts",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("domain", sa.String(100), nullable=True),
        sa.Column("difficulty", sa.Float, server_default="0.5"),
        sa.Column("embedding", postgresql.VECTOR(1536), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="ab6_learning_data",
    )

    op.create_table(
        "ai_concept_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("from_concept_id", sa.String(100),
                  sa.ForeignKey("ab6_learning_data.ai_concepts.id"),
                  nullable=False),
        sa.Column("to_concept_id", sa.String(100),
                  sa.ForeignKey("ab6_learning_data.ai_concepts.id"),
                  nullable=False),
        sa.Column("edge_type", sa.String(50), nullable=False, server_default="prerequisite"),
        sa.Column("weight", sa.Float, server_default="1.0"),
        sa.Column("source", sa.String(50), server_default="auto"),
        sa.UniqueConstraint("from_concept_id", "to_concept_id", "edge_type",
                            name="uq_concept_edge"),
        schema="ab6_learning_data",
    )

    op.create_table(
        "ai_concept_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("concept_id", sa.String(100),
                  sa.ForeignKey("ab6_learning_data.ai_concepts.id"),
                  nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("relevance", sa.Float, server_default="1.0"),
        sa.UniqueConstraint("concept_id", "entity_type", "entity_id",
                            name="uq_concept_mapping"),
        schema="ab6_learning_data",
    )

    op.create_table(
        "ai_population_benchmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("concept_id", sa.String(100), unique=True, nullable=False),
        sa.Column("avg_mastery", sa.Float, nullable=True),
        sa.Column("median_mastery", sa.Float, nullable=True),
        sa.Column("p25_mastery", sa.Float, nullable=True),
        sa.Column("p75_mastery", sa.Float, nullable=True),
        sa.Column("avg_attempts", sa.Float, nullable=True),
        sa.Column("avg_time_to_master", sa.Float, nullable=True),
        sa.Column("common_prerequisite_gaps", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="ab6_learning_data",
    )


def downgrade() -> None:
    op.drop_table("ai_population_benchmarks", schema="ab6_learning_data")
    op.drop_table("ai_concept_mappings", schema="ab6_learning_data")
    op.drop_table("ai_concept_edges", schema="ab6_learning_data")
    op.drop_table("ai_concepts", schema="ab6_learning_data")
    op.drop_table("ai_wisdom_store", schema="ab6_learning_data")
    op.drop_table("ai_intervention_log", schema="ab6_learning_data")
    op.drop_table("ai_learner_profiles", schema="ab6_learning_data")
