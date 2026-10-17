"""Small text helpers: lexical similarity for repeat-detection and skill extraction from resumes/JDs.

Similarity is lexical (token Jaccard). The interface (`similarity`, `is_repeat`) is deliberately
narrow so it can be swapped for embedding cosine similarity later without touching the engine.
"""
from __future__ import annotations

import re

from .question_bank import T

STOP = set("""a an the and or of to in on for with without is are was were be been being do does did
how what why when which who whom whose can could would should will you your yours i me my we our it its
this that these those there their them they he she his her as at by from into about than then so if
not no yes but also any some each more most such very just let lets let's tell explain describe give
please between versus vs""".split())


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+#]+", text.lower()) if t not in STOP and len(t) > 1}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def is_repeat(text: str, previous: list[str], threshold: float = 0.6) -> bool:
    norm = re.sub(r"\s+", " ", text.strip().lower())
    for p in previous:
        if norm == re.sub(r"\s+", " ", p.strip().lower()) or similarity(text, p) >= threshold:
            return True
    return False


# Skill lexicon: canonical skill -> regex. Kept explicit so matching is predictable and testable.
SKILLS: dict[str, str] = {
    "Java": r"\bjava\b(?!script)", "Spring Boot": r"spring", "Python": r"python", "Django": r"django",
    "Flask": r"flask", "FastAPI": r"fastapi", "JavaScript": r"javascript|\bjs\b", "TypeScript": r"typescript",
    "React": r"react", "Node.js": r"node\.?js|\bnode\b|express", "HTML/CSS": r"\bhtml|\bcss|tailwind|bootstrap",
    "SQL": r"\bsql\b|mysql|postgres|sqlite|oracle", "MongoDB": r"mongo", "Pandas": r"pandas|numpy",
    "Excel": r"excel|spreadsheet", "Power BI / Tableau": r"power ?bi|tableau|looker", "Statistics": r"statistic|hypothesis|a/b",
    "Machine Learning": r"machine learning|\bml\b|scikit|sklearn|xgboost", "Deep Learning": r"deep learning|pytorch|tensorflow|keras|cnn|lstm|transformer",
    "NLP / LLMs": r"\bnlp\b|\bllm|langchain|hugging ?face|bert|gpt", "Docker": r"docker|container", "Kubernetes": r"kubernetes|\bk8s\b",
    "AWS / Cloud": r"\baws\b|azure|gcp|cloud", "Git": r"\bgit\b|github|gitlab", "REST APIs": r"\brest\b|api",
    "Microservices": r"microservice", "Multithreading": r"thread|concurren", "Data Structures": r"data structure|algorithm|dsa|leetcode",
    "Testing": r"pytest|junit|jest|unit test|testing|selenium", "MLOps": r"mlops|mlflow|model deploy",
}

SKILL_TO_TOPICS: dict[str, list[str]] = {
    "Java": ["java_oop", "java_collections", "java_core"], "Spring Boot": ["spring_boot"],
    "Python": ["python_core", "python_advanced"], "Django": ["http_rest"], "Flask": ["http_rest"], "FastAPI": ["http_rest"],
    "JavaScript": ["javascript"], "TypeScript": ["javascript"], "React": ["react"], "Node.js": ["javascript", "http_rest"],
    "HTML/CSS": ["html_css"], "SQL": ["sql", "databases"], "MongoDB": ["databases"], "Pandas": ["data_analysis"],
    "Excel": ["data_analysis"], "Power BI / Tableau": ["data_viz"], "Statistics": ["statistics"],
    "Machine Learning": ["ml_fundamentals", "ml_evaluation"], "Deep Learning": ["deep_learning"], "NLP / LLMs": ["deep_learning"],
    "Docker": ["ml_ops", "system_design"], "Kubernetes": ["system_design"], "AWS / Cloud": ["system_design"],
    "REST APIs": ["http_rest"], "Microservices": ["system_design"], "Multithreading": ["java_concurrency"],
    "Data Structures": ["dsa"], "Testing": ["testing"], "MLOps": ["ml_ops"],
}


def extract_skills(text: str) -> list[str]:
    if not text:
        return []
    low = text.lower()
    return [skill for skill, pat in SKILLS.items() if re.search(pat, low)]


def topics_for_skills(skills: list[str], allowed: list[str]) -> list[str]:
    out: list[str] = []
    for s in skills:
        for tid in SKILL_TO_TOPICS.get(s, []):
            if tid in allowed and tid not in out and tid in T:
                out.append(tid)
    return out
