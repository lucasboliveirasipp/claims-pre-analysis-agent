import pandas as pd
import io
import json
from typing import List, Dict, Any
from uuid import uuid4
from langgraph.graph import END, StateGraph, START
from langchain_core.prompts import PromptTemplate
from .tools import (
    calc_time_counter,
    create_temp_files,
    extract_pages_from_pdf_di,
    get_time_counter,
)
from .prompts import pre_analysis_identity_card_prompt
from .config import gpt_4_1_mini, llm
from .state import CarteiraIdentidadePreAnaliseState
from .pre_analysis_identity_models import (
    CarteiraIdentidade,
)


class PreAnalysisIdentityCard:
    MAX_DOCS = 10

    def __init__(self, files, option: int):
        """Inicializa o processador de carteira de identidade"""
        if not isinstance(files, list):
            files = [files]
        self.files = files[: self.MAX_DOCS]
        self.option = option
        self.workflow = self._setup_pre_analysis_identity_workflow()

    def _setup_pre_analysis_identity_workflow(self):
        """Configura o fluxo específico para carteira de identidade"""
        workflow = StateGraph(CarteiraIdentidadePreAnaliseState)
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
        Processa a lista de documentos (máx 3) e retorna uma lista de resultados.
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
            # Invoca o workflow para processar APENAS este arquivo
            result = self.workflow.invoke(
                {
                    "files": [file_obj],
                    "temp_file": temp_file,
                    "start_time": get_time_counter(),
                    "documents": [],
                    "name": "null",
                    "rg": "null",
                    "cpf": "null",
                },
                config=config,
            )
            all_results.append(result)
        return all_results

    def extraction_node(self, state: CarteiraIdentidadePreAnaliseState):
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

    def analysis_node(self, state: CarteiraIdentidadePreAnaliseState):
        """Analisa a carteira de identidade e extrai informações estruturadas usando Pydantic"""
        documents = state["documents"]
        all_text = ""
        # Consolidar todo o texto de UM ÚNICO documento
        for document in documents:
            for page in document:
                all_text += page["text"] + "\n\n"
        # Usar structured output com Pydantic diretamente
        identical_template = PromptTemplate(
            template=pre_analysis_identity_card_prompt, input_variables=["texto"]
        )
        structured_llm = llm.with_structured_output(CarteiraIdentidade)
        identical_chain = identical_template | structured_llm
        prontuario = identical_chain.invoke({"texto": all_text})
        name = prontuario.name or "null"
        rg = prontuario.rg or "null"
        cpf = prontuario.cpf or "null"

        extracted_data_safe = {
            "Nome do Indivíduo": name,
            "RG do Indivíduo": rg,
            "CPF do Indivíduo": cpf,
        }
        return {
            "extracted_data": extracted_data_safe,
            "name": name,
            "rg": rg,
            "cpf": cpf,
        }

    def format_node(self, state: CarteiraIdentidadePreAnaliseState):
        """Formata o resultado final em CSV, garantindo o encoding correto (BOM)."""
        extracted_data = state["extracted_data"]
        time_counter = calc_time_counter(state["start_time"])
        file_name_base = "Analise_Carteira_Identidade"
        file_name = file_name_base

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
            # Fallback com UUID
            unique_suffix = str(uuid4())[:8]
            file_name = f"{file_name_base}_Fallback_{unique_suffix}"
        # --- Fim da Lógica de Nome de Arquivo ---

        # Criar DataFrame a partir do dicionário seguro
        df = pd.DataFrame([extracted_data])
        # Reindexação para garantir a ordem das colunas
        column_order = ["Nome do Indivíduo", "RG do Indivíduo", "CPF do Indivíduo"]
        df = df.reindex(columns=column_order, fill_value="")
        # Gerar CSV em buffer
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8", sep=";")
        csv_content_str = csv_buffer.getvalue()

        BOM = b"\xef\xbb\xbf"
        csv_content_bytes = BOM + csv_content_str.encode("utf-8")
        # Retorna os dados do documento atual
        return {
            "result": {"csv_file": csv_content_bytes, "file_name": file_name},
            "name": state.get("name", "null"),
            "cpf": state.get("cpf", "null"),
            "end_time": time_counter["end_time"],
            "elapsed_time": time_counter["elapsed_time"],
        }
