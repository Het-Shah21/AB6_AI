from pydantic import BaseModel, Field
from typing import Any


class YouTubeEvent(BaseModel):
    event_type: str
    timestamp: float
    video_time: float
    data: dict[str, Any] = {}


class WatchSession(BaseModel):
    user_id: str
    video_id: str
    video_url: str
    video_duration: float = 0.0
    events: list[YouTubeEvent] = []
    status: str = "watching"


class SegmentAnalysis(BaseModel):
    segment_index: int
    start_time: float
    end_time: float
    total_watch_time: float = 0.0
    rewatch_count: int = 0
    pause_count: int = 0
    avg_speed: float = 1.0
    was_skipped: bool = False
    tab_switch_count: int = 0
    struggle_score: float = 0.0


class AnalysisResult(BaseModel):
    video_id: str
    user_id: str
    video_duration: float
    segments: list[SegmentAnalysis]
    struggle_segments: list[SegmentAnalysis]
    overall_engagement: float = 0.0
    recommendations: list[str] = []
    narrative: str = ""


class AgentState(BaseModel):
    user_id: str
    session_id: str
    video_id: str
    prior_profile: dict[str, Any] = {}
    raw_events: list[YouTubeEvent] = []
    segment_analyses: list[SegmentAnalysis] = []
    struggle_segments: list[SegmentAnalysis] = []
    inferred_weaknesses: list[dict[str, Any]] = []
    interpreted_context: dict[str, Any] = {}
    intelligence_recommendations: list[str] = []
    agent_state: dict[str, Any] = {}
    narrative: str = ""
    cycle_count: int = 0
