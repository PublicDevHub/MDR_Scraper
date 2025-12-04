import requests
from bs4 import BeautifulSoup
import re
from typing import List, Optional
import tiktoken

from src.models import MDRChunk

# Configuration
TOKEN_LIMIT = 8000
ENCODING_NAME = "cl100k_base"

def get_tokenizer():
    try:
        return tiktoken.get_encoding(ENCODING_NAME)
    except Exception as e:
        print(f"Warning: Could not load tiktoken encoding {ENCODING_NAME}: {e}")
        return None

TOKENIZER = get_tokenizer()

def count_tokens(text: str) -> int:
    if TOKENIZER:
        return len(TOKENIZER.encode(text))
    else:
        # Fallback approximation: 1 token ~= 4 chars
        return len(text) // 4

def split_text_smartly(text: str, limit: int = None) -> List[str]:
    """
    Splits text into chunks respecting the token limit.
    Preserves paragraph structure by splitting on double newlines first.
    """
    if limit is None:
        limit = TOKEN_LIMIT

    if count_tokens(text) <= limit:
        return [text]

    chunks = []
    current_chunk_parts = []
    current_chunk_tokens = 0

    # Assuming text was extracted with "\n\n" separators
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = count_tokens(para)

        # If a single paragraph exceeds the limit, we must force split it
        # (This is a rare edge case, but safety first)
        if para_tokens > limit:
            # If we have accumulated content, save it first
            if current_chunk_parts:
                chunks.append("\n\n".join(current_chunk_parts))
                current_chunk_parts = []
                current_chunk_tokens = 0

            # Now split the massive paragraph by character or smaller delimiters
            # For simplicity, we'll just slice the string (not ideal but fallback)
            # Better: split by single newline or space
            # For now, we append it as is. If it's > 8000 tokens, it's a huge paragraph.
            chunks.append(para)
            continue

        if current_chunk_tokens + para_tokens > limit:
            # Chunk full, save it
            chunks.append("\n\n".join(current_chunk_parts))
            current_chunk_parts = []
            current_chunk_tokens = 0

        current_chunk_parts.append(para)
        current_chunk_tokens += para_tokens

    if current_chunk_parts:
        chunks.append("\n\n".join(current_chunk_parts))

    return chunks

def fetch_html(url: str) -> str:
    """
    Fetches the HTML content from the given URL.
    """
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def parse_mdr(html_content: str, url: str, valid_from: str = "2025-01-10") -> List[MDRChunk]:
    """
    Parses the MDR HTML content and returns a list of MDRChunk objects.
    """
    soup = BeautifulSoup(html_content, "lxml")
    chunks = []

    # Ensure ISO 8601 format for valid_from
    if re.match(r"^\d{4}-\d{2}-\d{2}$", valid_from):
        valid_from = f"{valid_from}T00:00:00Z"

    # Process Articles
    # Structure: <div class="eli-subdivision" id="art_X">
    articles = soup.find_all("div", class_="eli-subdivision", id=re.compile(r"^art_\d+"))
    for art in articles:
        article_chunks = process_article(art, url, valid_from)
        chunks.extend(article_chunks)

    # Process Annexes
    # Structure: <div id="anx_X">
    annexes = soup.find_all("div", id=re.compile(r"^anx_"))
    for anx in annexes:
        annex_chunks = process_annex(anx, url, valid_from)
        chunks.extend(annex_chunks)

    return chunks

def process_article(element: BeautifulSoup, base_url: str, valid_from: str) -> List[MDRChunk]:
    art_id_attr = element.get("id")
    if not art_id_attr:
        return []

    base_id = f"mdr_{art_id_attr}"

    # Extract Title
    title_parts = []
    # Usually <p class="title-article-norm">Artikel X</p>
    # And sometimes <div class="eli-title">Descriptive Title</div>

    title_p = element.find("p", class_="title-article-norm")
    if title_p:
        title_parts.append(title_p.get_text(strip=True))

    eli_title = element.find("div", class_="eli-title")
    if eli_title:
        title_parts.append(eli_title.get_text(strip=True))

    if not title_parts:
        # Fallback if no specific title tags found, though unlikely for valid articles
        title_text = f"Artikel {art_id_attr.split('_')[1]}"
    else:
        title_text = " - ".join(title_parts)

    # Extract Content with Paragraph Preservation
    content = element.get_text("\n\n", strip=True)

    # Extract Metadata: Chapter
    # The article is usually nested in a chapter div, e.g., <div id="cpt_II">
    chapter_text = "N/A"
    # Traverse parents to find chapter
    parent = element.parent
    while parent:
        if parent.name == "div" and parent.get("id", "").startswith("cpt_"):
            # Found chapter container
            # The chapter title is usually the first p tag(s)
            # e.g. "KAPITEL II"
            # We can try to grab the first p tag that looks like a title
            # In our analysis: first p was "KAPITEL II", second was the description.
            # We'll just grab the text of the first direct p child.
            chap_p = parent.find("p", recursive=False)
            if chap_p:
                chapter_text = chap_p.get_text(strip=True)
            else:
                 chapter_text = parent.get("id")
            break
        if parent.name == "body": # Stop at body
            break
        parent = parent.parent

    # Chunking
    text_chunks = split_text_smartly(content)

    results = []
    for i, chunk_text in enumerate(text_chunks):
        # Create unique ID for chunks
        if len(text_chunks) > 1:
            chunk_id = f"{base_id}_part{i+1}"
        else:
            chunk_id = base_id

        results.append(MDRChunk(
            id=chunk_id,
            source_type="MDR",
            title=title_text,
            content=chunk_text,
            url=f"{base_url}#{art_id_attr}",
            chapter=chapter_text,
            valid_from=valid_from,
            contentVector=None
        ))

    return results

def process_annex(element: BeautifulSoup, base_url: str, valid_from: str) -> List[MDRChunk]:
    anx_id_attr = element.get("id")
    if not anx_id_attr:
        return []

    base_id = f"mdr_{anx_id_attr.lower()}"

    # Title
    # <p class="title-annex-1">ANHANG I</p> or similar
    title_p = element.find("p", class_=re.compile(r"title-annex"))
    title_text = title_p.get_text(strip=True) if title_p else anx_id_attr

    # Content
    content = element.get_text("\n\n", strip=True)

    # Chunking
    text_chunks = split_text_smartly(content)

    results = []
    for i, chunk_text in enumerate(text_chunks):
        if len(text_chunks) > 1:
            chunk_id = f"{base_id}_part{i+1}"
        else:
            chunk_id = base_id

        results.append(MDRChunk(
            id=chunk_id,
            source_type="MDR",
            title=title_text,
            content=chunk_text,
            url=f"{base_url}#{anx_id_attr}",
            chapter="Annex",
            valid_from=valid_from,
            contentVector=None
        ))

    return results
