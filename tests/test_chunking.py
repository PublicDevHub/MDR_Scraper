import pytest
from bs4 import BeautifulSoup
import src.mdr_parser
from src.mdr_parser import process_article, count_tokens, split_text_smartly

def test_token_counting():
    text = "Hello world "
    # Simple check
    count = count_tokens(text)
    assert count > 0

def test_split_text_smartly_small():
    text = "Small text.\n\nParagraph 2."
    chunks = split_text_smartly(text, limit=1000)
    assert len(chunks) == 1
    assert chunks[0] == text

def test_split_text_smartly_large():
    # "word " is usually 1 token.
    limit = 10
    # Create 2 paragraphs, each 8 tokens (8 * "word ")
    para1 = "word " * 8
    para2 = "word " * 8
    text = f"{para1}\n\n{para2}"

    # Total 16 tokens > 10. Should split.
    chunks = split_text_smartly(text, limit=limit)

    assert len(chunks) == 2
    # Verify content
    # strip() is called in logic
    assert chunks[0] == para1.strip()
    assert chunks[1] == para2.strip()

def test_process_article_chunking():
    # Patch the limit temporarily
    original_limit = src.mdr_parser.TOKEN_LIMIT
    src.mdr_parser.TOKEN_LIMIT = 20 # Very small limit

    try:
        # Construct HTML
        # Title "Artikel 999" is ~3-4 tokens.
        # We need paragraphs that push it over 20.
        # Para 1: 15 tokens. Total ~19. Fits.
        # Para 2: 15 tokens. Total ~34. Overflow -> Split.

        para1 = "a " * 15
        para2 = "b " * 15

        html = f"""
        <div class="eli-subdivision" id="art_999">
            <p class="title-article-norm">Artikel 999</p>
            <p>{para1}</p>
            <p>{para2}</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("div")

        chunks = process_article(element, "http://test", "2025-01-01")

        assert len(chunks) == 2
        assert chunks[0].id == "mdr_art_999_part1"
        assert chunks[1].id == "mdr_art_999_part2"

        # Check title preservation
        assert chunks[0].title == "Artikel 999"
        assert chunks[1].title == "Artikel 999"

        # Check source type
        assert chunks[0].source_type == "MDR"

    finally:
        src.mdr_parser.TOKEN_LIMIT = original_limit
