import os
import json
import re
import uuid
from typing import List, Optional, Literal
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- CONFIG LOADING ---
load_dotenv()
OUTPUT_JSON_PATH = os.getenv("OUTPUT_JSON_PATH", "data/json") 

# PFAD ZUR LOKALEN DATEI (Lösung A)
LOCAL_MDR_PATH = r"D:\mdr_raw\CELEX_32017R0745_DE_TXT.html"

# URL für Metadaten (damit der Link im RAG später funktioniert)
MDR_ONLINE_URL = "https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32017R0745"

# --- DATA MODEL ---
class MDRChunk(BaseModel):
    id: str = Field(..., description="Unique ID")
    source_type: Literal["MDR", "MDCG", "SOP"] = Field(..., description="Source type")
    title: str = Field(..., description="The Heading")
    content: str = Field(..., description="The text chunk")
    url: str = Field(..., description="Source URL with anchor")
    chapter: str = Field(..., description="Chapter title")
    valid_from: str = Field(..., description="ISO 8601 Date")
    contentVector: Optional[List[float]] = Field(default=None)

# --- SPLITTING CONFIG ---
CHUNK_SIZE = 2000 
CHUNK_OVERLAP = 200

def parse_mdr(html_content: str, base_url: str, valid_from: str = "2025-01-10") -> List[dict]:
    """
    Parses MDR HTML and returns a list of DICTIONARIES.
    """
    print("   Parsing HTML content with BeautifulSoup...")
    soup = BeautifulSoup(html_content, "lxml") # lxml ist schneller
    chunks = []

    if re.match(r"^\d{4}-\d{2}-\d{2}$", valid_from):
        valid_from = f"{valid_from}T00:00:00Z"

    # Smart Text Splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", r"(?=\d+\.)", " ", ""]
    )

    # 1. Articles
    # Suche nach divs mit 'eli-subdivision' UND id='art_...'
    articles = soup.find_all("div", class_="eli-subdivision", id=re.compile(r"^art_\d+"))
    print(f"   Found {len(articles)} Articles. Processing...")
    
    for art in articles:
        new_chunks = process_element_smart(art, "Article", base_url, valid_from, text_splitter)
        chunks.extend(new_chunks)

    # 2. Annexes
    annexes = soup.find_all("div", id=re.compile(r"^anx_"))
    print(f"   Found {len(annexes)} Annexes. Processing...")
    
    for anx in annexes:
        new_chunks = process_element_smart(anx, "Annex", base_url, valid_from, text_splitter)
        chunks.extend(new_chunks)

    return chunks

def get_chapter_title(element: BeautifulSoup) -> str:
    """Traverse parents to find the Chapter"""
    parent = element.parent
    while parent:
        if parent.name == "div" and parent.get("id", "").startswith("cpt_"):
            chap_p = parent.find("p", recursive=False)
            if chap_p:
                return chap_p.get_text(strip=True)
            return parent.get("id")
        if parent.name == "body":
            break
        parent = parent.parent
    return "N/A"

def process_element_smart(element: BeautifulSoup, kind: str, base_url: str, valid_from: str, splitter) -> List[dict]:
    """Extrahiert und splittet HTML-Elemente."""
    elem_id = element.get("id")
    if not elem_id: return []

    # Title Extraction
    title_parts = []
    if kind == "Article":
        t_p = element.find("p", class_="title-article-norm")
        if t_p: title_parts.append(t_p.get_text(strip=True))
        e_t = element.find("div", class_="eli-title")
        if e_t: title_parts.append(e_t.get_text(strip=True))
        full_title = " - ".join(title_parts) if title_parts else f"Artikel {elem_id}"
    else: 
        t_p = element.find("p", class_=re.compile(r"title-annex"))
        full_title = t_p.get_text(strip=True) if t_p else elem_id.upper()

    chapter = get_chapter_title(element) if kind == "Article" else "Annex"
    
    # Content Cleaning: Entferne überflüssige Whitespaces, behalte Text
    raw_text = element.get_text(" ", strip=True)

    # Splitting
    text_chunks = splitter.split_text(raw_text)
    
    final_chunks = []
    for i, chunk_text in enumerate(text_chunks):
        # Deterministische ID
        chunk_id = f"mdr_{elem_id}_{i}"
        
        # URL zeigt auf Online-Quelle (Anchor), nicht lokal
        chunk_url = f"{base_url}#{elem_id}"

        display_title = full_title
        if len(text_chunks) > 1:
            display_title = f"{full_title} (Part {i+1}/{len(text_chunks)})"

        chunk_obj = MDRChunk(
            id=chunk_id,
            source_type="MDR",
            title=display_title,
            content=chunk_text,
            url=chunk_url,
            chapter=chapter,
            valid_from=valid_from,
            contentVector=None
        )
        final_chunks.append(chunk_obj.dict())

    return final_chunks

# --- EXECUTION ---
if __name__ == "__main__":
    print(f"🚀 Starting MDR Parser (Local File Mode)...")
    print(f"📂 Reading from: {LOCAL_MDR_PATH}")
    print(f"📂 Output Target: {OUTPUT_JSON_PATH}")

    # Ordner erstellen
    if not os.path.exists(OUTPUT_JSON_PATH):
        os.makedirs(OUTPUT_JSON_PATH, exist_ok=True)

    try:
        # LOKALES LADEN
        if not os.path.exists(LOCAL_MDR_PATH):
            raise FileNotFoundError(f"Die Datei {LOCAL_MDR_PATH} wurde nicht gefunden. Bitte Pfad prüfen.")

        with open(LOCAL_MDR_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        print(f"   ✅ File loaded ({len(html_content)} chars). Parsing...")
        
        # Parsen
        data = parse_mdr(html_content, MDR_ONLINE_URL)
        
        if len(data) == 0:
            print("   ❌ WARNING: 0 chunks found. Check the HTML structure (Are classes 'eli-subdivision' correct?).")
        else:
            # Speichern
            output_file = os.path.join(OUTPUT_JSON_PATH, "mdr_full.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Success! Saved {len(data)} chunks to '{output_file}'")
            print("👉 NEXT STEP: Run 'python upload_manager.py' to index these chunks.")

    except Exception as e:
        print(f"❌ Error: {e}")