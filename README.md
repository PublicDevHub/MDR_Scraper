🏥 MedTech Compliance Audit Engine (MVP)

Status: Phase 1 Completed (Knowledge Base Ingestion)

Client: Geister MedTech

Tech Stack: Azure Native (AI Search, OpenAI, Doc Intelligence)
🎯 Vision

Dieses System automatisiert die regulatorische Überwachung und GAP-Analyse für MedTech-Hersteller. Es löst das Problem der manuellen Prüfung von internen SOPs gegen sich ständig ändernde regulatorische Anforderungen (MDR, IVDR, MDCG).

Anders als einfache "Chat with PDF"-Lösungen nutzt dieses System eine Multi-Stage Refinement Pipeline, um sicherzustellen, dass kritische regulatorische Nuancen (Fußnoten, Querverweise, Tabellen-Qualifier) nicht durch technisches Chunking verloren gehen.
🏗 Architektur der Daten-Pipeline

Der Prozess transformiert unstrukturierte PDFs (Leitlinien) in eine hochpräzise, durchsuchbare Vektor-Datenbank.
Code snippet

graph LR
    A[PDF Input] -->|Azure Doc Intelligence| B(Raw Markdown)
    B -->|GPT-5.1 Semantic Cleaning| C(Refined Markdown)
    C -->|Semantic Chunking| D(JSON Chunks)
    D -->|Text-Embedding-3-Large| E[(Azure AI Search)]

Die 4 Phasen der Pipeline

    Ingestion (ingest_manager.py)

        Nutzung des Azure AI Document Intelligence (Layout Model).

        Extraktion von visueller Struktur (Tabellen, Header, Paragraphen) anstatt reinem Text.

        Output: _raw.md Dateien.

    Refinement (refine_manager.py)

        AI-Driven Cleaning: Ein LLM (GPT-5.1/GPT-4o) liest das Dokument.

        Context Repair: Fußnoten am Seitenende werden semantisch an ihre Referenz im Text verschoben.

        Noise Reduction: Entfernung von Seitenzahlen, Kopfzeilen und Artefakten.

        Output: _cleaned.md Dateien (Human Readable).

    Conversion (mdcg_to_json.py)

        Semantic Chunking: Splitting basierend auf Markdown-Headern (#, ##), nicht willkürlichen Token-Grenzen.

        Metadata Enrichment: Hinzufügen von Hierarchie-Pfaden (Chapter > Section).

        Output: Granulare JSON-Dateien pro Dokument.

    Indexing (upload_manager.py)

        Generierung von Vektoren mittels text-embedding-3-large (3072 Dimensionen).

        Upload in den Azure AI Search Index (mdr-legal-index-v1).

        Merge von MDR (HTML-Source) und MDCG (PDF-Source) in ein einheitliches Schema.

🚀 Installation & Setup
1. Umgebungsvariablen (.env)

Erstelle eine .env Datei im Root-Verzeichnis mit folgenden Schlüsseln:
Ini, TOML

# --- AZURE SEARCH (Vektor Datenbank) ---
AZURE_SEARCH_ENDPOINT="https://DEIN-SEARCH.search.windows.net"
AZURE_SEARCH_KEY="DEIN-ADMIN-KEY"
AZURE_SEARCH_INDEX="mdr-legal-index-v1"

# --- AZURE OPENAI: EMBEDDINGS (Für Vektoren) ---
AZURE_OPENAI_EMBEDDING_ENDPOINT="https://DEIN-AI-RESSOURCE-1.openai.azure.com/"
AZURE_OPENAI_EMBEDDING_KEY="KEY-1"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-3-large"
AZURE_OPENAI_EMBEDDING_API_VERSION="2024-02-01"

# --- AZURE OPENAI: CHAT / REFINER (Für Cleaning) ---
AZURE_OPENAI_CHAT_ENDPOINT="https://DEIN-AI-RESSOURCE-2.openai.azure.com/"
AZURE_OPENAI_CHAT_KEY="KEY-2"
AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-5.1-chat"
AZURE_OPENAI_CHAT_API_VERSION="2024-12-01-preview"

# --- AZURE DOCUMENT INTELLIGENCE (OCR) ---
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://DEIN-DOC-INTEL.cognitiveservices.azure.com/"
AZURE_DOCUMENT_INTELLIGENCE_KEY="DEIN-KEY"

# --- LOKALE PFADE (Konfigurierbar) ---
INPUT_PDF_PATH="data/input"           # Hier PDFs ablegen
OUTPUT_MD_PATH="data/output"          # Zwischenspeicher Raw MD
OUTPUT_MD_PATH_REFINED="data/refined" # Zwischenspeicher Clean MD
OUTPUT_JSON_PATH="data/json"          # Ready for Upload

2. Dependencies installieren
Bash

pip install azure-search-documents azure-ai-documentintelligence openai langchain langchain-text-splitters python-dotenv pydantic tiktoken

💻 Nutzung

Um die gesamte Pipeline (vom PDF bis zum Index) auszuführen:
Bash

python main.py

Das Skript führt alle Schritte sequenziell aus und bricht bei Fehlern ab, um Dateninkonsistenzen zu vermeiden.

Einzelne Module testen:

    Nur OCR testen: python ingest_manager.py

    Nur Cleaning testen: python refine_manager.py

    Nur Upload wiederholen: python upload_manager.py

📂 Projektstruktur

.
├── main.py                 # Orchestrator Script
├── ingest_manager.py       # Phase 1: PDF zu Markdown (Azure ADI)
├── refine_manager.py       # Phase 2: Markdown Cleaning (LLM)
├── mdcg_to_json.py         # Phase 3: Markdown zu JSON Chunks
├── upload_manager.py       # Phase 4: JSON zu Azure Search
├── src/
│   ├── models.py           # Pydantic Data Models (MDRChunk)
│   └── mdr_parser.py       # Legacy: HTML Scraper für MDR Gesetzestexte
├── data/                   # Lokaler Datenspeicher (Gitignored)
│   ├── input/              # Dropzone für PDFs
│   ├── refined/            # Quality Check Zone
│   └── json/               # Upload Zone
└── .env                    # Secrets

⚠️ Disclaimer

Dieses Tool dient zur Unterstützung von Regulatory Affairs Managern. Die Ergebnisse der KI (insbesondere beim Cleaning) müssen stichprobenartig validiert werden. Es ersetzt keine Benannte Stelle (Notified Body).