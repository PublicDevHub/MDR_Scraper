import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# Lade Umgebungsvariablen
load_dotenv()

# --- CONFIG ---
# Search
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX")

# Embedding (Resource 1)
EMBEDDING_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT")
EMBEDDING_KEY = os.getenv("AZURE_OPENAI_EMBEDDING_KEY")
EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") # text-embedding-3-large
EMBEDDING_API_VERSION = os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION")

# Chat / Logic (Resource 2)
CHAT_ENDPOINT = os.getenv("AZURE_OPENAI_CHAT_ENDPOINT")
CHAT_KEY = os.getenv("AZURE_OPENAI_CHAT_KEY")
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT") # gpt-5.1-chat
CHAT_API_VERSION = os.getenv("AZURE_OPENAI_CHAT_API_VERSION")

# --- SIMULIERTER USER INPUT (GEISTER SOP) ---
# Ein klassischer Fehler: Behauptung, Klasse I braucht keinen PMS Plan.
SOP_CHUNK_TEXT = """
Für unsere Klasse I Produkte (wiederverwendbare chirurgische Instrumente) erstellen wir 
keinen separaten Plan für die Überwachung nach dem Inverkehrbringen (PMS-Plan), 
da das Risiko vernachlässigbar ist. Wir reagieren nur auf Reklamationen.
"""

def main():
    print("🔬 Starte Comparator Test-Run...")
    print(f"📄 SOP Claim: '{SOP_CHUNK_TEXT.strip()}'\n")

    # 1. CLIENTS INIT
    if not SEARCH_KEY or not EMBEDDING_KEY or not CHAT_KEY:
        print("❌ Error: API Keys fehlen in .env")
        return

    emb_client = AzureOpenAI(
        azure_endpoint=EMBEDDING_ENDPOINT,
        api_key=EMBEDDING_KEY,
        api_version=EMBEDDING_API_VERSION
    )

    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )

    chat_client = AzureOpenAI(
        azure_endpoint=CHAT_ENDPOINT,
        api_key=CHAT_KEY,
        api_version=CHAT_API_VERSION
    )

    # 2. EMBEDDING GENERIEREN (Resource 1)
    print("1️⃣ Generiere Embedding für SOP Chunk...")
    try:
        emb_resp = emb_client.embeddings.create(
            input=SOP_CHUNK_TEXT,
            model=EMBEDDING_DEPLOYMENT
        )
        query_vector = emb_resp.data[0].embedding
        print(f"   ✅ Vektor generiert ({len(query_vector)} Dimensionen).")
    except Exception as e:
        print(f"   ❌ Embedding Fehler: {e}")
        return

    # 3. AZURE AI SEARCH (Vector Search)
    print("2️⃣ Suche im 'mdr-legal-index-v1' nach Regulationen...")
    
    vector_query = VectorizedQuery(
        vector=query_vector, 
        k_nearest_neighbors=3, 
        fields="contentVector"
    )

    results = search_client.search(
        search_text=SOP_CHUNK_TEXT, # Hybrid Search (Keyword + Vector)
        vector_queries=[vector_query],
        select=["title", "content", "source_type", "chapter", "id"],
        top=3
    )

    retrieved_context = []
    print("\n--- GEFUNDENE REGULARIEN ---")
    for res in results:
        score = res["@search.score"]
        title = res['title']
        source = res['source_type']
        content_snippet = res['content'][:200].replace("\n", " ") + "..."
        
        print(f"   🔹 [{score:.4f}] {source}: {title}")
        print(f"      Context: {content_snippet}\n")
        
        retrieved_context.append(f"SOURCE: {source} ({title})\nTEXT: {res['content']}")

    if not retrieved_context:
        print("⚠️ Keine Treffer gefunden. Index leer oder Embedding falsch?")
        return

    # 4. SIMPLE GAP ANALYSIS (Resource 2)
    print("3️⃣ KI-Analyse: SOP vs. Regulation (Comparator Logic)...")
    
    context_block = "\n\n".join(retrieved_context)
    
    prompt = f"""
    Du bist ein strenger MedTech Auditor.
    
    USER SOP BEHAUPTUNG:
    "{SOP_CHUNK_TEXT}"
    
    GEFUNDENE REGULATORIK (FACTS):
    {context_block}
    
    AUFGABE:
    Prüfe die SOP-Behauptung gegen die Fakten. Ist sie compliant?
    Antworte kurz und knackig: 
    1. Konformitäts-Status (JA/NEIN)
    2. Begründung unter Zitierung der Quelle.
    """

    try:
        response = chat_client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}]
        )
        print("\n--- 🤖 AUDITOR ERGEBNIS ---")
        print(response.choices[0].message.content)
        print("---------------------------")
    except Exception as e:
        print(f"   ❌ Chat Fehler: {e}")

if __name__ == "__main__":
    main()