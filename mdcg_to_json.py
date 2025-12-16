import os
import glob
import json
import uuid
import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_text_splitters import MarkdownHeaderTextSplitter

load_dotenv()

# --- CONFIG ---
INPUT_FOLDER = os.getenv("OUTPUT_MD_PATH_REFINED")
OUTPUT_FOLDER = os.getenv("OUTPUT_JSON_PATH")
DEFAULT_VALID_FROM = datetime.datetime.now().strftime("%Y-%m-%dT00:00:00Z")

# --- DATA MODEL ---
class MDRChunk(BaseModel):
    id: str = Field(..., description="Unique ID")
    source_type: Literal["MDR", "MDCG", "SOP"] = Field(..., description="Source type")
    title: str = Field(..., description="The Heading or Doc Title")
    content: str = Field(..., description="The full text or chunk")
    url: str = Field(..., description="Source URL or File Path")
    chapter: str = Field(..., description="Context/Section Header")
    valid_from: str = Field(..., description="ISO 8601 Date")
    contentVector: Optional[List[float]] = Field(default=None)

def convert_md_to_json_structure():
    # 1. Ordner Checks
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ Ordner {INPUT_FOLDER} nicht gefunden.")
        return
    
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"✅ Output Ordner '{OUTPUT_FOLDER}' erstellt.")

    md_files = glob.glob(os.path.join(INPUT_FOLDER, "*.md"))
    print(f"🚀 Konvertiere {len(md_files)} Markdown-Dateien in separate JSONs...")

    # Splitter Konfiguration
    headers_to_split_on = [
        ("#", "Title"),
        ("##", "Chapter"),
        ("###", "Section"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

    # 2. Loop über Files
    for file_path in md_files:
        filename = os.path.basename(file_path)
        # Basis-Name ohne Endungen (z.B. "MDCG_2021-6_Rev_1")
        doc_name_clean = filename.replace("_cleaned.md", "").replace(".md", "")
        
        # Container für DIESES Dokument
        doc_chunks = []
        
        # URL Simulation
        fake_url = f"https://dein-storage.blob.core.windows.net/pdfs/{doc_name_clean}.pdf"

        print(f"   ...processing {filename}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            # Splitting
            splits = markdown_splitter.split_text(text)
            
            for split in splits:
                content = split.page_content
                metadata = split.metadata
                
                # Mapping Logic
                chunk_title = metadata.get("Title", doc_name_clean)
                
                # Chapter Path Building
                chapter_parts = []
                if "Chapter" in metadata: chapter_parts.append(metadata["Chapter"])
                if "Section" in metadata: chapter_parts.append(metadata["Section"])
                chapter_text = " > ".join(chapter_parts) if chapter_parts else "General"

                # ID Generation
                chunk_id = f"mdcg_{uuid.uuid4().hex[:8]}"

                # Pydantic Model
                chunk_obj = MDRChunk(
                    id=chunk_id,
                    source_type="MDCG",
                    title=chunk_title,
                    content=content,
                    url=fake_url,
                    chapter=chapter_text,
                    valid_from=DEFAULT_VALID_FROM,
                    contentVector=None
                )
                
                doc_chunks.append(chunk_obj.dict())

            # 3. Speichern pro Dokument
            json_filename = f"{doc_name_clean}.json"
            output_path = os.path.join(OUTPUT_FOLDER, json_filename)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(doc_chunks, f, indent=2, ensure_ascii=False)
            
            print(f"      -> Saved {len(doc_chunks)} chunks to {json_filename}")

        except Exception as e:
            print(f"❌ Fehler bei {filename}: {e}")

    print(f"\n✅ Fertig. JSONs liegen in '{OUTPUT_FOLDER}'.")

if __name__ == "__main__":
    convert_md_to_json_structure()