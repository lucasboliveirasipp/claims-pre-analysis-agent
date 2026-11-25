import pandas as pd
import io
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from uuid import uuid4
from langgraph.graph import END, StateGraph, START
from langchain_core.prompts import PromptTemplate

# ASSUMIR que tools, prompts, config e state estão corretos
from .tools import (
    calc_time_counter,
    create_temp_files,
    extract_pages_from_pdf_di,
    get_time_counter,
)
from .prompts import pre_analysis_death_certificate_prompt
from .config import gpt_4_1_mini, llm
from .state import DeathCertificateState
from .pre_analysis_death_certificate_models import CertidaoDeObito


def extract_declarante_info(text: str) -> Tuple[str, str, str]:
    """Extrai nome, RG e CPF do declarante próximos à palavra 'Declarante'."""
    nome_declarante = "null"
    rg_declarante = "null"
    cpf_declarante = "null"
    match_declarante_block = re.search(
        r"(Declarante[\s\S]{0,200})", text, re.IGNORECASE
    )
    if match_declarante_block:
        block = match_declarante_block.group(1)
        nome_match = re.search(r"Declarante(?:\:|\s+)?([A-Z][A-Za-zÀ-ÿ\s]+)", block)
        rg_match = re.search(r"RG(?:\:|\s+)?(\d{2}\.\d{3}\.\d{3}-\d{1,2})", block)
        cpf_match = re.search(r"CPF(?:\:|\s+)?(\d{3}\.\d{3}\.\d{3}-\d{2})", block)
        if nome_match:
            nome_declarante = nome_match.group(1).strip()
        if rg_match:
            rg_declarante = rg_match.group(1)
        if cpf_match:
            cpf_declarante = cpf_match.group(1)
    return nome_declarante, rg_declarante, cpf_declarante


class PreAnalysisDeathCertificate:
    MAX_DOCS = 10

    def __init__(self, files, option: int):
        """Inicializa o processador de certidão de óbito"""
        if not isinstance(files, list):
            files = [files]
        self.files = files[: self.MAX_DOCS]
        self.option = option
        self.workflow = self._setup_pre_analysis_death_certificate_workflow()

    def _setup_pre_analysis_death_certificate_workflow(self):
        workflow = StateGraph(DeathCertificateState)
        workflow.add_node("extraction_node", self.extraction_node)
        workflow.add_node("analysis_node", self.analysis_node)
        workflow.add_node("format_node", self.format_node)
        workflow.add_edge(START, "extraction_node")
        workflow.add_edge("extraction_node", "analysis_node")
        workflow.add_edge("analysis_node", "format_node")
        workflow.add_edge("format_node", END)
        return workflow.compile()

    def process_documents(self, config):
        """
        Processa a lista de documentos (máx 3) e retorna uma lista de resultados (dicionários de estado).
        """
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
                    f"Aviso: Não encontrou arquivo temporário para {original_file_name}"
                )
                continue
            # Define o estado inicial
            initial_state = {
                "files": [file_obj],
                "temp_file": temp_file,
                "start_time": get_time_counter(),
                "documents": [],
                "extracted_data": {},
                "name": "",  # Nome do Declarante
                "rg": "",  # RG do Declarante
                "cpf": "",  # CPF do Declarante
                "reason_of_death": "",
                "date_of_death": "",
                "autentication": "",
                "result": {},
                "end_time": 0.0,
                "elapsed_time": "",
            }
            # Invoca o workflow para processar APENAS este arquivo
            result = self.workflow.invoke(initial_state, config=config)
            all_results.append(result)
        return all_results

    def extraction_node(self, state: DeathCertificateState):
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

    def analysis_node(self, state: DeathCertificateState):
        """Analisa a certidão de óbito e extrai informações estruturadas."""
        documents = state["documents"]
        all_text = ""
        for doc in documents:
            for page in doc:
                all_text += page["text"] + "\n\n"
        # Pré-extração e contexto do declarante (para auxiliar o LLM)
        nome_declarante, rg_declarante, cpf_declarante = extract_declarante_info(
            all_text
        )
        declarante_context = (
            f"\n[Bloco do Declarante]\nNome: {nome_declarante}\n"
            f"RG: {rg_declarante}\nCPF: {cpf_declarante}\n"
        )
        all_text = declarante_context + all_text
        # Chain de LLM
        death_certificate_template = PromptTemplate(
            template=pre_analysis_death_certificate_prompt, input_variables=["texto"]
        )
        structured_llm = llm.with_structured_output(CertidaoDeObito)
        death_certificate_chain = death_certificate_template | structured_llm
        certificado = death_certificate_chain.invoke({"texto": all_text})
        date_of_death_value = certificado.date_of_death or "null"
        reason_of_death_value = certificado.reason_of_death or "null"
        extracted_data_safe = {
            "Nome do Declarante": certificado.name or nome_declarante or "null",
            "RG do Declarante": certificado.rg or rg_declarante or "null",
            "CPF do Declarante": certificado.cpf or cpf_declarante or "null",
            "Causa da Morte": reason_of_death_value,
            "Data do Óbito": date_of_death_value,
            "Autenticidade": certificado.autentication or "Null",
        }
        return {
            "extracted_data": extracted_data_safe,  # Usando o dicionário seguro
            "name": certificado.name or nome_declarante or "null",
            "rg": certificado.rg or rg_declarante or "null",
            "cpf": certificado.cpf or cpf_declarante or "null",
            "reason_of_death": reason_of_death_value,
            "date_of_death": date_of_death_value,
            "autentication": certificado.autentication or "Null",
        }

    def format_node(self, state: DeathCertificateState):
        """Formata o resultado final em CSV e adiciona file_name."""
        extracted_data = state["extracted_data"]
        time_counter = calc_time_counter(state["start_time"])
        file_name_base = "Analise_Certidao_Obito"
        file_name = file_name_base

        # Lógica para obter o nome do arquivo, priorizando o temp_file
        original_name = "documento"
        temp_file = state.get("temp_file")
        if temp_file and temp_file.get("metadata", {}).get("original_name"):
            original_name = temp_file["metadata"]["original_name"]

        if original_name and original_name != "documento":
            # Remove a extensão do arquivo
            clean_name = (
                original_name.rsplit(".", 1)[0]
                if "." in original_name
                else original_name
            )
            file_name = f"{file_name_base}_{clean_name}"
        else:
            # Fallback com UUID para garantir unicidade
            unique_suffix = str(uuid4())[:8]
            file_name = f"{file_name_base}_Fallback_{unique_suffix}"
        # Cria o DataFrame
        df = pd.DataFrame([extracted_data])
        # Reindexação para garantir a ordem das colunas
        df = df.reindex(
            columns=[
                "Nome do Declarante",
                "RG do Declarante",
                "CPF do Declarante",
                "Causa da Morte",
                "Data do Óbito",
                "Autenticidade",
            ],
            fill_value="",
        )
        csv_buffer = io.StringIO()
        # Mantendo separador ';'
        df.to_csv(csv_buffer, index=False, encoding="utf-8", sep=";")
        csv_content_str = csv_buffer.getvalue()

        BOM = b"\xef\xbb\xbf"
        csv_content_bytes = BOM + csv_content_str.encode("utf-8")

        return {
            # ⬅️ AJUSTE: Passando os bytes com BOM
            "result": {"csv_file": csv_content_bytes, "file_name": file_name},
            "end_time": time_counter["end_time"],
            "elapsed_time": time_counter["elapsed_time"],
        }
