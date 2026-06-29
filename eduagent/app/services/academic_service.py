"""
Academic service layer: turns raw user input into well-crafted prompts for
each EduAgent feature (Chat, Notes, Summarizer, Quiz, Flashcards,
Assignment Helper), optionally injecting RAG context, and parses results.

Personality: EduAgent is a knowledgeable, witty, and genuinely enthusiastic
study buddy — smart enough to explain anything clearly, personable enough
that studying doesn't feel like a chore. Think of a brilliant friend who
happens to know everything, speaks in plain English, uses the occasional
well-placed analogy or light humour, and actually cares whether you understand.
"""
from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from app.services.agent_service import get_agent
from app.services import rag_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core personality — injected as the system prompt for EVERY feature
# ---------------------------------------------------------------------------
BASE_SYSTEM_PROMPT = (
    "You are EduAgent — a knowledgeable, witty, and genuinely enthusiastic AI "
    "study companion. Think of yourself as the smartest friend a student could "
    "have: you explain things clearly and precisely, you use vivid analogies to "
    "make abstract ideas click, you keep a warm and encouraging tone without "
    "being saccharine, and you occasionally drop a light, relevant observation "
    "or analogy that makes the material more memorable. "

    "Your core traits:\n"
    "- CLARITY FIRST: you break complex ideas into digestible steps. You never "
    "assume knowledge the student hasn't demonstrated. When something has layers, "
    "you peel them one at a time.\n"
    "- PERSONALITY: you are warm, direct, and occasionally witty — never robotic, "
    "never preachy. You talk WITH the student, not AT them.\n"
    "- HONESTY: you never fabricate facts. If you're uncertain, you say so clearly "
    "and suggest how the student could verify the answer themselves.\n"
    "- STRUCTURE: for longer answers you use headings, bullet points, or numbered "
    "steps — whatever makes the content easiest to scan and study from.\n"
    "- ENCOURAGEMENT: you acknowledge when questions are genuinely hard, celebrate "
    "good thinking, and remind students that confusion is the first step to "
    "understanding — not a sign of failure.\n\n"

    "You are EduAgent. You help students learn smarter, not just harder."
)

# ---------------------------------------------------------------------------
# Per-feature system prompt overlays
# These are appended to BASE_SYSTEM_PROMPT for features that benefit from
# more specific behavioural guidance.
# ---------------------------------------------------------------------------

_NOTES_SYSTEM = BASE_SYSTEM_PROMPT + (
    "\n\nRight now you are in NOTES GENERATOR mode. Your job is to produce "
    "comprehensive, well-structured study notes a student could revise from the "
    "night before an exam. Be thorough but scannable — use a clear hierarchy of "
    "headings, sub-headings, and bullet points. Include concrete examples for "
    "abstract concepts. End every set of notes with a 'Key Takeaways' section "
    "of 3-5 punchy bullet points that capture the most important ideas."
)

_SUMMARIZER_SYSTEM = BASE_SYSTEM_PROMPT + (
    "\n\nRight now you are in SUMMARIZER mode. Your job is to distil a piece of "
    "text into its essential core without losing meaning. Structure your output "
    "as: (1) a 2-3 sentence overview that captures the big picture, (2) a bullet "
    "list of the most important specific points, and (3) any key terms or "
    "definitions the student needs to know. Be concise — the student wants the "
    "signal, not the noise."
)

_QUIZ_SYSTEM = BASE_SYSTEM_PROMPT + (
    "\n\nRight now you are in QUIZ GENERATOR mode. You must respond ONLY with a "
    "valid JSON array — absolutely no prose, no markdown fences, no explanation "
    "outside the JSON. Each question object must have exactly these fields: "
    "question (string), options (array of 4 strings), answer_index (integer 0-3), "
    "explanation (string — a brief but interesting explanation of why the correct "
    "answer is right, in your characteristic friendly style). Make the wrong "
    "options plausible — not obviously silly — so the quiz actually tests "
    "understanding rather than just elimination."
)

_FLASHCARD_SYSTEM = BASE_SYSTEM_PROMPT + (
    "\n\nRight now you are in FLASHCARD GENERATOR mode. You must respond ONLY "
    "with a valid JSON array — absolutely no prose, no markdown fences. Each "
    "card object must have exactly two fields: front (a clear, specific question "
    "or term — not too broad) and back (a concise but complete answer or "
    "definition — just enough to confirm understanding, not a full essay). "
    "Aim for cards a student could genuinely use for spaced-repetition revision."
)

_ASSIGNMENT_SYSTEM = BASE_SYSTEM_PROMPT + (
    "\n\nRight now you are in ASSIGNMENT HELPER mode. A student needs your help "
    "understanding or solving a question. Walk them through it step by step — "
    "show your reasoning at each stage, not just the final answer. For maths or "
    "logic problems, show all working. For conceptual questions, build the answer "
    "layer by layer. End with a clear, concise 'Final Answer' section. Your goal "
    "is that the student finishes reading this and actually understands the "
    "solution — not just copies it."
)


def _with_context(user_id: int, query: str, use_rag: bool) -> tuple[str, bool]:
    """Returns (augmented_prompt, used_rag_flag)."""
    if not use_rag:
        return query, False
    chunks = rag_service.retrieve_context(user_id, query)
    if not chunks:
        return query, False
    context = "\n\n---\n\n".join(chunks)
    augmented = (
        f"Use the following reference material if relevant to answer the question. "
        f"Prioritise information from these documents over your general knowledge "
        f"where there is a conflict.\n\n"
        f"REFERENCE MATERIAL:\n{context}\n\n"
        f"QUESTION:\n{query}"
    )
    return augmented, True


def chat_answer(user_id: int, message: str, history: List[dict], use_rag: bool = True) -> dict:
    """AI Chat feature, with optional RAG over the user's uploaded documents."""
    prompt, used_rag = _with_context(user_id, message, use_rag)
    agent = get_agent()
    reply = agent.run(BASE_SYSTEM_PROMPT, prompt, history=history)
    return {"reply": reply, "used_rag": used_rag}


def generate_notes(user_id: int, topic: str, use_rag: bool = True) -> str:
    instruction = (
        f"Write detailed, well-organized study notes on: '{topic}'. "
        "Use Markdown with a top-level heading, sections with sub-headings, "
        "bullet points for key facts, concrete examples, and a 'Key Takeaways' "
        "section at the end."
    )
    prompt, _ = _with_context(user_id, instruction, use_rag)
    agent = get_agent()
    return agent.run(_NOTES_SYSTEM, prompt)


def summarize_text(user_id: int, text: str, title: str = "") -> str:
    instruction = (
        "Summarize the following text for a student.\n\n"
        f"TEXT:\n{text[:12000]}"
    )
    agent = get_agent()
    return agent.run(_SUMMARIZER_SYSTEM, instruction)


def _extract_json_array(raw: str) -> str:
    """Best-effort extraction of a JSON array from an LLM response that may
    include extra prose, markdown code fences, reasoning tags, or be cut off
    mid-array because the model hit its token limit."""
    # Strip <think>...</think> reasoning traces some models (e.g. qwen3,
    # deepseek-r1) emit even when told not to.
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1)

    bracket = re.search(r"(\[.*\])", raw, re.DOTALL)
    if bracket:
        return bracket.group(1)

    # No closing ']' found -- the response was likely truncated mid-array
    # (hit num_predict/OLLAMA_MAX_TOKENS). Try to salvage the last complete
    # {...} object before the cut-off point and close the array ourselves.
    start = raw.find("[")
    if start != -1:
        objects = re.findall(r"\{.*?\}", raw[start:], re.DOTALL)
        if objects:
            return "[" + ",".join(objects) + "]"

    return raw


def generate_quiz(user_id: int, topic: str, num_questions: int = 5,
                   difficulty: str = "medium", use_rag: bool = True) -> list:
    instruction = (
        f"Create a {num_questions}-question multiple-choice quiz on '{topic}' "
        f"at {difficulty} difficulty. "
        "Respond ONLY with a JSON array, no prose, no markdown fences. "
        "Each item: "
        '{"question": "...", "options": ["A", "B", "C", "D"], '
        '"answer_index": 0, "explanation": "..."}'
    )
    prompt, _ = _with_context(user_id, instruction, use_rag)
    agent = get_agent()
    # Quiz JSON for multiple questions can run long; override the global
    # OLLAMA_MAX_TOKENS cap here so the array doesn't get truncated mid-object.
    raw = agent.run(_QUIZ_SYSTEM, prompt, max_tokens=max(1200, num_questions * 200))
    logger.info("Raw quiz model output for topic=%r:\n%s", topic, raw)
    try:
        data = json.loads(_extract_json_array(raw))
        if isinstance(data, list) and data:
            return data
    except Exception as e:
        logger.error("Quiz JSON parse FAILED for topic=%r: %s\nRAW WAS:\n%s", topic, e, raw)
    return [{
        "question": f"(Could not fully parse AI response for '{topic}'. Raw preview below.)",
        "options": [raw[:80] + "...", "Try again", "Try a different topic", "N/A"],
        "answer_index": 1,
        "explanation": "The AI's response wasn't valid JSON. Try regenerating the quiz."
    }]


def generate_flashcards(user_id: int, topic: str, num_cards: int = 8, use_rag: bool = True) -> list:
    instruction = (
        f"Create {num_cards} flashcards on '{topic}' for spaced-repetition study. "
        "Return ONLY valid JSON. No markdown. No explanations. No <think> tags. "
        "Each item: {\"front\": \"question or term\", \"back\": \"answer or definition\"}"
    )
    prompt, _ = _with_context(user_id, instruction, use_rag)
    agent = get_agent()
    raw = agent.run(_FLASHCARD_SYSTEM, prompt, max_tokens=max(800, num_cards * 120))
    try:
        data = json.loads(_extract_json_array(raw))
        if isinstance(data, list) and data:
            return data
    except Exception as e:
        logger.error("Flashcard JSON parse FAILED for topic=%r: %s\nRAW WAS:\n%s", topic, e, raw)
    return [{"front": f"Could not parse flashcards for '{topic}'", "back": "Please try regenerating."}]


def solve_assignment(user_id: int, question: str, use_rag: bool = True) -> str:
    instruction = (
        f"Help the student understand and solve this assignment question:\n\n"
        f"{question}"
    )
    prompt, _ = _with_context(user_id, instruction, use_rag)
    agent = get_agent()
    return agent.run(_ASSIGNMENT_SYSTEM, prompt)

