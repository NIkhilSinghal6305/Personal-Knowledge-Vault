"""
Quiz generation service.
Generates MCQ quizzes from documents using AI.
"""
import json
import re
from typing import List, Optional, Dict
from app.services.vector_store import query_similar_chunks
from app.services.llm_service import generate_response


def generate_quiz(
    user_id: int,
    document_ids: List[int],
    num_questions: int = 5,
    difficulty: str = "medium",
    topic: Optional[str] = None,
) -> Dict:
    """
    Generate an MCQ quiz from specified documents.
    Returns structured quiz data.
    """
    # Build query for retrieving relevant content
    query = topic if topic else "important concepts, definitions, and key facts"

    # Retrieve relevant chunks from the specified documents
    chunks = query_similar_chunks(
        user_id=user_id,
        query_text=query,
        n_results=10,
        document_ids=document_ids,
    )

    if not chunks:
        return {
            "questions": [],
            "topic": topic,
            "difficulty": difficulty,
            "source_documents": [],
            "error": "No content found in the specified documents.",
        }

    # Build context from chunks
    context = "\n\n".join([chunk["text"] for chunk in chunks])
    source_docs = list(set([c.get("metadata", {}).get("document_name", "Unknown") for c in chunks]))

    difficulty_instructions = {
        "easy": "Create simple, straightforward questions testing basic recall and understanding.",
        "medium": "Create questions that test understanding and application of concepts.",
        "hard": "Create challenging questions that test deep understanding, analysis, and ability to apply concepts in new contexts.",
    }

    diff_instruction = difficulty_instructions.get(difficulty, difficulty_instructions["medium"])

    prompt = f"""Generate exactly {num_questions} multiple-choice questions based on the following content.

CONTENT:
{context}

{f"Focus on the topic: {topic}" if topic else "Cover the most important concepts."}

{diff_instruction}

IMPORTANT: Respond ONLY with a valid JSON array. No other text before or after.
Each question must have this exact JSON structure:
[
  {{
    "question": "What is...?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": 0,
    "explanation": "The correct answer is A because..."
  }}
]

Rules:
- Each question must have exactly 4 options
- correct_answer is the 0-based index of the correct option
- Provide a brief explanation for each answer
- Questions should be based ONLY on the provided content
- Make questions clear and unambiguous"""

    response = generate_response(
        prompt,
        system_instruction="You are a quiz generator. Generate well-crafted MCQ questions. Respond ONLY with valid JSON.",
        temperature=0.5,
        max_tokens=3000,
    )

    # Parse the JSON response
    questions = parse_quiz_response(response)

    return {
        "questions": questions,
        "topic": topic,
        "difficulty": difficulty,
        "source_documents": source_docs,
    }


def parse_quiz_response(response: str) -> List[Dict]:
    """Parse the LLM's quiz response into structured data."""
    try:
        # Try direct JSON parse first
        questions = json.loads(response)
        if isinstance(questions, list):
            return validate_questions(questions)
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the response
    json_match = re.search(r"\[[\s\S]*\]", response)
    if json_match:
        try:
            questions = json.loads(json_match.group())
            if isinstance(questions, list):
                return validate_questions(questions)
        except json.JSONDecodeError:
            pass

    # If all parsing fails, return an error message as a single question
    return [
        {
            "question": "Quiz generation encountered an issue. Please try again.",
            "options": ["Try again", "Use different settings", "Select fewer questions", "Change topic"],
            "correct_answer": 0,
            "explanation": "The AI response could not be parsed into quiz format. Try regenerating.",
        }
    ]


def validate_questions(questions: List[Dict]) -> List[Dict]:
    """Validate and clean the question structure."""
    valid = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        if "question" not in q or "options" not in q:
            continue
        if not isinstance(q["options"], list) or len(q["options"]) < 2:
            continue

        # Ensure exactly 4 options
        while len(q["options"]) < 4:
            q["options"].append("N/A")
        q["options"] = q["options"][:4]

        # Ensure correct_answer is valid
        correct = q.get("correct_answer", 0)
        if not isinstance(correct, int) or correct < 0 or correct > 3:
            q["correct_answer"] = 0

        # Ensure explanation exists
        if "explanation" not in q or not q["explanation"]:
            q["explanation"] = "No explanation provided."

        valid.append(q)

    return valid
