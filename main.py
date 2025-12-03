import json
import logging
import os
from src.mdr_parser import fetch_html, parse_mdr
from src.create_index_definition import get_index_schema

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MDR_URL = "https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:02017R0745-20250110"
OUTPUT_FILE = "output/compliance_data.json"
INDEX_DEF_FILE = "output/azure_index_definition.json"

def main():
    logger.info("Starting MDR Scraper Pipeline...")

    # 1. Fetch HTML
    logger.info(f"Fetching MDR HTML from {MDR_URL}...")
    try:
        html_content = fetch_html(MDR_URL)
        logger.info(f"Successfully fetched {len(html_content)} characters.")
    except Exception as e:
        logger.error(f"Failed to fetch HTML: {e}")
        return

    # 2. Parse HTML
    logger.info("Parsing HTML content...")
    chunks = parse_mdr(html_content, MDR_URL)
    logger.info(f"Parsed {len(chunks)} chunks (Articles/Annexes).")

    # 3. Save to JSON
    logger.info(f"Saving data to {OUTPUT_FILE}...")
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    data = [chunk.model_dump() for chunk in chunks]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # 4. Save Index Definition
    logger.info(f"Saving Azure Index Definition to {INDEX_DEF_FILE}...")
    index_schema = get_index_schema()
    with open(INDEX_DEF_FILE, "w", encoding="utf-8") as f:
        json.dump(index_schema, f, indent=2, ensure_ascii=False)

    logger.info("Pipeline completed successfully.")

if __name__ == "__main__":
    main()
