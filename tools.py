import io
import time
import tempfile
import PyPDF2
from typing import List, Union
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from xhtml2pdf import pisa
from .config import document_intelligence_client


def create_temp_files(files: Union[List, object]):
    # Garantir que o argumento seja tratado como uma lista, mesmo se for um único arquivo
    if not isinstance(files, list):
        files = [files]

    temp_files = []
    for file in files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file.read())
            temp_files.append(
                {
                    "file": temp_file,
                    "metadata": {
                        "original_name": file.name,
                        "type": "pdf",
                        "temp_name": temp_file.name,
                    },
                }
            )
    return temp_files


def has_text(pdf_file):
    with open(pdf_file, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                return True
        return False


def extract_pages_from_pdf(pdf_file, original_name):
    pages = []
    with open(pdf_file, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                pages.append(
                    {
                        "text": text,
                        "metadata": {
                            "document_name": original_name,
                            "page_number": i + 1,
                            "document_type": "pdf",
                        },
                    }
                )
    return pages


def extract_pages_from_pdf_di(pdf_file, original_name):
    pages = []
    with open(pdf_file, "rb") as file:
        poller = document_intelligence_client.begin_analyze_document(
            "prebuilt-layout", AnalyzeDocumentRequest(bytes_source=file.read())
        )

        result: AnalyzeResult = poller.result()

        for i, page in enumerate(result.pages):
            extracted_text = []
            for _, line in enumerate(page.lines):
                extracted_text.append(line.content)

            pages.append(
                {
                    "text": "\n".join(extracted_text),
                    "metadata": {
                        "document_name": original_name,
                        "page_number": i + 1,
                        "document_type": "pdf",
                    },
                }
            )
    return pages


def criar_pdf_html(lista_paginas_html):
    book = []
    for p in lista_paginas_html:
        book.append(p["text"] + "<div style='page-break-after:always'></div>")

    pdf_buffer = io.BytesIO()

    pisa_status = pisa.CreatePDF(src="\n".join(book), dest=pdf_buffer)

    if pisa_status.err:
        return None

    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def get_time_counter():
    return time.perf_counter()


def calc_time_counter(start_time: float):
    processing_time = {}
    processing_time["start_time"] = start_time
    processing_time["end_time"] = get_time_counter()
    total_time = processing_time["end_time"] - processing_time["start_time"]
    processing_time["elapsed_time"] = f"{total_time:.2f} segundos"
    return processing_time
