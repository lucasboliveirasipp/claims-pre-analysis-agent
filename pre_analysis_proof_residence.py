import pandas as pd
import io
import json
import re
from typing import List, Dict, Any
from datetime import datetime
from uuid import uuid4  # ⬅️ ADICIONADO: Import para ID único
from langgraph.graph import END, StateGraph, START
from langchain_core.prompts import PromptTemplate
from .tools import (
    calc_time_counter,
    create_temp_files,
    extract_pages_from_pdf_di,
    get_time_counter,
)
from .prompts import pre_analysis_proof_residence_prompt
from .config import gpt_4_1_mini, llm
from .state import ProofResidenceState
from .pre_analysis_proof_residence_models import ComprovanteResidencia


def clean_text(all_text: str) -> str:
    """Normaliza texto do PDF para melhorar extração"""

    text = re.sub(r"\s+", " ", all_text)
    text = (
        text.replace("N0ME", "NOME")
        .replace("CP F", "CPF")
        .replace("ClIENTE", "CLIENTE")
    )

    text = re.sub(r"\*{3}\.\*{3}\.\*{3}-\*{2}", "null", text)
    text = re.sub(r"\d{3}\.\*{3}\.\*{3}-\*{2}", "null", text)
    cpfs = re.findall(r"\b\d{11}\b", text)

    for cpf in cpfs:
        text = text.replace(cpf, f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}")
    return text


class PreAnalysisProofResidence:
    MAX_DOCS = 10

    def __init__(self, files, option: int):
        """Inicializa o processador do comprovante de residência"""
        if not isinstance(files, list):
            files = [files]
        self.files = files[: self.MAX_DOCS]
        self.option = option
        self.workflow = self._setup_pre_analysis_proof_residence_workflow()

    def _setup_pre_analysis_proof_residence_workflow(self):
        """Configura o fluxo específico para um ÚNICO comprovante de residência"""
        workflow = StateGraph(ProofResidenceState)
        workflow.add_node("extraction_node", self.extraction_node)
        workflow.add_node("analysis_node", self.analysis_node)
        workflow.add_node("format_node", self.format_node)
        workflow.add_edge(START, "extraction_node")
        workflow.add_edge("extraction_node", "analysis_node")
        workflow.add_edge("analysis_node", "format_node")
        workflow.add_edge("format_node", END)

        return workflow.compile()

    def process_documents(self, config):
        """Processa a lista de documentos e retorna uma lista de resultados."""
        all_results = []
        temp_files_data = create_temp_files(self.files)
        for i, file_obj in enumerate(self.files):
            original_file_name = getattr(file_obj, "name", f"documento_{i}.pdf")
            temp_file = next(
                (
                    f
                    for f in temp_files_data
                    if f["metadata"]["original_name"] == original_file_name
                ),
                None,
            )

            if not temp_file:
                print(
                    f"Aviso: Não encontrou arquivo temporário para {original_file_name}. Pulando."
                )
                continue

            result = self.workflow.invoke(
                {
                    "files": [file_obj],
                    "temp_file": temp_file,
                    "start_time": get_time_counter(),
                    "documents": [],
                    "name": "null",
                    "cpf": "null",
                    "emission_date": "null",
                    "autentication": "null",
                },
                config=config,
            )
            all_results.append(result)
        return all_results

    def extraction_node(self, state: ProofResidenceState):
        """Extrai texto de UM documento usando Document Intelligence"""
        temp_file = state.get("temp_file")

        if not temp_file:
            raise ValueError(
                "Caminho do arquivo temporário não fornecido para extração."
            )

        document_pages = extract_pages_from_pdf_di(
            temp_file["metadata"]["temp_name"], temp_file["metadata"]["original_name"]
        )

        return {"documents": [document_pages]}

    def analysis_node(self, state: ProofResidenceState):
        """Analisa o comprovante de residência e extrai informações estruturadas."""
        documents = state["documents"]
        all_text = ""
        for doc in documents:
            for page in doc:
                all_text += page["text"] + "\n\n"

        all_text = clean_text(all_text)
        cpf_match = re.search(
            r"(?i)CPF[:\s]*((?:\d{3}|\*{3})\.(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})-(?:\d{2}|\*{2}))",
            all_text,
        )
        cpf_detected = cpf_match.group(1) if cpf_match else None

        proof_residence_template = PromptTemplate(
            template=pre_analysis_proof_residence_prompt
            + ("\n\nCPF já identificado previamente: {cpf}" if cpf_detected else ""),
            input_variables=["texto"] + (["cpf"] if cpf_detected else []),
        )

        structured_llm = llm.with_structured_output(ComprovanteResidencia)
        proof_residence_chain = proof_residence_template | structured_llm
        inputs = {"texto": all_text}

        if cpf_detected:
            inputs["cpf"] = cpf_detected
        declaracao = proof_residence_chain.invoke(inputs)
        name = declaracao.name or "null"
        cpf = declaracao.cpf or cpf_detected or "null"
        emission_date = declaracao.emission_date or "null"
        autentication = "null"

        if emission_date != "null":
            try:
                emission_dt = datetime.strptime(emission_date, "%d/%m/%Y")
                days_diff = (datetime.today() - emission_dt).days
                autentication = "Autenticado" if days_diff < 180 else "Não Autenticado"

            except Exception:
                autentication = "null"

        csv_data_safe = {
            "Nome do Indivíduo": name,
            "CPF do Indivíduo": cpf,
            "Data de Emissão": emission_date,
            "Autenticação do Documento (até 180 dias)": autentication,
        }

        return {
            "extracted_data": csv_data_safe,  # Usando o dicionário seguro para o DataFrame
            "name": name,
            "cpf": cpf,
            "emission_date": emission_date,
            "autentication": autentication,
        }

    def format_node(self, state: ProofResidenceState):
        """Formata o resultado final em CSV e adiciona file_name único, garantindo o encoding UTF-8 com BOM."""
        extracted_data = state["extracted_data"]
        time_counter = calc_time_counter(state["start_time"])
        file_name_base = "Analise_Comprovante_Residencia"
        file_name = file_name_base
        original_name = "documento"
        temp_file = state.get("temp_file")

        if temp_file and temp_file.get("metadata", {}).get("original_name"):
            original_name = temp_file["metadata"]["original_name"]

        if original_name and original_name != "documento":

            clean_name = (
                original_name.rsplit(".", 1)[0]
                if "." in original_name
                else original_name
            )

            file_name = f"{file_name_base}_{clean_name}"

        else:
            unique_suffix = str(uuid4())[:8]
            file_name = f"{file_name_base}_Fallback_{unique_suffix}"

        df = pd.DataFrame([extracted_data])
        column_order = [
            "Nome do Indivíduo",
            "CPF do Indivíduo",
            "Data de Emissão",
            "Autenticação do Documento (até 180 dias)",
        ]

        df = df.reindex(columns=column_order, fill_value="")
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8", sep=";")
        csv_content_str = csv_buffer.getvalue()

        BOM = b"\xef\xbb\xbf"
        csv_content_bytes = BOM + csv_content_str.encode("utf-8")

        return {
            "result": {
                "csv_file": csv_content_bytes,
                "file_name": file_name,
            },
            "name": state.get("name", "null"),
            "cpf": state.get("cpf", "null"),
            "end_time": time_counter["end_time"],
            "elapsed_time": time_counter["elapsed_time"],
        }
