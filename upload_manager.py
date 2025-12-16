import os
import glob
import json
import time
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

load_dotenv()

# --- CONFIGURATION ---
# Pfad aus deiner neuen .env (oder hardcoded Fallback)
INPUT_FOLDER = os.getenv("OUTPUT_JSON_PATH", "U:/mdr_json")

# Azure Search Config
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "mdr-legal-index-v1")

# --- WICHTIG: Hier laden wir jetzt die SPEZIFISCHEN Embedding-Credentials ---
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_EMBEDDING_KEY")
AOAI_VERSION = os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION", "2024-02-01")
EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

def get_embedding(client: AzureOpenAI, text: str) -> list:
    if not text or not isinstance(text, str):
        return None
    
    clean_text = text.replace("\n", " ")
    safe_text = clean_text[:8000]

    try:
        response = client.embeddings.create(
            input=safe_text,
            model=EMBEDDING_DEPLOYMENT
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"   ❌ Embedding Error: {e}")
        return None

def run_upload_pipeline():
    # Check ob wir wirklich die richtigen Keys haben
    if not AOAI_ENDPOINT or not EMBEDDING_DEPLOYMENT:
        print("❌ Error: Embedding Credentials fehlen in .env")
        print(f"   Endpoint: {AOAI_ENDPOINT}")
        print(f"   Deployment: {EMBEDDING_DEPLOYMENT}")
        return

    print(f"🔌 Verbinde mit Azure Search Index: '{INDEX_NAME}'")
    print(f"🔌 Nutze Embedding Ressource: '{AOAI_ENDPOINT}' -> '{EMBEDDING_DEPLOYMENT}'")
    
    # Client Setup
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )

    aoai_client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version=AOAI_VERSION
    )

    # File Handling
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ Input Ordner '{INPUT_FOLDER}' existiert nicht.")
        return

    json_files = glob.glob(os.path.join(INPUT_FOLDER, "*.json"))
    if not json_files:
        print(f"⚠️ Keine JSON-Dateien in '{INPUT_FOLDER}' gefunden.")
        return

    print(f"🚀 Starte Upload für {len(json_files)} Dateien...")
    
    total_uploaded = 0
    batch = []
    BATCH_SIZE = 50 

    for file_path in json_files:
        filename = os.path.basename(file_path)
        print(f"\n📄 Lade Datei: {filename}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            
            print(f"   ...verarbeite {len(chunks)} Chunks.")

            for chunk in chunks:
                if not chunk.get("contentVector"):
                    vector = get_embedding(aoai_client, chunk["content"])
                    if vector:
                        chunk["contentVector"] = vector
                    else:
                        continue
                
                if not chunk.get("valid_from"):
                    chunk["valid_from"] = "2024-01-01T00:00:00Z"

                batch.append(chunk)

                if len(batch) >= BATCH_SIZE:
                    try:
                        search_client.upload_documents(documents=batch)
                        total_uploaded += len(batch)
                        print(f"   ⬆️ Batch von {len(batch)} hochgeladen.")
                        batch = [] 
                        time.sleep(0.5) 
                    except Exception as e:
                        print(f"   ❌ Fehler beim Upload Batch: {e}")

        except Exception as e:
            print(f"❌ Fehler bei Datei {filename}: {e}")

    if batch:
        try:
            search_client.upload_documents(documents=batch)
            total_uploaded += len(batch)
            print(f"   ⬆️ Finaler Batch hochgeladen.")
        except Exception as e:
            print(f"   ❌ Fehler beim finalen Upload: {e}")

    print(f"\n✅ Pipeline beendet. {total_uploaded} Dokumente indexiert.")

if __name__ == "__main__":
    run_upload_pipeline()