import json
import os
import time
from dotenv import load_dotenv  # Import this
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

# Load environment variables from .env file
load_dotenv()

# --- 1. CONFIGURATION ---
# Azure AI Search Config
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX")

# Azure OpenAI Config
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AOAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Safety Check: Stop if keys are missing
if not SEARCH_KEY or not AOAI_KEY:
    raise ValueError("❌ CRITICAL ERROR: API Keys not found. Did you create the .env file?")

# --- 2. INITIALIZE CLIENTS ---
print("--- CONFIGURATION CHECK ---")
print(f"OpenAI Endpoint: {AOAI_ENDPOINT}")
print(f"OpenAI Deployment: {AOAI_DEPLOYMENT}")
print(f"OpenAI Version: {AOAI_API_VERSION}")
print("---------------------------")

# Search Client
search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)

# OpenAI Client
# CRITICAL: This must use the variables defined above
openai_client = AzureOpenAI(
    azure_endpoint=AOAI_ENDPOINT,
    api_key=AOAI_KEY,
    api_version=AOAI_API_VERSION
)

# --- 3. HELPER FUNCTIONS ---
def generate_embeddings(text):
    """Generates a vector for the given text using Azure OpenAI."""
    # Safety: Truncate to ~8000 chars to avoid token limits
    safe_text = text[:8000] 
    
    # CRITICAL: This must use the AOAI_DEPLOYMENT variable
    response = openai_client.embeddings.create(
        input=safe_text,
        model=AOAI_DEPLOYMENT
    )
    return response.data[0].embedding

# --- 4. MAIN UPLOAD PROCESS ---
def main():
    print("Loading data.json...")
    try:
        # Adjust filename if your json is named differently (e.g. output/compliance_data.json)
        with open('output/compliance_data.json', 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        try:
             with open('data.json', 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except:
            print("Error: Could not find 'data.json' or 'output/compliance_data.json'.")
            return

    documents_to_upload = []
    total_docs = len(raw_data)

    print(f"Found {total_docs} documents. Starting processing...")

    for i, item in enumerate(raw_data):
        doc_id = item.get("id")
        title = item.get("title", "No Title")
        
        # VISUAL PROGRESS: Print every document to see where it hangs
        print(f"[{i+1}/{total_docs}] Processing: {doc_id}...", end=" ", flush=True)

        # 1. READ FIELDS (Handling flat structure)
        chapter = item.get("chapter", "")
        valid_from = item.get("valid_from", None) 
        source_type = item.get("source_type", "MDR")
        url = item.get("url", "")
        content_text = item.get("content", "")

        # 2. GENERATE VECTOR
        vector = []
        if content_text:
            try:
                vector = generate_embeddings(content_text)
                print("✅ Vector OK", end=" | ")
            except Exception as e:
                print(f"\n   ❌ Vector Failed: {e}")
                # We continue loop to debug other docs, or you can 'break' here
                continue 
        else:
            print("⚠️ Empty Content", end=" | ")

        # 3. BUILD DOC
        doc = {
            "id": doc_id,
            "title": title,
            "content": content_text,
            "source_type": source_type,
            "url": url,
            "chapter": chapter,          
            "valid_from": valid_from,    
            "contentVector": vector      
        }
        
        documents_to_upload.append(doc)
        print("Buffered.")

    # 4. UPLOAD
    if not documents_to_upload:
        print("No documents successfully processed.")
        return

    print(f"\nUploading {len(documents_to_upload)} documents to Azure Search...")
    
    try:
        result = search_client.upload_documents(documents=documents_to_upload)
        succeeded = sum([1 for r in result if r.succeeded])
        failed = sum([1 for r in result if not r.succeeded])
        print(f"Upload Complete! ✅ Succeeded: {succeeded}, ❌ Failed: {failed}")
    except Exception as e:
        print(f"Upload Error: {e}")

if __name__ == "__main__":
    main()