import os
import time
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticSearch,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField
)

# Load environment variables
load_dotenv()

# --- CONFIG ---
ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "mdr-legal-index-v1")

def recreate_index():
    if not ENDPOINT or not KEY:
        print("❌ Error: .env Variablen fehlen (ENDPOINT/KEY).")
        return

    print(f"⚠️  ACHTUNG: Du bist dabei, den Index '{INDEX_NAME}' KOMPLETT zu löschen.")
    confirm = input("   Bist du sicher? (y/n): ")
    if confirm.lower() != 'y':
        print("   Abbruch.")
        return

    # Client für Index-Management (nicht für Data-Upload!)
    credential = AzureKeyCredential(KEY)
    client = SearchIndexClient(endpoint=ENDPOINT, credential=credential)

    # 1. LÖSCHEN (Falls existent)
    print(f"🔨 Lösche Index '{INDEX_NAME}'...")
    try:
        client.delete_index(INDEX_NAME)
        print("   ✅ Index gelöscht.")
    except Exception as e:
        print(f"   ℹ️ Index existierte wohl noch nicht oder Fehler: {e}")

    # Kurze Pause, damit Azure aufräumen kann
    time.sleep(2)

    # 2. DEFINITION (Schema)
    # Das ist dein Schema aus den vorherigen Schritten
    print("🏗  Erstelle Index-Schema neu...")
    
    # Vector Search Config (HNSW)
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-config",
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="my-vector-profile",
                algorithm_configuration_name="hnsw-config"
            )
        ]
    )

    # Semantic Search Config (Optional, aber gut für Hybrid Search)
    semantic_config = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="my-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="chapter")]
                )
            )
        ]
    )

    # Felder Definition
    fields = [
        # ID & Core Data
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String, analyzer_name="de.microsoft"),
        SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="de.microsoft"),
        
        # Metadaten (Filterbar/Facetierbar)
        SimpleField(name="source_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="url", type=SearchFieldDataType.String), # URL muss nicht suchbar sein, nur abrufbar
        SearchableField(name="chapter", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="valid_from", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),

        # Der Vektor (Wichtig: 3072 Dimensionen für text-embedding-3-large!)
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072, 
            vector_search_profile_name="my-vector-profile"
        )
    ]

    # Index Objekt zusammenbauen
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_config
    )

    # 3. ERSTELLEN
    try:
        client.create_index(index)
        print(f"✅ Index '{INDEX_NAME}' erfolgreich leer neu angelegt.")
        print("   Du kannst jetzt 'upload_manager.py' starten.")
    except Exception as e:
        print(f"❌ Fehler beim Erstellen: {e}")

if __name__ == "__main__":
    recreate_index()