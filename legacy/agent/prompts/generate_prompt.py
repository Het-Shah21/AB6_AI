CHALLENGE_GENERATION_PROMPT = """You are an AI challenge generator for a robotics education platform.
Generate a {challenge_type} challenge for the concept "{concept_name}" at difficulty {difficulty}.

The challenge should:
1. Be appropriate for the given difficulty level (0.0 = easy, 1.0 = hard)
2. Test understanding of the core concept, not memorization
3. Include a clear problem statement
4. Include the correct answer and explanation

Domain: {domain}
Description: {description}

Here are some example challenges for reference:
{examples}

Respond with a JSON object:
For MCQ:
{{
    "type": "mcq",
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "correct_answer": 0,
    "explanation": "..."
}}
For code:
{{
    "type": "code",
    "problem_statement": "...",
    "solution_template": "...",
    "test_cases": [{{"input": "...", "expected_output": "..."}}],
    "explanation": "..."
}}
"""


CRITIQUE_PROMPT = """You are a quality assurance reviewer for educational content.
Review the following challenge and provide a critique.

Criteria:
1. Is the challenge appropriate for the stated difficulty level? (0-1)
2. Is the question clear and unambiguous? (0-1)
3. Is the answer correct? (0-1)
4. Is the explanation helpful? (0-1)

Return JSON: {{"quality_score": 0.0-1.0, "issues": ["..."], "suggestions": ["..."]}}

Challenge:
{challenge}
"""
