import json
import os
import time
from dotenv import load_dotenv  # Import this
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

# Load environment variables from .env file
load_dotenv()


# Azure OpenAI Config
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
KEY = os.getenv("AZURE_OPENAI_KEY")
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

client = AzureOpenAI(
    azure_endpoint=ENDPOINT,
    api_key=KEY,
    api_version=VERSION
)

print(f"Testing connection to: {ENDPOINT}")
print(f"Model Deployment: {DEPLOYMENT}")
print(f"API Version: {VERSION}")

try:
    response = client.embeddings.create(
        input="Test sentence for embedding",
        model=DEPLOYMENT
    )
    print("\n✅ SUCCESS! Vector generated.")
    print(f"Vector length: {len(response.data[0].embedding)}")
except Exception as e:
    print("\n❌ ERROR:")
    print(e)