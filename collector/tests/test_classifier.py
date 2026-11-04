from collector.classifier import MIN_SCORE, classify, is_relevant, normalize


def test_normalize_strips_accents_and_case():
    assert normalize("  Inovação   no VAREJO ") == "inovacao no varejo"


def test_portuguese_retail_title_is_relevant():
    c = classify("O futuro do varejo: loja conceito aposta em IA", "")
    assert "retail-innovation" in c.topics
    assert is_relevant(c, curated=False, has_default=False)


def test_english_fashion_tech():
    c = classify("Brand launches virtual try-on for digital fashion", "")
    assert next(iter(c.topics)) == "fashion-tech"


def test_off_topic_is_rejected():
    c = classify("Local football team wins match", "The game ended 2-1.")
    assert c.score < MIN_SCORE
    assert not is_relevant(c, curated=False, has_default=False)


def test_default_topic_applies_to_curated_sources():
    c = classify("Something neutral", "", default_topic="coolhunting")
    assert c.topics == {"coolhunting": 1.0}
    assert is_relevant(c, curated=True, has_default=True)


def test_word_boundaries():
    # "drop" não deve casar dentro de "dropshipping"... nem "viral" em "antiviral"
    c = classify("New antiviral study", "")
    assert "cultural-trends" not in c.topics
