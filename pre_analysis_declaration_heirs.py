import pandas as pd
import io
from typing import List, Dict, Any
from uuid import uuid4  # ⬅️ ADICIONADO: Import para ID único
from langgraph.graph import END, StateGraph, START
from langchain_core.prompts import PromptTemplate
from .tools import (
    calc_time_counter,
    create_temp_files,
    extract_pages_from_pdf_di,
    get_time_counter,
)
from .prompts import pre_analysis_declaration_heirs_prompt
from .config import gpt_4_1_mini, llm  # ⬅️ Ajustado para usar 'llm'
from .state import DeclarationOfHeirsState
from .pre_analysis_declaration_heirs_models import DeclaracaoHerdeiros


class PreAnalysisDeclarationHeirs:
    # Limite de documentos
    MAX_DOCS = 10

    def __init__(self, files, option: int):
        """
        Inicializa o processador de declaração de herdeiros
        Args:
            files: Arquivo ou lista de arquivos (máx 3) para processar
            option: Opção selecionada (módulo)
        """
        if not isinstance(files, list):
            files = [files]
        # Garante que files seja uma lista e limita ao máximo
        self.files = files[: self.MAX_DOCS]
        self.option = option
        self.workflow = self._setup_pre_analysis_declaration_heirs_workflow()

    def _setup_pre_analysis_declaration_heirs_workflow(self):
        """Configura o fluxo específico para uma ÚNICA declaração de herdeiros"""
        workflow = StateGraph(DeclarationOfHeirsState)
        workflow.add_node("extraction_node", self.extraction_node)
        workflow.add_node("analysis_node", self.analysis_node)
        workflow.add_node("format_node", self.format_node)
        workflow.add_edge(START, "extraction_node")
        workflow.add_edge("extraction_node", "analysis_node")
        workflow.add_edge("analysis_node", "format_node")
        workflow.add_edge("format_node", END)
        return workflow.compile()

    # ATUALIZADO: Itera sobre os arquivos e invoca o workflow para cada um.
    def process_documents(self, config):
        """
        Processa a lista de documentos (máx 3) e retorna uma lista de resultados,
        um para cada arquivo.
        """
        all_results = []
        # Cria os arquivos temporários uma vez
        temp_files_data = create_temp_files(self.files)
        for i, file_obj in enumerate(self.files):
            # Encontra o nome temporário correspondente ao arquivo
            temp_file = next(
                (
                    f
                    for f in temp_files_data
                    if f["metadata"]["original_name"]
                    == getattr(file_obj, "name", f"documento_{i}.pdf")
                ),
                None,
            )
            if not temp_file:
                print(
                    f"Aviso: Não encontrou arquivo temporário para {getattr(file_obj, 'name', i)}"
                )
                continue
            # Invoca o workflow para processar APENAS este arquivo
            result = self.workflow.invoke(
                {
                    "files": [file_obj],
                    "temp_file": temp_file,  # Novo campo para o nó de extração
                    "start_time": get_time_counter(),
                    "documents": [],
                    # Campos comuns adicionados (necessários para o Agente Global)
                    "name": "null",
                    "cpf": "null",
                },
                config=config,
            )
            # Adiciona o resultado individual à lista
            all_results.append(result)
        return all_results  # Retorna a lista completa de resultados

    # ATUALIZADO: Recebe apenas o caminho do arquivo temporário.
    def extraction_node(self, state: DeclarationOfHeirsState):
        """Extrai texto de UM documento usando Document Intelligence"""
        # Recebe o arquivo temporário
        temp_file = state.get("temp_file")
        if not temp_file:
            raise ValueError(
                "Caminho do arquivo temporário não fornecido para extração."
            )
        # Extrai de um único arquivo
        document_pages = extract_pages_from_pdf_di(
            temp_file["metadata"]["temp_name"], temp_file["metadata"]["original_name"]
        )
        # O estado é atualizado com uma lista de 1 documento
        return {"documents": [document_pages]}

    # AJUSTADO: Consolidação de texto refeita para UM único documento.
    def analysis_node(self, state: DeclarationOfHeirsState):
        """Analisa a declaração de herdeiros e extrai informações estruturadas usando Pydantic"""
        documents = state["documents"]
        all_text = ""
        # Consolida o texto do ÚNICO documento na lista 'documents'
        for doc in documents:  # Deve ter apenas 1 iteração aqui
            for page in doc:
                all_text += page["text"] + "\n\n"
        # Prompt + LLM estruturado
        declaration_heirs_template = PromptTemplate(
            template=pre_analysis_declaration_heirs_prompt, input_variables=["texto"]
        )
        structured_llm = llm.with_structured_output(DeclaracaoHerdeiros)
        declaration_heirs_chain = declaration_heirs_template | structured_llm
        # Invoca o LLM
        declaracao = declaration_heirs_chain.invoke({"texto": all_text})
        print(f"DEBUG - Objeto Pydantic criado diretamente: {declaracao}")
        csv_data = []
        name = "null"
        cpf = "null"
        for heir in declaracao.heirs:
            if heir.name and heir.name.strip():
                csv_data.append(heir.to_csv_dict())
                if name == "null" and heir.name:
                    name = heir.name
                if cpf == "null" and heir.cpf:
                    cpf = heir.cpf
        return {
            "extracted_data": csv_data,
            "name": name,
            "cpf": cpf,
        }

    def format_node(self, state: DeclarationOfHeirsState):
        """Formata o resultado final em CSV e garante unicidade do file_name e codificação correta."""
        extracted_data = state["extracted_data"]
        time_counter = calc_time_counter(state["start_time"])
        # Lógica de obtenção do nome de arquivo único
        file_name_base = "Analise_Declaracao_Herdeiros"
        file_name = file_name_base
        # 1. Tenta obter o nome original
        if (
            state.get("files")
            and isinstance(state["files"], list)
            and len(state["files"]) > 0
        ):
            original_file_obj = state["files"][0]
            original_name = getattr(original_file_obj, "name", "documento")

            if original_name and original_name != "documento":
                # Limpa a extensão do arquivo
                clean_name = (
                    original_name.rsplit(".", 1)[0]
                    if "." in original_name
                    else original_name
                )
                file_name = f"{file_name_base}_{clean_name}"
            else:
                unique_suffix = str(uuid4())[:8]
                file_name = f"{file_name_base}_fallback_{unique_suffix}"

        # Cria o DataFrame a partir da lista de herdeiros (csv_data)
        df = pd.DataFrame(extracted_data)
        # Colunas com separador ;
        column_order = [
            "Nome do Indivíduo",
            "RG do Indivíduo",
            "CPF do Indivíduo",
            "Autenticação do Documento",
        ]
        df = df.reindex(columns=column_order, fill_value="")
        csv_buffer = io.StringIO()
        # Gerar a string CSV usando UTF-8 e separador ;
        df.to_csv(csv_buffer, index=False, encoding="utf-8", sep=";")
        csv_content_str = csv_buffer.getvalue()

        BOM = b"\xef\xbb\xbf"
        csv_content_bytes = BOM + csv_content_str.encode("utf-8")
        return {
            # ⬅️ AJUSTE: Passando os bytes com BOM
            "result": {"csv_file": csv_content_bytes, "file_name": file_name},
            # ⬅️ ADICIONADO: Retorna os campos comuns no nível raiz
            "name": state.get("name", "null"),
            "cpf": state.get("cpf", "null"),
            "end_time": time_counter["end_time"],
            "elapsed_time": time_counter["elapsed_time"],
        }
