"""Classificação bilíngue (EN/PT) de matérias na taxonomia de temas.

Abordagem leve e determinística, baseada em termos com pesos: termos no título
valem o dobro dos termos no resumo. O texto é normalizado (minúsculas, sem
acentos) para que "inovação" e "inovacao" casem igualmente.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

TITLE_WEIGHT = 2.0
SUMMARY_WEIGHT = 1.0
# Pontuação mínima para aceitar matéria de fonte não curada.
MIN_SCORE = 2.0

# tópico -> {termo: peso}. Termos já em minúsculas e sem acento.
TOPIC_TERMS: Mapping[str, Mapping[str, float]] = {
    "trend-forecasting": {
        "trend forecast": 3,
        "trend forecasting": 3,
        "trend report": 2,
        "trends report": 2,
        "trends for 20": 2,
        "macro trend": 2,
        "microtrend": 2,
        "micro-trend": 2,
        "previsao de tendencias": 3,
        "relatorio de tendencias": 2,
        "tendencias para 20": 2,
        "macrotendencia": 2,
        "microtendencia": 2,
        "wgsn": 2,
        "trendwatching": 2,
    },
    "consumer-insights": {
        "consumer trend": 3,
        "consumer insight": 3,
        "consumer behavior": 2,
        "consumer behaviour": 2,
        "shoppers": 1,
        "gen z": 1.5,
        "gen alpha": 1.5,
        "millennials": 1,
        "consumer survey": 2,
        "consumer spending": 1,
        "tendencias de consumo": 3,
        "tendencia de consumo": 3,
        "comportamento do consumidor": 3,
        "consumidor": 1,
        "consumidores": 1,
        "geracao z": 1.5,
        "pesquisa de consumo": 2,
    },
    "emerging-tech": {
        "emerging tech": 3,
        "emerging technology": 3,
        "generative ai": 2,
        "gen ai": 1.5,
        "artificial intelligence": 1,
        "ai agent": 1.5,
        "wearable": 2,
        "smart glasses": 2,
        "spatial computing": 2,
        "augmented reality": 1.5,
        "virtual reality": 1,
        "robotics": 1.5,
        "humanoid": 1.5,
        "quantum": 1.5,
        "biotech": 1.5,
        "3d printing": 1.5,
        "prototype": 1,
        "unveils": 1,
        "launches": 1,
        "new device": 1.5,
        "tecnologia emergente": 3,
        "tecnologias emergentes": 3,
        "inteligencia artificial": 1,
        "ia generativa": 2,
        "realidade aumentada": 1.5,
        "realidade virtual": 1,
        "robotica": 1.5,
        "vestivel": 2,
        "vestiveis": 2,
        "oculos inteligentes": 2,
        "computacao quantica": 1.5,
        "lanca": 1,
        "lancamento": 1,
        "novo dispositivo": 1.5,
    },
    "fashion-tech": {
        "fashion tech": 3,
        "fashiontech": 3,
        "fashion technology": 3,
        "virtual try-on": 3,
        "digital fashion": 3,
        "smart textile": 3,
        "wearable tech": 2,
        "resale": 1.5,
        "circular fashion": 2,
        "biomaterial": 2,
        "lab-grown": 1.5,
        "phygital": 2,
        "moda e tecnologia": 3,
        "moda digital": 3,
        "provador virtual": 3,
        "tecido inteligente": 3,
        "moda circular": 2,
        "brecho": 1.5,
    },
    "retail-innovation": {
        "retail innovation": 3,
        "future of retail": 3,
        "retail tech": 3,
        "retailtech": 3,
        "store of the future": 3,
        "concept store": 2,
        "flagship": 1,
        "pop-up": 1.5,
        "omnichannel": 2,
        "social commerce": 2,
        "live shopping": 2,
        "checkout-free": 2,
        "retail media": 2,
        "e-commerce": 1,
        "ecommerce": 1,
        "quick commerce": 2,
        "inovacao no varejo": 3,
        "futuro do varejo": 3,
        "varejo": 1.5,
        "loja conceito": 2,
        "omnicanal": 2,
        "comercio social": 2,
        "live commerce": 2,
        "loja do futuro": 3,
    },
    "coolhunting": {
        "coolhunting": 3,
        "cool hunting": 3,
        "coolhunter": 3,
        "limited edition": 1.5,
        "collab": 1.5,
        "collaboration": 1,
        "capsule collection": 2,
        "drop": 0.5,
        "sneaker": 1.5,
        "streetwear": 1.5,
        "design week": 1.5,
        "concept": 1,
        "cacador de tendencias": 3,
        "edicao limitada": 1.5,
        "colaboracao": 1,
        "colecao capsula": 2,
    },
    "foresight": {
        "foresight": 3,
        "futurist": 3,
        "futures thinking": 3,
        "scenario planning": 2.5,
        "future of": 1.5,
        "by 2030": 1.5,
        "by 2035": 1.5,
        "by 2040": 1.5,
        "speculative design": 2,
        "futurismo": 3,
        "futurista": 2,
        "estudos de futuro": 3,
        "cenarios futuros": 2.5,
        "futuro do": 1.5,
        "futuro da": 1.5,
        "ate 2030": 1.5,
    },
    "disruptive-innovation": {
        "disruptive": 2.5,
        "disruption": 2,
        "breakthrough": 1.5,
        "game-changer": 1.5,
        "startup": 1,
        "unicorn": 1.5,
        "innovation": 1,
        "innovative": 1,
        "first-ever": 1.5,
        "world's first": 2,
        "new business model": 2,
        "disruptiva": 2.5,
        "disruptivo": 2.5,
        "disrupcao": 2,
        "inovacao": 1,
        "inovador": 1,
        "inovadora": 1,
        "unicornio": 1.5,
        "pioneira": 1.5,
        "pioneiro": 1.5,
        "primeiro do mundo": 2,
    },
    "cultural-trends": {
        "cultural trend": 3,
        "culture trend": 3,
        "pop culture": 2,
        "subculture": 2,
        "tiktok": 1,
        "viral": 1,
        "aesthetic": 1.5,
        "zeitgeist": 2.5,
        "creator economy": 2,
        "fandom": 1.5,
        "nostalgia": 1.5,
        "wellness": 1,
        "loneliness economy": 2,
        "tendencia cultural": 3,
        "tendencias culturais": 3,
        "cultura pop": 2,
        "subcultura": 2,
        "estetica": 1.5,
        "economia criativa": 2,
        "economia dos criadores": 2,
        "bem-estar": 1,
    },
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("’", "'")
    return re.sub(r"\s+", " ", text.lower()).strip()


def _compile(terms: Mapping[str, float]) -> list[tuple[re.Pattern[str], float]]:
    return [(re.compile(rf"(?<![\w]){re.escape(t)}(?![\w])"), w) for t, w in terms.items()]


_PATTERNS = {topic: _compile(terms) for topic, terms in TOPIC_TERMS.items()}


@dataclass(frozen=True, slots=True)
class Classification:
    topics: dict[str, float]  # tópico -> pontuação

    @property
    def score(self) -> float:
        return round(sum(self.topics.values()), 2)


def classify(title: str, summary: str = "", default_topic: str | None = None) -> Classification:
    """Pontua a matéria por tópico. Se nada casar, usa ``default_topic`` (score 1)."""
    t, s = normalize(title), normalize(summary)
    scores: dict[str, float] = {}
    for topic, patterns in _PATTERNS.items():
        total = 0.0
        for pattern, weight in patterns:
            if pattern.search(t):
                total += weight * TITLE_WEIGHT
            elif pattern.search(s):
                total += weight * SUMMARY_WEIGHT
        if total > 0:
            scores[topic] = round(total, 2)
    if default_topic and default_topic not in scores:
        scores[default_topic] = 1.0
    return Classification(dict(sorted(scores.items(), key=lambda kv: -kv[1])))


def is_relevant(c: Classification, *, curated: bool, has_default: bool) -> bool:
    if curated or has_default:
        return bool(c.topics)
    return c.score >= MIN_SCORE
