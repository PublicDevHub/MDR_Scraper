Context: We are building a high-stakes B2B SaaS MVP for the MedTech industry. The goal is a RAG (Retrieval Augmented Generation) system running on Azure that helps QA managers navigate complex EU regulations. The core value proposition is precision. We cannot have hallucinations. The retrieval must happen on specific legal "Articles" and "Annexes".

Your Role: You are a Senior Python Data Engineer specializing in Azure AI Search and Unstructured Data Pipelines.

The Task: Create a Python-based ingestion pipeline (script) that scrapes, parses, and structures regulatory data into a JSON format ready for upload to an Azure AI Search Index.

Data Sources:

    EU MDR (HTML): The Consolidated Medical Device Regulation.

        Target: https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:02017R0745-20250110 (or current version).

        Challenge: This is a massive HTML file. We need to parse it not by generic token count, but by legal structure. Each "Article" (e.g., "Artikel 10") should be a distinct chunk.

    MDCG Guidelines (PDF): Guidance documents.

        Target: A folder of PDF files (assume local path ./data/mdcg/ for now).

        Challenge: Extract text cleanly. If possible, chunk by headers.

Technical Requirements:

    Language: Python 3.10+

    Libraries: beautifulsoup4 (for HTML), pypdf or pdfplumber (for PDFs), pydantic (for schema validation).

    Output: A list of JSON objects (Dictionaries).

The Target Data Schema (Crucial): Every chunk must follow this structure exactly to maximize retrieval quality in Azure:
JSON

{
  "id": "mdr_art_10",           // Unique ID (e.g., source_article_number)
  "source_type": "MDR",         // "MDR" or "MDCG"
  "title": "Artikel 10",        // The Heading
  "content": "...",             // The full text of the article
  "url": "...",                 // Source URL
  "metadata": {
      "chapter": "Kapitel 2",
      "valid_from": "2025-01-10"
  }
}

Execution Steps for you:

    Setup: Initialize a Python project with a virtual env and requirements.txt.

    MDR Parser: Write a function that fetches the HTML. Use BeautifulSoup to identify the specific HTML hierarchy of EUR-Lex (look for tags creating the "Article" structure). Extract the Article Title and the Article Body.

        Strategic Note: Do NOT split an Article into multiple chunks unless it exceeds 8000 tokens. Keep the context intact.

    MDCG Parser: Write a function to iterate through a local folder of PDFs and extract text.

    Main Loop: orchestrate the scraping and save the result to output/compliance_data.json.

Constraints:

    Write clean, modular code (separate scraper.py, parser.py, models.py).

    Include error handling (if the URL changes or PDF is corrupt).

    Do NOT build a UI. This is a backend data pipeline.

Testing Strategy:

    All code must be accompanied by unit tests.

    Use `pytest` as the testing framework.

    Create a `tests/` directory and ensure tests cover:
        - Parsing logic (identifying articles, extracting fields).
        - Schema validation (ensuring output matches the Pydantic model).
        - Error handling.

    Mock external requests (e.g., HTML fetching) to ensure tests are deterministic and fast.

GO! Start by analyzing the project structure and writing the models.py with Pydantic to enforce the schema.