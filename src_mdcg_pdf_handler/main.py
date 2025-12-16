import os
import sys
import time
import argparse
from dotenv import load_dotenv

# Lade Umgebungsvariablen einmal zentral
load_dotenv()

# Importiere die Module (Passe Funktionsnamen ggf. an deine Scripts an)
try:
    from ingest_manager import run_batch_processing as step_1_ingest
    from refine_manager import run_refinement_pipeline as step_2_refine
    from mdcg_to_json import convert_md_to_json_structure as step_3_convert
    from upload_manager import run_upload_pipeline as step_4_upload
except ImportError as e:
    print(f"❌ Critical Error: Konnte Module nicht importieren. {e}")
    sys.exit(1)

def print_header(step_name):
    print("\n" + "="*60)
    print(f"🚀 STARTING PHASE: {step_name}")
    print("="*60 + "\n")

def main():
    parser = argparse.ArgumentParser(description="MedTech Compliance Engine - Data Ingestion Pipeline")
    parser.add_argument(
        "--step",
        choices=["ingest", "refine", "convert", "upload", "all"],
        default="all",
        help="Specific pipeline step to execute. Default: all"
    )
    args = parser.parse_args()
    step = args.step

    start_time = time.time()
    
    print("🏥 MedTech Compliance Engine - Data Ingestion Pipeline")
    print("------------------------------------------------------")
    print(f"Executing: {step}")

    # --- SCHRITT 1: INGESTION (PDF -> MD) ---
    if step in ["ingest", "all"]:
        print_header("1. INGESTION (Azure ADI)")
        try:
            step_1_ingest()
        except Exception as e:
            print(f"❌ Abbruch in Phase 1: {e}")
            sys.exit(1)

    # --- SCHRITT 2: REFINEMENT (LLM Cleaning) ---
    if step in ["refine", "all"]:
        print_header("2. REFINEMENT (GPT-5 Cleaning)")
        try:
            step_2_refine()
        except Exception as e:
            print(f"❌ Abbruch in Phase 2: {e}")
            sys.exit(1)

    # --- SCHRITT 3: CONVERSION (MD -> JSON Chunks) ---
    if step in ["convert", "all"]:
        print_header("3. CONVERSION (Semantic Chunking)")
        try:
            step_3_convert()
        except Exception as e:
            print(f"❌ Abbruch in Phase 3: {e}")
            sys.exit(1)

    # --- SCHRITT 4: UPLOAD (Embeddings -> Search Index) ---
    if step in ["upload", "all"]:
        print_header("4. INDEXING (Vector Upload)")
        try:
            step_4_upload()
        except Exception as e:
            print(f"❌ Abbruch in Phase 4: {e}")
            sys.exit(1)

    # --- SUMMARY ---
    duration = time.time() - start_time
    print("\n" + "="*60)
    print(f"✅ PIPELINE SUCCESSFULLY COMPLETED in {duration:.2f} seconds.")
    print("="*60)

if __name__ == "__main__":
    main()
