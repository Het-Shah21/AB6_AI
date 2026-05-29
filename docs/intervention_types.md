# Intervention Types

| Type | Description | When to Use |
|---|---|---|
| concept_explanation | Generate theory/formula explanation | Struggling with concept understanding |
| video_recommendation | Recommend specific video timestamp | Visual learner needs reinforcement |
| prerequisite_nudge | Suggest revisiting prerequisite topic | Missing foundational knowledge |
| challenge_hint | Provide targeted hint for current challenge | Stuck on specific problem |
| challenge_swap | Replace next challenge with AI-generated one | Current challenge is inappropriate level |
| revision_prompt | Spaced repetition review | Mastery dropping on previously learned concepts |
| encouragement | Motivational nudge | Engagement score dropping |

## Selection Strategy: Thompson Sampling

Each intervention type is modeled as a Beta distribution arm:
- **Alpha**: Successful outcomes + 1
- **Beta**: Failed outcomes + 1

The agent samples from each arm and selects the highest sample. This naturally balances exploration (untried arms have wide distributions) vs exploitation (proven arms have narrow, high distributions).

## Effectiveness Tracking

After intervention delivery, the next challenge score is compared against a predicted baseline. The delta feeds back into the Wisdom Store.
