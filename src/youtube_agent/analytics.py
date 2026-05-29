import numpy as np
from collections import defaultdict
from .schemas import YouTubeEvent, SegmentAnalysis, AnalysisResult


class YouTubeAnalytics:
    def __init__(self, segment_duration: float = 10.0):
        self.segment_duration = segment_duration

    def analyze(self, user_id: str, video_duration: float, events: list[YouTubeEvent]) -> AnalysisResult:
        num_segments = max(1, int(np.ceil(video_duration / self.segment_duration)))
        segments = self._build_segments(num_segments, video_duration)
        self._process_events(segments, events)
        self._compute_struggle_scores(segments)
        struggle = [s for s in segments if s.struggle_score > 0.4]
        engagement = self._compute_engagement(segments)
        recommendations = self._generate_recommendations(struggle, video_duration)

        return AnalysisResult(
            video_id="",
            user_id=user_id,
            video_duration=video_duration,
            segments=segments,
            struggle_segments=struggle,
            overall_engagement=engagement,
            recommendations=recommendations,
        )

    def _build_segments(self, count: int, duration: float) -> list[SegmentAnalysis]:
        seg_dur = duration / count
        return [
            SegmentAnalysis(
                segment_index=i,
                start_time=round(i * seg_dur, 1),
                end_time=round((i + 1) * seg_dur, 1),
            )
            for i in range(count)
        ]

    def _process_events(self, segments: list[SegmentAnalysis], events: list[YouTubeEvent]):
        seg_idx = lambda t: min(len(segments) - 1, max(0, int(t / (segments[-1].end_time / len(segments)))))

        watch_accumulator: dict[int, float] = defaultdict(float)
        segment_visit_count: dict[int, set[str]] = defaultdict(set)
        was_paused_in_segment: dict[int, bool] = defaultdict(bool)
        segment_speeds: dict[int, list[float]] = defaultdict(list)
        seek_jumps: list[tuple[int, int]] = []
        last_play_time: float | None = None

        for ev in events:
            idx = seg_idx(ev.video_time)
            et = ev.event_type

            if et == "play":
                segment_visit_count[idx].add("play")
                last_play_time = ev.video_time

            elif et == "pause":
                was_paused_in_segment[idx] = True
                segments[idx].pause_count += 1
                if last_play_time is not None:
                    elapsed = ev.video_time - last_play_time
                    watch_accumulator[idx] += elapsed
                    last_play_time = None

            elif et == "seek":
                seek_from = ev.data.get("from", ev.video_time)
                seek_to = ev.data.get("to", ev.video_time)
                from_idx = seg_idx(seek_from)
                to_idx = seg_idx(seek_to)
                seek_jumps.append((from_idx, to_idx))
                if to_idx > from_idx:
                    for skip_idx in range(from_idx, to_idx):
                        if skip_idx < len(segments):
                            segments[skip_idx].was_skipped = True

            elif et == "speed_change":
                speed = ev.data.get("speed", 1.0)
                segment_speeds[idx].append(speed)

            elif et == "tab_switch":
                segments[idx].tab_switch_count += 1

            elif et == "timeupdate" and last_play_time is not None:
                pass

        for idx, total_time in watch_accumulator.items():
            segments[idx].total_watch_time = round(total_time, 2)

        for idx, visits in segment_visit_count.items():
            segments[idx].rewatch_count = max(0, len(visits) - 1)

        for idx, speeds in segment_speeds.items():
            segments[idx].avg_speed = round(float(np.mean(speeds)), 2)

    def _compute_struggle_scores(self, segments: list[SegmentAnalysis]):
        max_rewatch = max((s.rewatch_count for s in segments), default=1)
        max_pause = max((s.pause_count for s in segments), default=1)
        max_tab = max((s.tab_switch_count for s in segments), default=1)

        for s in segments:
            seg_dur = s.end_time - s.start_time
            watch_ratio = min(1.0, s.total_watch_time / seg_dur) if seg_dur > 0 else 0
            rewatch_norm = s.rewatch_count / max_rewatch if max_rewatch > 0 else 0
            pause_norm = s.pause_count / max_pause if max_pause > 0 else 0
            tab_norm = s.tab_switch_count / max_tab if max_tab > 0 else 0
            speed_factor = max(0, 1.0 - abs(s.avg_speed - 1.0) / 2.0)

            score = (
                (1.0 - watch_ratio) * 0.25
                + rewatch_norm * 0.25
                + pause_norm * 0.20
                + tab_norm * 0.15
                + speed_factor * 0.15
            )
            s.struggle_score = round(min(1.0, score), 3)

    def _compute_engagement(self, segments: list[SegmentAnalysis]) -> float:
        if not segments:
            return 0.5
        scores = [s.struggle_score for s in segments]
        return round(1.0 - float(np.mean(scores)), 3)

    def _generate_recommendations(self, struggle_segments: list, duration: float) -> list[str]:
        recs = []
        if not struggle_segments:
            recs.append("Great job! No major struggle sections detected.")
            return recs

        for seg in struggle_segments[:5]:
            start_min = int(seg.start_time // 60)
            start_sec = int(seg.start_time % 60)
            end_min = int(seg.end_time // 60)
            end_sec = int(seg.end_time % 60)

            reasons = []
            if seg.rewatch_count > 1:
                reasons.append(f"rewatched {seg.rewatch_count}x")
            if seg.pause_count > 2:
                reasons.append(f"paused {seg.pause_count}x")
            if seg.was_skipped:
                reasons.append("skipped forward")
            if seg.avg_speed < 0.8:
                reasons.append(f"slowed to {seg.avg_speed}x")
            if seg.tab_switch_count > 0:
                reasons.append("tab switches detected")

            reason_str = f" ({', '.join(reasons)})" if reasons else ""
            recs.append(
                f"Review section {seg.start_time:.0f}s-{seg.end_time:.0f}s "
                f"({start_min}:{start_sec:02d}–{end_min}:{end_sec:02d}){reason_str}"
            )

        return recs
