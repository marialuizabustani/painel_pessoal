"""Catálogo de fontes monitoradas.

Duas famílias de fontes:

* **Feeds RSS editoriais** — veículos especializados. ``curated=True`` indica um
  veículo 100% dedicado a tendências/inovação: todas as matérias são aceitas.
  Nos demais, só entram matérias que casam com a taxonomia (ver ``classifier``).
* **Google News (busca)** — consultas temáticas em EN e PT que ampliam a
  cobertura para veículos sem RSS. O veículo original vai em ``publisher``.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True, slots=True)
class Source:
    slug: str
    name: str
    site_url: str
    feed_url: str
    language: str  # 'en' | 'pt'
    kind: str = "rss"  # 'rss' | 'google_news'
    curated: bool = False
    # Tópico atribuído quando o classificador não encontra nenhum termo
    # (fontes curadas e buscas temáticas já são on-topic por construção).
    default_topic: str | None = None


RSS_SOURCES: tuple[Source, ...] = (
    # --- Inglês: trend forecasting / coolhunting / foresight -----------------
    Source(
        "springwise",
        "Springwise",
        "https://www.springwise.com",
        "https://www.springwise.com/feed/",
        "en",
        curated=True,
        default_topic="disruptive-innovation",
    ),
    Source(
        "trend-hunter",
        "Trend Hunter",
        "https://www.trendhunter.com",
        "https://www.trendhunter.com/rss",
        "en",
        curated=True,
        default_topic="coolhunting",
    ),
    Source(
        "psfk",
        "PSFK",
        "https://www.psfk.com",
        "https://www.psfk.com/feed",
        "en",
        curated=True,
        default_topic="retail-innovation",
    ),
    Source(
        "cool-hunting",
        "Cool Hunting",
        "https://coolhunting.com",
        "https://coolhunting.com/feed/",
        "en",
        curated=True,
        default_topic="coolhunting",
    ),
    Source(
        "trendwatching",
        "TrendWatching",
        "https://www.trendwatching.com",
        "https://www.trendwatching.com/feed",
        "en",
        curated=True,
        default_topic="consumer-insights",
    ),
    # --- Inglês: moda, varejo e consumo ---------------------------------------
    Source(
        "business-of-fashion",
        "The Business of Fashion",
        "https://www.businessoffashion.com",
        "https://www.businessoffashion.com/arc/outboundfeeds/rss/",
        "en",
    ),
    Source(
        "vogue-business",
        "Vogue Business",
        "https://www.voguebusiness.com",
        "https://www.voguebusiness.com/feed/rss",
        "en",
    ),
    Source("glossy", "Glossy", "https://www.glossy.co", "https://www.glossy.co/feed/", "en"),
    Source(
        "modern-retail",
        "Modern Retail",
        "https://www.modernretail.co",
        "https://www.modernretail.co/feed/",
        "en",
    ),
    Source(
        "retail-dive",
        "Retail Dive",
        "https://www.retaildive.com",
        "https://www.retaildive.com/feeds/news/",
        "en",
    ),
    Source("hypebeast", "Hypebeast", "https://hypebeast.com", "https://hypebeast.com/feed", "en"),
    Source("dezeen", "Dezeen", "https://www.dezeen.com", "https://www.dezeen.com/feed/", "en"),
    # --- Inglês: tecnologia e inovação ----------------------------------------
    Source(
        "mit-tech-review",
        "MIT Technology Review",
        "https://www.technologyreview.com",
        "https://www.technologyreview.com/feed/",
        "en",
    ),
    Source(
        "fast-company",
        "Fast Company",
        "https://www.fastcompany.com",
        "https://www.fastcompany.com/latest/rss",
        "en",
    ),
    Source(
        "techcrunch", "TechCrunch", "https://techcrunch.com", "https://techcrunch.com/feed/", "en"
    ),
    Source(
        "the-verge",
        "The Verge",
        "https://www.theverge.com",
        "https://www.theverge.com/rss/index.xml",
        "en",
    ),
    Source("wired", "WIRED", "https://www.wired.com", "https://www.wired.com/feed/rss", "en"),
    # --- Português ------------------------------------------------------------
    Source(
        "mercado-e-consumo",
        "Mercado & Consumo",
        "https://mercadoeconsumo.com.br",
        "https://mercadoeconsumo.com.br/feed/",
        "pt",
    ),
    Source(
        "consumidor-moderno",
        "Consumidor Moderno",
        "https://consumidormoderno.com.br",
        "https://consumidormoderno.com.br/feed/",
        "pt",
    ),
    Source("startse", "StartSe", "https://www.startse.com", "https://www.startse.com/feed/", "pt"),
    Source("b9", "B9", "https://www.b9.com.br", "https://www.b9.com.br/feed/", "pt"),
    Source(
        "meio-e-mensagem",
        "Meio & Mensagem",
        "https://www.meioemensagem.com.br",
        "https://www.meioemensagem.com.br/feed",
        "pt",
    ),
    Source("ffw", "FFW", "https://ffw.uol.com.br", "https://ffw.uol.com.br/feed/", "pt"),
    Source(
        "fashion-network-br",
        "FashionNetwork Brasil",
        "https://br.fashionnetwork.com",
        "https://br.fashionnetwork.com/rss/feed/fashionnetwork_pt.xml",
        "pt",
    ),
    Source(
        "mit-tech-review-br",
        "MIT Technology Review Brasil",
        "https://mittechreview.com.br",
        "https://mittechreview.com.br/feed/",
        "pt",
    ),
    Source("tecnoblog", "Tecnoblog", "https://tecnoblog.net", "https://tecnoblog.net/feed/", "pt"),
    Source(
        "canaltech", "Canaltech", "https://canaltech.com.br", "https://canaltech.com.br/rss/", "pt"
    ),
    Source(
        "forbes-brasil",
        "Forbes Brasil",
        "https://forbes.com.br",
        "https://forbes.com.br/feed/",
        "pt",
    ),
)

# Consultas temáticas no Google News (janela de 1 dia): tópico -> (EN, PT).
GOOGLE_NEWS_QUERIES: dict[str, tuple[str, str]] = {
    "trend-forecasting": (
        '"trend forecasting" OR "trend forecast"',
        '"previsão de tendências" OR "relatório de tendências"',
    ),
    "consumer-insights": (
        '"consumer trends" OR "consumer insights"',
        '"tendências de consumo" OR "comportamento do consumidor"',
    ),
    "emerging-tech": (
        '"emerging technology" OR "emerging tech" launch',
        '"tecnologias emergentes" OR "tecnologia emergente"',
    ),
    "fashion-tech": (
        '"fashion tech" OR "fashion technology"',
        '"moda e tecnologia" OR "fashion tech" OR "moda digital"',
    ),
    "retail-innovation": (
        '"retail innovation" OR "future of retail"',
        '"inovação no varejo" OR "futuro do varejo"',
    ),
    "coolhunting": (
        'coolhunting OR "cool hunting" OR coolhunter',
        'coolhunting OR coolhunter OR "caçador de tendências"',
    ),
    "foresight": (
        '"strategic foresight" OR futurist OR "future trends"',
        'foresight OR futurismo OR "estudos de futuro"',
    ),
    "disruptive-innovation": (
        '"disruptive innovation" OR "disruptive startup"',
        '"inovação disruptiva" OR "startup disruptiva"',
    ),
    "cultural-trends": (
        '"cultural trends" OR "culture trend" OR "Gen Z trend"',
        '"tendências culturais" OR "tendência cultural" OR "geração Z" tendência',
    ),
}

_GN_LOCALE = {"en": ("en-US", "US", "US:en"), "pt": ("pt-BR", "BR", "BR:pt-419")}


def google_news_sources() -> tuple[Source, ...]:
    out: list[Source] = []
    for topic, queries in GOOGLE_NEWS_QUERIES.items():
        for lang, query in zip(("en", "pt"), queries, strict=True):
            hl, gl, ceid = _GN_LOCALE[lang]
            url = (
                "https://news.google.com/rss/search?q="
                f"{quote_plus(query + ' when:1d')}&hl={hl}&gl={gl}&ceid={ceid}"
            )
            out.append(
                Source(
                    slug=f"google-news-{lang}-{topic}",
                    name=f"Google News ({lang.upper()}) · {topic}",
                    site_url="https://news.google.com",
                    feed_url=url,
                    language=lang,
                    kind="google_news",
                    default_topic=topic,
                )
            )
    return tuple(out)


def all_sources() -> tuple[Source, ...]:
    return RSS_SOURCES + google_news_sources()
