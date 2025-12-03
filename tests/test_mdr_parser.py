import pytest
from src.mdr_parser import parse_mdr

# Sample HTML mock
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div id="cpt_I">
        <p>KAPITEL I</p>
        <div class="eli-subdivision" id="art_1">
            <p class="title-article-norm">Artikel 1</p>
            <div class="eli-title">Gegenstand</div>
            <div class="norm">
                <p>Dies ist der Inhalt von Artikel 1.</p>
            </div>
        </div>
    </div>

    <div class="eli-container">
        <div id="anx_I">
            <p class="title-annex-1">ANHANG I</p>
            <p>Inhalt von Anhang I.</p>
        </div>
    </div>
</body>
</html>
"""

def test_parse_mdr_articles():
    chunks = parse_mdr(SAMPLE_HTML, "http://example.com")

    # We expect 2 chunks: Art 1 and Anhang I
    assert len(chunks) == 2

    # Check Article 1
    art1 = next(c for c in chunks if c.id == "mdr_art_1")
    assert art1.title == "Artikel 1 - Gegenstand"
    assert "Dies ist der Inhalt von Artikel 1." in art1.content
    assert art1.source_type == "MDR"
    assert art1.url == "http://example.com#art_1"

    # Check flattened fields
    assert art1.chapter == "KAPITEL I"
    assert art1.valid_from == "2025-01-10T00:00:00Z" # ISO format check
    assert art1.contentVector is None
    assert art1.metadata["chapter"] == "KAPITEL I"
    assert art1.metadata["valid_from"] == "2025-01-10"

def test_parse_mdr_annex():
    chunks = parse_mdr(SAMPLE_HTML, "http://example.com")

    # Check Annex I
    anx1 = next(c for c in chunks if c.id == "mdr_anx_i")
    assert anx1.title == "ANHANG I"
    assert "Inhalt von Anhang I." in anx1.content
    assert anx1.chapter == "Annex"
    assert anx1.valid_from == "2025-01-10T00:00:00Z"
    assert anx1.metadata["chapter"] == "Annex"

def test_parse_mdr_empty():
    chunks = parse_mdr("<html></html>", "http://example.com")
    assert len(chunks) == 0
