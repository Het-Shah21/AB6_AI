import logging
import json
import numpy as np
from datetime import datetime

from .schemas import AgentState, YouTubeEvent, SegmentAnalysis
from .analytics import YouTubeAnalytics

logger = logging.getLogger(__name__)

WEAKNESS_KEYWORDS: dict[str, list[str]] = {
    "fundamentals": [
        "introduction", "basic", "overview", "foundation",
        "prerequisite", "background", "concept",
    ],
    "technical_depth": [
        "algorithm", "implementation", "formula", "equation",
        "code", "syntax", "function", "method",
    ],
    "advanced_topics": [
        "advanced", "complex", "optimization", "deep",
        "architecture", "framework", "integration",
    ],
    "practical_application": [
        "example", "tutorial", "walkthrough", "demo",
        "hands-on", "exercise", "practice", "case study",
    ],
}


class YouTubeAgent:
    def __init__(self):
        self.analytics = YouTubeAnalytics(segment_duration=10.0)

    async def run_pipeline(self, state: AgentState) -> AgentState:
        logger.info("=== Starting YouTube Agent Pipeline (cycle %d) ===", state.cycle_count)

        state = self._prior_info(state)
        state = await self._observe(state)
        state = self._analyze(state)
        state = self._inference(state)
        state = self._interpret(state)
        state = self._intelligence(state)
        state = self._feedback_loop(state)

        state.cycle_count += 1
        logger.info("=== Pipeline complete ===")
        return state

    def _prior_info(self, state: AgentState) -> AgentState:
        logger.info("[PRIOR INFO] Gathering learner background for user=%s", state.user_id)
        prior_profile = {
            "user_id": state.user_id,
            "session_count": state.cycle_count + 1,
            "inferred_persona": "self-directed_learner",
            "past_struggles": [],
            "video_history_count": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        for ev in state.raw_events:
            if ev.event_type == "play" and not state.prior_profile:
                prior_profile["first_action"] = "play"
                break

        if state.prior_profile:
            prior_profile["past_struggles"] = state.prior_profile.get("past_struggles", [])
            prior_profile["video_history_count"] = state.prior_profile.get("video_history_count", 0) + 1

        state.prior_profile = prior_profile
        return state

    async def _observe(self, state: AgentState) -> AgentState:
        logger.info("[OBSERVE] Processing %d raw events", len(state.raw_events))
        video_duration = max(
            (ev.data.get("duration", 0) for ev in state.raw_events if ev.event_type == "video_metadata"),
            default=0.0,
        )
        state.agent_state["video_duration"] = video_duration

        analysis = self.analytics.analyze(
            user_id=state.user_id,
            video_duration=video_duration or 600.0,
            events=state.raw_events,
        )
        state.segment_analyses = analysis.segments
        state.struggle_segments = analysis.struggle_segments
        state.agent_state["overall_engagement"] = analysis.overall_engagement

        logger.info("[OBSERVE] Video duration=%.0fs, %d segments, %d struggle segments",
                     video_duration, len(analysis.segments), len(analysis.struggle_segments))
        return state

    def _analyze(self, state: AgentState) -> AgentState:
        logger.info("[ANALYZE] Computing segment-level patterns")
        segments = state.segment_analyses
        if not segments:
            return state

        total_pauses = sum(s.pause_count for s in segments)
        total_rewatches = sum(s.rewatch_count for s in segments)
        total_skipped = sum(1 for s in segments if s.was_skipped)
        avg_speed = float(np.mean([s.avg_speed for s in segments])) if segments else 1.0

        analysis_summary = {
            "total_events": len(state.raw_events),
            "total_pauses": total_pauses,
            "total_rewatches": total_rewatches,
            "total_segments_skipped": total_skipped,
            "average_playback_speed": round(avg_speed, 2),
            "struggle_segment_count": len(state.struggle_segments),
        }
        state.agent_state["analysis_summary"] = analysis_summary
        logger.info("[ANALYZE] Summary: %s", json.dumps(analysis_summary))
        return state

    def _inference(self, state: AgentState) -> AgentState:
        logger.info("[INFERENCE] Diagnosing weakness areas")
        state.inferred_weaknesses = []

        seg_text_map = {
            0: "introduction and basic concepts",
            1: "core fundamentals",
            2: "technical implementation",
            3: "advanced applications",
            4: "practical examples",
        }

        for seg in state.struggle_segments:
            normalized_idx = min(seg.segment_index // max(1, len(state.segment_analyses) // 5), 4)
            weakness_area = seg_text_map.get(normalized_idx, f"section_{seg.segment_index}")

            reasons = []
            if seg.rewatch_count > 1:
                reasons.append("repeated_viewing")
            if seg.pause_count > 2:
                reasons.append("frequent_pausing")
            if seg.was_skipped:
                reasons.append("content_skipped")
            if seg.avg_speed < 0.8:
                reasons.append("reduced_playback_speed")
            if seg.tab_switch_count > 0:
                reasons.append("attention_loss")

            weakness = {
                "area": weakness_area,
                "segment_index": seg.segment_index,
                "time_range": f"{seg.start_time:.0f}s-{seg.end_time:.0f}s",
                "struggle_score": seg.struggle_score,
                "indicators": reasons,
                "confidence": round(min(1.0, seg.struggle_score * 1.2), 2),
            }
            state.inferred_weaknesses.append(weakness)

        state.agent_state["inferred_weaknesses"] = state.inferred_weaknesses
        logger.info("[INFERENCE] Identified %d weakness areas", len(state.inferred_weaknesses))
        return state

    def _interpret(self, state: AgentState) -> AgentState:
        logger.info("[INTERPRET] Contextualizing weakness patterns")
        state.interpreted_context = {}

        weakness_count = len(state.inferred_weaknesses)
        engagement = state.agent_state.get("overall_engagement", 0.5)
        analysis = state.agent_state.get("analysis_summary", {})

        if weakness_count == 0:
            interpretation = "The learner demonstrated strong comprehension throughout the video."
            severity = "none"
        elif weakness_count <= 2:
            interpretation = "Minor comprehension gaps detected in specific sections."
            severity = "low"
        elif weakness_count <= 4:
            interpretation = "Moderate comprehension issues detected. Several concepts may need reinforcement."
            severity = "medium"
        else:
            interpretation = "Significant comprehension challenges detected across multiple sections."
            severity = "high"

        if engagement < 0.3:
            interpretation += " Overall engagement was low, suggesting possible distraction or fatigue."
        elif engagement < 0.6:
            interpretation += " Engagement was moderate with intermittent attention drops."

        state.interpreted_context = {
            "interpretation": interpretation,
            "severity": severity,
            "engagement_level": "low" if engagement < 0.3 else "medium" if engagement < 0.6 else "high",
            "weakness_count": weakness_count,
            "total_pauses": analysis.get("total_pauses", 0),
            "total_rewatches": analysis.get("total_rewatches", 0),
            "avg_speed": analysis.get("average_playback_speed", 1.0),
        }
        logger.info("[INTERPRET] Severity=%s, engagement=%s", severity, state.interpreted_context["engagement_level"])
        return state

    def _intelligence(self, state: AgentState) -> AgentState:
        logger.info("[INTELLIGENCE] Generating actionable recommendations")
        state.intelligence_recommendations = []
        ctx = state.interpreted_context

        if ctx.get("severity") == "none":
            state.intelligence_recommendations.append(
                "No revision needed — you demonstrated strong comprehension."
            )
            state.narrative = (
                "Excellent session! Your playback behavior shows consistent understanding "
                "across all sections. Consider exploring advanced topics next."
            )
            return state

        for weakness in state.inferred_weaknesses:
            time_range = weakness["time_range"]
            area = weakness["area"]
            indicators = weakness["indicators"]

            if "repeated_viewing" in indicators:
                state.intelligence_recommendations.append(
                    f"You rewatched content at {time_range} ({area}). "
                    f"Review this section with focused attention on the core concepts."
                )
            if "frequent_pausing" in indicators:
                state.intelligence_recommendations.append(
                    f"Frequent pauses at {time_range} ({area}) suggest the material was challenging. "
                    f"Consider breaking this section into smaller parts and reviewing each separately."
                )
            if "content_skipped" in indicators:
                state.intelligence_recommendations.append(
                    f"You skipped content around {time_range} ({area}). "
                    f"This section contains important material you may have missed — revisit it."
                )
            if "reduced_playback_speed" in indicators:
                state.intelligence_recommendations.append(
                    f"Reduced playback speed at {time_range} ({area}) indicates careful study. "
                    f"Practice problems related to this topic will help solidify understanding."
                )
            if "attention_loss" in indicators:
                state.intelligence_recommendations.append(
                    f"Attention drops detected at {time_range} ({area}). "
                    f"Try taking short breaks before studying dense material."
                )

        analysis = state.agent_state.get("analysis_summary", {})
        weak_areas = [w["area"] for w in state.inferred_weaknesses]
        state.narrative = (
            f"Analysis complete. You showed {len(state.inferred_weaknesses)} area(s) needing review: "
            f"{', '.join(set(weak_areas))}. "
            f"Total pauses: {analysis.get('total_pauses', 0)}, "
            f"rewatches: {analysis.get('total_rewatches', 0)}. "
            f"Focus on the recommended sections above."
        )

        logger.info("[INTELLIGENCE] Generated %d recommendations", len(state.intelligence_recommendations))
        return state

    def _feedback_loop(self, state: AgentState) -> AgentState:
        logger.info("[FEEDBACK] Updating learner profile for next cycle")
        if state.prior_profile is not None:
            prior_struggles = state.prior_profile.get("past_struggles", [])
            new_areas = list(set(
                w["area"] for w in state.inferred_weaknesses
            ))
            updated_struggles = list(set(prior_struggles + new_areas))
            state.prior_profile["past_struggles"] = updated_struggles

        state.agent_state["last_cycle_completed"] = datetime.utcnow().isoformat()
        state.agent_state["feedback_saved"] = True

        logger.info("[FEEDBACK] Profile updated, %d total struggle areas tracked",
                     len(state.prior_profile.get("past_struggles", [])))
        return state
