import os
import glob
import re
import tiktoken
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# --- CONFIG ---
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AOAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat") # Updated Model
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

INPUT_FOLDER = os.getenv("OUTPUT_MD_PATH")
OUTPUT_FOLDER =  os.getenv("OUTPUT_MD_PATH_REFINED")

# LIMITS (GPT-5.1 Specs)
MAX_OUTPUT_TOKENS = 128000 # Safety buffer unter 16.384
SAFE_CHUNK_SIZE = 110000   # Zielgröße für Input Chunks um Output Limit nicht zu reißen

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Zählt Tokens mit tiktoken. 
    Hinweis: GPT-5 nutzt meist das o200k_base Encoding, fallback auf cl100k_base (gpt-4o) ist oft nah genug.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base") # Annahme für GPT-5
    return len(encoding.encode(text))

def clean_chunk_with_llm(client: AzureOpenAI, chunk_text: str, doc_context: str) -> str:
    """
    Sendet einen Chunk an das LLM.
    """
    if not chunk_text.strip():
        return ""

    system_prompt = f"""
    You are a Data Cleaning Expert for Medical Device Regulation (MDR/IVDR) documents.
    Your task is to refine a specific section of a document into clean, semantic Markdown.
    
    CONTEXT: This section belongs to the document "{doc_context}".
    
    STRICT RULES:
    1. NO DATA LOSS: Preserve all regulatory content verbatim. Do NOT summarize.
    2. REMOVE NOISE: Remove page numbers (e.g. "Page 2 of 10"), artifacts (":unselected:"), and repeated headers.
    3. REMOVE TOC: If the text contains a Table of Contents, remove it.
    4. INTEGRATE FOOTNOTES: Move footnote explanations from the bottom to their reference point in the text: "word[1]" -> "word [Note: explanation]".
    5. FORMATTING: Ensure tables are valid Markdown.
    
    INPUT: Raw Markdown chunk.
    OUTPUT: Cleaned Markdown chunk only.
    """

    try:
        response = client.chat.completions.create(
            model=AOAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk_text}
            ],
            # Kein temperature Parameter für reasoning models/preview
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"   ⚠️ API Error: {e}")
        return chunk_text # Fallback

def recursive_split_and_process(client, text, doc_name):
    """
    Rekursive Funktion:
    1. Prüft Token Count.
    2. Wenn OK (< SAFE_CHUNK_SIZE) -> Process.
    3. Wenn zu groß -> Split bei Paragraphen (\n\n) und rekursiv aufrufen.
    """
    tokens = count_tokens(text)
    
    if tokens < SAFE_CHUNK_SIZE:
        return clean_chunk_with_llm(client, text, doc_name)
    
    # Zu groß: Split Strategy
    print(f"   ...Chunk too large ({tokens} tokens). Splitting further...")
    
    # Versuch 1: Split bei Double Newline (Paragraphen)
    parts = text.split("\n\n")
    if len(parts) == 1:
        # Versuch 2: Split bei Single Newline (Zeilen), wenn keine Paragraphen da sind
        parts = text.split("\n")
    
    # Re-assemble in kleinere Chunks
    current_chunk = ""
    processed_text = ""
    
    for part in parts:
        # Check ob part allein schon zu groß ist (unwahrscheinlich, aber sicher ist sicher)
        if count_tokens(current_chunk + "\n\n" + part) > SAFE_CHUNK_SIZE:
            # Process current batch
            processed_text += recursive_split_and_process(client, current_chunk, doc_name) + "\n\n"
            current_chunk = part
        else:
            current_chunk += "\n\n" + part if current_chunk else part
            
    # Rest verarbeiten
    if current_chunk:
        processed_text += recursive_split_and_process(client, current_chunk, doc_name)
        
    return processed_text

def run_refinement_pipeline():
    if not AOAI_ENDPOINT or not AOAI_KEY:
        print("❌ Error: Azure OpenAI Credentials missing.")
        return

    client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version=AOAI_API_VERSION
    )

    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ Input folder missing.")
        return
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    md_files = glob.glob(os.path.join(INPUT_FOLDER, "*.md"))
    print(f"🚀 Refinement Pipeline for {len(md_files)} docs (Model: {AOAI_DEPLOYMENT})")

    for file_path in md_files:
        filename = os.path.basename(file_path)
        print(f"\n📄 Processing: {filename}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Step 1: Grob-Split nach Headern (Semantisch bester Split)
        # Wir splitten vor jedem ## Header
        sections = re.split(r"(?=\n## )", raw_content)
        
        full_clean_doc = ""
        print(f"   ...Found {len(sections)} semantic sections.")

        for i, section in enumerate(sections):
            # Step 2: Safe Process (mit Token Check)
            clean_part = recursive_split_and_process(client, section, filename)
            full_clean_doc += clean_part + "\n\n"
            
            if i % 5 == 0: print(f"   ...section {i+1}/{len(sections)} done.")

        output_path = os.path.join(OUTPUT_FOLDER, filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_clean_doc)
        
        print(f"✅ Saved: {output_path}")

if __name__ == "__main__":
    run_refinement_pipeline()