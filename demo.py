"""
AB6 AI Agent — Self-Contained Demo
Runs a full OODA cycle with in-memory state, no external dependencies.
"""

import asyncio
import json

from src.agent.graph import build_ooda_graph, create_initial_state


async def demo():
    print("=" * 60)
    print("AB6 AI AGENT — OODA CYCLE DEMO")
    print("=" * 60)

    graph = build_ooda_graph()
    agent = graph.compile()

    state = await create_initial_state("demo-user", "demo-session", max_cycles=1)

    state["raw_events"] = [
        {
            "event_type": "start_attempt",
            "challenge_id": "ik-challenge-1",
            "is_correct": None,
        },
        {
            "event_type": "end_attempt",
            "challenge_id": "ik-challenge-1",
            "score": 0.3,
            "is_correct": False,
        },
        {
            "event_type": "run_code",
            "challenge_id": "ik-challenge-1",
        },
        {
            "event_type": "run_code",
            "challenge_id": "ik-challenge-1",
        },
        {
            "event_type": "end_attempt",
            "challenge_id": "ik-challenge-1",
            "score": 0.35,
            "is_correct": False,
        },
        {
            "event_type": "page_view",
            "page": "/video/inverse-kinematics",
        },
    ]

    print("\n>> Running OBSERVE -> ORIENT -> DECIDE -> ACT cycle...\n")

    result = await agent.ainvoke(state)

    print(f"  Cycle count:     {result.get('cycle_count', 0)}")
    print(f"  Engagement:      {result.get('engagement_score', 'N/A')}")
    print(f"  Should pause:    {result.get('should_pause', False)}")

    struggles = result.get("diagnosed_struggles", [])
    if struggles:
        print(f"  Struggles:       {', '.join(struggles)}")
    else:
        print(f"  Struggles:       (none diagnosed in demo mode)")

    intervention = result.get("intervention_delivered")
    if intervention:
        print(f"\n  Intervention delivered!")
        print(f"    Type:          {intervention['type']}")
        print(f"    Content:       {intervention['content']['body'][:80]}...")
        print(f"    Channel:       {result.get('delivery_channel', 'N/A')}")
    else:
        print(f"\n  No intervention (cooldown or no diagnosis)")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
