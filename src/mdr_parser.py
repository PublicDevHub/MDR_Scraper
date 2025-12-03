import requests
from bs4 import BeautifulSoup
import re
from typing import List, Optional

from src.models import MDRChunk

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
        chunk = process_article(art, url, valid_from)
        if chunk:
            chunks.append(chunk)

    # Process Annexes
    # Structure: <div id="anx_X">
    annexes = soup.find_all("div", id=re.compile(r"^anx_"))
    for anx in annexes:
        chunk = process_annex(anx, url, valid_from)
        if chunk:
            chunks.append(chunk)

    return chunks

def process_article(element: BeautifulSoup, base_url: str, valid_from: str) -> Optional[MDRChunk]:
    art_id_attr = element.get("id")
    if not art_id_attr:
        return None

    unique_id = f"mdr_{art_id_attr}"

    # Extract Title
    title_parts = []
    # Usually <p class="title-article-norm">Artikel X</p>
    # And sometimes <div class="eli-title">Descriptive Title</div>
    title_parts = []

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

    # Extract Content
    content = element.get_text(" ", strip=True)

    # Extract Chapter
    chapter_text = "N/A"
    parent = element.parent
    while parent:
        if parent.name == "div" and parent.get("id", "").startswith("cpt_"):
    # We want the full text of the article.
    content = element.get_text(" ", strip=True)

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
        if parent.name == "body":
                 chapter_text = parent.get("id") # Fallback
            break
        if parent.name == "body": # Stop at body
            break
        parent = parent.parent

    return MDRChunk(
        id=unique_id,
        source_type="MDR",
        title=title_text,
        content=content,
        url=f"{base_url}#{art_id_attr}",
        chapter=chapter_text,
        valid_from=valid_from,
        contentVector=None
        metadata={
            "chapter": chapter_text,
            "valid_from": valid_from
        }
    )

def process_annex(element: BeautifulSoup, base_url: str, valid_from: str) -> Optional[MDRChunk]:
    anx_id_attr = element.get("id")
    if not anx_id_attr:
        return None

    unique_id = f"mdr_{anx_id_attr.lower()}"

    # Title
    # <p class="title-annex-1">ANHANG I</p> or similar
    title_p = element.find("p", class_=re.compile(r"title-annex"))
    title_text = title_p.get_text(strip=True) if title_p else anx_id_attr

    content = element.get_text(" ", strip=True)

    return MDRChunk(
        id=unique_id,
        source_type="MDR",
        title=title_text,
        content=content,
        url=f"{base_url}#{anx_id_attr}",
        chapter="Annex",
        valid_from=valid_from,
        contentVector=None
        metadata={
            "chapter": "Annex",
            "valid_from": valid_from
        }
    )
