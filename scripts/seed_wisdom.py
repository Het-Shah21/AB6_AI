#!/usr/bin/env python3
"""Seed initial wisdom priors for the Global Wisdom Store."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED_WISDOM = [
    {
        "concept_id": "kinematics.forward.dh_parameters",
        "intervention_type": "video_recommendation",
        "alpha": 15.0,
        "beta": 3.0,
        "insight": "For DH parameters, video explanations yield 83% success rate.",
    },
    {
        "concept_id": "kinematics.forward.dh_parameters",
        "intervention_type": "concept_explanation",
        "alpha": 10.0,
        "beta": 5.0,
        "insight": "Text explanations work for 67% of learners on DH parameters.",
    },
    {
        "concept_id": "kinematics.inverse.jacobian",
        "intervention_type": "challenge_hint",
        "alpha": 12.0,
        "beta": 4.0,
        "insight": "Targeted hints improve IK performance by 75%.",
    },
    {
        "concept_id": "kinematics.inverse.jacobian",
        "intervention_type": "prerequisite_nudge",
        "alpha": 8.0,
        "beta": 6.0,
        "insight": "Reviewing forward kinematics first helps 57% of learners.",
    },
    {
        "concept_id": "dynamics.newton_euler",
        "intervention_type": "concept_explanation",
        "alpha": 20.0,
        "beta": 5.0,
        "insight": "Newton-Euler explanations with formula breakdowns are highly effective (80%).",
    },
    {
        "concept_id": "general",
        "intervention_type": "encouragement",
        "alpha": 25.0,
        "beta": 2.0,
        "insight": "Encouragement messages improve engagement for 92% of learners.",
    },
]


async def main():
    session = await get_session()
    for wisdom in SEED_WISDOM:
        await session.execute(
            text("""
                INSERT INTO ab6_learning_data.ai_wisdom_store
                    (concept_id, intervention_type, alpha, beta_param, total_trials,
                     success_rate, insight_text)
                VALUES (:cid, :itype, :alpha, :beta, :trials, :rate, :insight)
                ON CONFLICT (concept_id, intervention_type, profile_segment)
                DO UPDATE SET
                    alpha = EXCLUDED.alpha,
                    beta_param = EXCLUDED.beta_param,
                    total_trials = EXCLUDED.total_trials,
                    success_rate = EXCLUDED.success_rate
            """),
            {
                "cid": wisdom["concept_id"],
                "itype": wisdom["intervention_type"],
                "alpha": wisdom["alpha"],
                "beta": wisdom["beta"],
                "trials": wisdom["alpha"] + wisdom["beta"] - 2,
                "rate": wisdom["alpha"] / (wisdom["alpha"] + wisdom["beta"]),
                "insight": wisdom.get("insight", ""),
            },
        )
    await session.commit()
    logger.info("Seeded %d wisdom entries", len(SEED_WISDOM))
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
