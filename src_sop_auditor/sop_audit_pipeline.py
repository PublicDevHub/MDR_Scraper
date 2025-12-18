import os
import docx
import time
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

load_dotenv()

# --- CONFIG ---
SOP_PATH = r"d:\sop\sop_test.docx"

# Azure Configs
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "mdr-legal-index-v1")

EMBEDDING_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT")
EMBEDDING_KEY = os.getenv("AZURE_OPENAI_EMBEDDING_KEY")
EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

CHAT_ENDPOINT = os.getenv("AZURE_OPENAI_CHAT_ENDPOINT")
CHAT_KEY = os.getenv("AZURE_OPENAI_CHAT_KEY")
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
CHAT_VERSION = os.getenv("AZURE_OPENAI_CHAT_API_VERSION")

# --- STEP 1: WORD TO RAW MARKDOWN ---
def docx_to_raw_markdown(docx_path):
    print(f"📖 Schritt 1: Lese DOCX '{os.path.basename(docx_path)}'...")
    doc = docx.Document(docx_path)
    md_lines = []
    
    for element in doc.element.body:
        if element.tag.endswith('p'): 
            para = docx.text.paragraph.Paragraph(element, doc)
            if para.text.strip():
                md_lines.append(para.text)
        elif element.tag.endswith('tbl'):
            table = docx.table.Table(element, doc)
            md_lines.append("\n--- TABELLE START ---")
            for row in table.rows:
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                md_lines.append("| " + " | ".join(cells) + " |")
            md_lines.append("--- TABELLE ENDE ---\n")
            
    return "\n\n".join(md_lines)

# --- STEP 2: RAW MD TO CLAIMS ---
def refine_to_claims(client, raw_text):
    print("🧠 Schritt 2: Extrahiere prüfbare Claims (KI)...")
    
    # PROMPT UPDATE: Deutsch & Präzise
    system_prompt = """
    Du bist ein Senior Quality Manager in der Medizintechnik.
    Deine Aufgabe ist es, "Prüfbare Aussagen" (Claims) aus einer rohen SOP zu extrahieren.

    INPUT: Roher Text aus einer DOCX (enthält "Rauschen" wie Versionstabellen, Unterschriften, Verteiler).
    OUTPUT: Eine saubere Markdown-Liste relevanter Prozessdefinitionen.

    REGELN:
    1. IGNORIERE: Historie, Unterschriftenblöcke, Inhaltsverzeichnisse, reine Header.
    2. EXTRAHIERE: Konkrete Anweisungen, Definitionen, Frequenzen (z.B. "Bericht erscheint jährlich").
    3. FORMAT:
       ### Claim: [Kurzer Titel]
       [Der vollständige Text der Anweisung aus der SOP]
    
    Antworte ausschließlich auf DEUTSCH.
    """

    try:
        response = client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"RAW SOP CONTENT:\n{raw_text[:30000]}"}
            ],
            timeout=60
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Fehler bei Step 2 (Refinement): {e}")
        return ""

# --- STEP 3: AUDIT LOOP ---
def get_embedding(client, text):
    response = client.embeddings.create(
        input=text, 
        model=EMBEDDING_DEPLOYMENT,
        timeout=10 
    )
    return response.data[0].embedding

def audit_claims(claims_md, search_client, emb_client, chat_client):
    print("⚖️ Schritt 3: Prüfe Claims gegen Azure Index...")
    
    claims = claims_md.split("### Claim:")
    audit_results = []
    
    claims = [c.strip() for c in claims if c.strip()]

    print(f"   {len(claims)} Claims gefunden.")
    
    partial_report_path = SOP_PATH.replace(".docx", "_PARTIAL_REPORT.md")
    with open(partial_report_path, "w", encoding="utf-8") as f:
        f.write("# PARTIAL AUDIT LOG\n\n")

    for i, claim_text in enumerate(claims):
        try:
            lines = claim_text.split("\n", 1)
            title = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else title
            
            print(f"\n   [{i+1}/{len(claims)}] Prüfe: '{title}'...", end=" ", flush=True)

            # A. Vector Search
            try:
                query_vec = get_embedding(emb_client, content)
            except Exception as e:
                print(f"❌ Emb Error: {e}")
                audit_results.append(f"## {title}\n**Status:** ⚪ ÜBERSPRUNGEN (Embedding Fehler)")
                continue

            vector_query = VectorizedQuery(vector=query_vec, k_nearest_neighbors=3, fields="contentVector")
            results = search_client.search(
                search_text=content,
                vector_queries=[vector_query],
                select=["title", "content", "source_type", "chapter"],
                top=3
            )

            references = []
            for res in results:
                # Wir bereiten den Kontext vor, damit das LLM ihn zitieren kann
                references.append(f"QUELLE: {res['source_type']} | {res['title']}\nTEXTAUSZUG: {res['content']}")

            if not references:
                print("⚠️ Kein Kontext", end="")
                audit_results.append(f"## {title}\n**Status:** ⚪ ÜBERSPRUNGEN (Keine Regulatorik gefunden)")
                continue

            context_str = "\n\n".join(references)

            # B. Comparator (LLM) - PROMPT UPDATE: Deutsch, Zitate, Strenge
            audit_prompt = f"""
            Du bist ein strenger MDR/IVDR Auditor für Medizintechnik.
            
            SOP AUSSAGE DES HERSTELLERS:
            "{content}"
            
            REGULATORISCHE FAKTEN (Aus der Datenbank):
            {context_str}
            
            AUFGABE:
            Prüfe die SOP-Aussage auf Konformität mit den Fakten.
            
            FORMAT VORGABE (Strikt einhalten):
            **Status:** [✅ KONFORM | ⚠️ WARNUNG | ❌ KRITISCH]
            **Begründung:** [Deine Analyse auf Deutsch. Warum ist es konform oder nicht?]
            **Zitat / Referenz:** [Nenne Artikel/Guideline UND kopiere den relevanten Satz wörtlich aus den "REGULATORISCHE FAKTEN". Wenn der Text dort steht, zitiere ihn!]
            """

            response = chat_client.chat.completions.create(
                model=CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": audit_prompt}],
                timeout=45
            )
            
            decision = response.choices[0].message.content
            
            # OUTPUT FORMAT UPDATE: Kein Slicing mehr beim Content!
            entry = f"## Claim: {title}\n\n**SOP Text:**\n> {content}\n\n{decision}\n"
            
            audit_results.append(entry)
            print("✅ Fertig", end="")

            with open(partial_report_path, "a", encoding="utf-8") as f:
                f.write(entry + "\n---\n")

            time.sleep(2)

        except Exception as e:
            print(f"\n   ❌ CRITICAL ERROR on Claim {i+1}: {e}")
            audit_results.append(f"## {title}\n**Status:** 💥 ERROR ({str(e)})")
            time.sleep(5) 

    return "\n---\n".join(audit_results)

# --- ORCHESTRATOR ---
def main():
    chat_client = AzureOpenAI(azure_endpoint=CHAT_ENDPOINT, api_key=CHAT_KEY, api_version=CHAT_VERSION)
    emb_client = AzureOpenAI(azure_endpoint=EMBEDDING_ENDPOINT, api_key=EMBEDDING_KEY, api_version="2024-02-01")
    search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY))

    if not os.path.exists(SOP_PATH):
        print(f"❌ SOP File not found: {SOP_PATH}")
        return
        
    raw_md = docx_to_raw_markdown(SOP_PATH)
    
    claims_md = refine_to_claims(chat_client, raw_md)
    
    # Debug Save
    claims_path = SOP_PATH.replace(".docx", "_CLAIMS.md")
    with open(claims_path, "w", encoding="utf-8") as f:
        f.write(claims_md)
    print(f"✅ Claims extrahiert nach: {claims_path}")

    final_report = audit_claims(claims_md, search_client, emb_client, chat_client)
    
    report_path = SOP_PATH.replace(".docx", "_AUDIT_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Audit Report: {os.path.basename(SOP_PATH)}\n\n{final_report}")
    
    print(f"\n🎉 DONE. Finaler Report: {report_path}")

if __name__ == "__main__":
    main()