import os
import glob
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# CONFIG - Environment Variables
ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
DOC_INT_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

# CONFIG - Folder Paths (Anpassbar)
INPUT_FOLDER = os.getenv("INPUT_PDF_PATH")  # Hier liegen deine PDFs
OUTPUT_FOLDER = os.getenv("OUTPUT_MD_PATH")  # Hier landen die Markdown Files

def table_to_markdown(table) -> str:
    """
    Konvertiert ein Azure AI Table Objekt in einen Markdown String.
    """
    if not table.cells:
        return ""

    rows = table.row_count
    cols = table.column_count
    grid = [["" for _ in range(cols)] for _ in range(rows)]

    for cell in table.cells:
        # Bereinigung von Newlines innerhalb einer Zelle
        content = cell.content.replace('\n', ' ').strip()
        grid[cell.row_index][cell.column_index] = content

    markdown_lines = []
    
    # Header Row
    header_row = "| " + " | ".join(grid[0]) + " |"
    markdown_lines.append(header_row)
    
    # Separator Row
    separator = "| " + " | ".join(["---"] * cols) + " |"
    markdown_lines.append(separator)

    # Data Rows
    for row in grid[1:]:
        row_line = "| " + " | ".join(row) + " |"
        markdown_lines.append(row_line)

    return "\n".join(markdown_lines) + "\n\n"

def process_pdf_to_markdown(file_path: str, client: DocumentIntelligenceClient) -> dict:
    """
    Analysiert ein PDF und gibt strukturiertes Markdown + Metadaten zurück.
    """
    print(f"   ...sende an Azure: {os.path.basename(file_path)}")
    
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout", 
            body=f, 
            content_type="application/pdf"
        )
    
    result: AnalyzeResult = poller.result()
    print("   ...Analyse abgeschlossen. Generiere Markdown.")
    
    output_content = ""
    
    # 1. Tabellen-Bereiche mappen
    table_spans = []
    for table in result.tables:
        for span in table.spans:
            table_spans.append((span.offset, span.offset + span.length))
            
    def is_in_table(offset):
        for start, end in table_spans:
            if start <= offset < end:
                return True
        return False

    # 2. Iteration und Rekonstruktion
    current_table_idx = 0
    sorted_tables = sorted(result.tables, key=lambda t: t.spans[0].offset if t.spans else 0)
    
    for paragraph in result.paragraphs:
        # Check: Ist Paragraph Teil einer Tabelle?
        if is_in_table(paragraph.spans[0].offset):
            if current_table_idx < len(sorted_tables):
                tbl = sorted_tables[current_table_idx]
                tbl_start = tbl.spans[0].offset
                
                # Nur rendern, wenn wir am Anfang der Tabelle stehen
                if paragraph.spans[0].offset >= tbl_start:
                    md_table = table_to_markdown(tbl)
                    output_content += f"\n\n{md_table}"
                    current_table_idx += 1
            continue

        # Header Detection
        role = paragraph.role
        content = paragraph.content
        
        if role == "pageHeader" or role == "pageFooter":
            continue 
            
        if role == "title":
            output_content += f"# {content}\n\n"
        elif role == "sectionHeading":
            output_content += f"## {content}\n\n"
        else:
            output_content += f"{content}\n\n"

    return {
        "filename": os.path.basename(file_path),
        "content": output_content
    }

def run_batch_processing():
    # 1. Client initialisieren (nur einmal)
    if not ENDPOINT or not DOC_INT_KEY:
        print("FEHLER: Bitte .env Variablen setzen (ENDPOINT, KEY).")
        return

    client = DocumentIntelligenceClient(
        endpoint=ENDPOINT, 
        credential=AzureKeyCredential(DOC_INT_KEY)
    )

    # 2. Ordner checken
    if not os.path.exists(INPUT_FOLDER):
        print(f"Input Ordner '{INPUT_FOLDER}' existiert nicht. Bitte erstellen.")
        return
    
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"Output Ordner '{OUTPUT_FOLDER}' erstellt.")

    # 3. Dateien suchen
    pdf_files = glob.glob(os.path.join(INPUT_FOLDER, "*.pdf"))
    
    if not pdf_files:
        print(f"Keine PDFs in {INPUT_FOLDER} gefunden.")
        return

    print(f"--- Starte Batch Processing für {len(pdf_files)} Dateien ---")

    # 4. Loop
    for pdf_path in pdf_files:
        try:
            result = process_pdf_to_markdown(pdf_path, client)
            
            # Output Filename: original.pdf -> original.md
            md_filename = result["filename"].replace(".pdf", ".md")
            output_path = os.path.join(OUTPUT_FOLDER, md_filename)
            
            # Speichern (UTF-8 ist wichtig!)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result["content"])
                
            print(f"✅ Gespeichert: {output_path}\n")
            
        except Exception as e:
            print(f"❌ Fehler bei {pdf_path}: {e}\n")

if __name__ == "__main__":
    run_batch_processing()