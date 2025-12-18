import streamlit as st
import os
import time
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI
import docx

# Lade deine bestehende Logik (Kopiere die Funktionen aus sop_audit_pipeline.py hier rein oder importiere sie)
# Der Einfachheit halber: Wir importieren die Module und nutzen die Logik direkt.
# WICHTIG: Stelle sicher, dass sop_audit_pipeline.py im selben Ordner liegt und 'docx_to_raw_markdown', 'refine_to_claims' etc. exportiert.
from sop_audit_pipeline import docx_to_raw_markdown, refine_to_claims, get_embedding

load_dotenv()

# Config laden
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

# Clients
chat_client = AzureOpenAI(azure_endpoint=CHAT_ENDPOINT, api_key=CHAT_KEY, api_version=CHAT_VERSION)
emb_client = AzureOpenAI(azure_endpoint=EMBEDDING_ENDPOINT, api_key=EMBEDDING_KEY, api_version="2024-02-01")
search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY))

# --- UI ---
st.set_page_config(page_title="MedTech Compliance Auditor", layout="wide")

st.title("🏥 AI Compliance Auditor (MVP)")
st.markdown("Automatischer Abgleich von SOPs gegen MDR/IVDR & MDCG Guidelines.")

uploaded_file = st.file_uploader("Lade eine SOP (Word .docx) hoch", type="docx")

if uploaded_file:
    st.info("Datei wird verarbeitet...")
    
    # 1. READ
    # Wir müssen das File temporär speichern für python-docx
    with open("temp.docx", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    raw_md = docx_to_raw_markdown("temp.docx")
    
    with st.expander("Schritt 1: Rohdaten anzeigen (Debug)"):
        st.text(raw_md[:2000] + "...")

    # 2. REFINE
    if st.button("Audit starten"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🤖 KI extrahiert Claims...")
        claims_md = refine_to_claims(chat_client, raw_md)
        
        claims = claims_md.split("### Claim:")
        claims = [c.strip() for c in claims if c.strip()]
        
        st.success(f"{len(claims)} prüfbare Claims identifiziert.")
        
        # 3. AUDIT LOOP
        results_container = st.container()
        
        for i, claim_text in enumerate(claims):
            progress = (i + 1) / len(claims)
            progress_bar.progress(progress)
            
            lines = claim_text.split("\n", 1)
            title = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else title
            
            status_text.text(f"Prüfe Claim {i+1}: {title}...")
            
            # Search & Compare Logic (Kurzform)
            try:
                query_vec = get_embedding(emb_client, content)
                vector_query = VectorizedQuery(vector=query_vec, k_nearest_neighbors=3, fields="contentVector")
                results = search_client.search(search_text=content, vector_queries=[vector_query], top=3)
                
                references = [f"**{r['source_type']} - {r['title']}**\n>{r['content'][:300]}..." for r in results]
                context_str = "\n\n".join(references)
                
                if not references:
                    with results_container:
                        st.warning(f"**{title}**: Keine Regulatorik gefunden.")
                    continue

                # Audit Prompt
                audit_prompt = f"""
                Du bist ein strenger MDR Auditor.
                SOP: "{content}"
                FAKTEN: {context_str}
                AUFGABE: Status (KONFORM/WARNUNG/KRITISCH), Begründung (Deutsch), Zitat.
                """
                response = chat_client.chat.completions.create(
                    model=CHAT_DEPLOYMENT, messages=[{"role":"user", "content":audit_prompt}]
                )
                decision = response.choices[0].message.content
                
                # Display Result
                with results_container:
                    with st.expander(f"{title}", expanded=True):
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.markdown("**SOP Aussage:**")
                            st.info(content)
                        with col2:
                            st.markdown("**Audit Ergebnis:**")
                            if "KONFORM" in decision:
                                st.success(decision)
                            elif "KRITISCH" in decision:
                                st.error(decision)
                            else:
                                st.warning(decision)
                        
                        st.caption("Quellen:")
                        for ref in references:
                            st.markdown(ref)

            except Exception as e:
                st.error(f"Fehler bei {title}: {e}")
                
        status_text.text("✅ Audit abgeschlossen.")