import time

import feedparser

from collector.parsing import clean_url, entry_to_article, html_to_text
from collector.sources import Source, google_news_sources

RSS = Source("x", "X", "https://x.com", "https://x.com/feed", "en")


def test_clean_url_removes_tracking():
    url = "https://Example.com/a?utm_source=rss&id=3&fbclid=abc#frag"
    assert clean_url(url) == "https://example.com/a?id=3"


def test_clean_url_rejects_non_http():
    assert clean_url("javascript:alert(1)") is None
    assert clean_url("") is None


def test_html_to_text_truncates():
    text = html_to_text("<p>" + "palavra " * 200 + "</p>", limit=50)
    assert len(text) <= 50 and text.endswith("…")


def test_entry_to_article_rss():
    xml = """<rss><channel><item>
      <title>Retail innovation &amp; more</title>
      <link>https://x.com/post?utm_medium=feed</link>
      <description>&lt;p&gt;Hello &lt;img src="https://x.com/i.jpg"&gt;&lt;/p&gt;</description>
      <pubDate>Wed, 04 Nov 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>"""
    entry = feedparser.parse(xml).entries[0]
    art = entry_to_article(entry, RSS)
    assert art is not None
    assert art.url == "https://x.com/post"
    assert art.title == "Retail innovation & more"
    assert art.image_url == "https://x.com/i.jpg"
    assert art.published_at is not None and art.published_at.year == 2026


def test_entry_to_article_google_news_splits_publisher():
    gn = google_news_sources()[0]
    entry = feedparser.FeedParserDict(
        title="Big trend report - Vogue Business",
        link="https://news.google.com/rss/articles/abc",
        summary="ignored",
        published_parsed=time.gmtime(),
    )
    art = entry_to_article(entry, gn)
    assert art.title == "Big trend report"
    assert art.publisher == "Vogue Business"
    assert art.summary == ""


def test_google_news_sources_cover_both_languages():
    langs = {s.language for s in google_news_sources()}
    assert langs == {"en", "pt"}
    assert all(s.default_topic for s in google_news_sources())
