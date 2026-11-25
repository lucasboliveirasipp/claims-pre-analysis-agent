import pandas as pd
import io
import json
import re
import unicodedata
from typing import List, Dict, Any, Tuple, Optional
from langgraph.graph import END, StateGraph, START
from langchain_core.prompts import PromptTemplate
from .tools import (
    calc_time_counter,
    create_temp_files,
    extract_pages_from_pdf_di,
    get_time_counter,
)
from .prompts import (
    pre_analysis_gfip_prompt,
    verification_gfip_prompt_cpf_raw_text,
    verification_gfip_prompt_nome_raw_text,
    extraction_employees_list_gfip_prompt,
    extraction_afastamento_prompt,
)
from .config import llm  # Ajuste conforme sua importação do LLM
from .state import DataGFIPState, FuncionarioGFIPState, ComparacaoDocState
from .pre_analysis_gfip_models import (
    GFIP,
    FuncionarioGFIP,
    FuncionariosGFIPList,
    FuncionariosNomeCpfList,
    ListaAfastamentos,
    ComparacaoResult,
)


# --- FUNÇÕES AUXILIARES ---
def clean_value(val):
    """Garante que None, 'NULO', 'NULL' e strings vazias retornem ''."""
    if val is None:
        return ""
    val_str = str(val).strip()
    if val_str.upper() in ["NULO", "NULL", "NONE", "N/A", "NAN"]:
        return ""
    return val_str.replace("\n", " ")


def normalize_text_for_search(text: str) -> str:
    """Remove acentos, pontuações não essenciais e espaços extras para busca robusta."""
    if not isinstance(text, str):
        return ""
    normalized_text = (
        unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    )
    # Remove tudo que não for letra ou número
    cleaned_text = re.sub(r"[^a-zA-Z0-9\s]", "", normalized_text)
    # Remove espaços duplicados e converte para maiúsculo
    final_text = re.sub(r"\s+", " ", cleaned_text).strip().upper()
    return final_text


def extract_gfip_info_regex(text: str) -> Tuple[str, str, str]:
    """Extração via Regex otimizada para cabeçalho GFIP."""
    enterprise_name = "null"
    cnpj = "null"
    total_employees = "null"

    # Regex CNPJ
    cnpj_pattern = r"(?:CNPJ\s*/\s*CEI|Estabelecimento)\s*[:\s\n]*((?:\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})|(?:\d{14}))"
    cnpj_match = re.search(cnpj_pattern, text, re.IGNORECASE | re.DOTALL)
    if cnpj_match:
        cnpj_val = cnpj_match.group(1).strip()
        if cnpj_val:
            cnpj = cnpj_val
    if cnpj == "null":
        fallback_cnpj_pattern = r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})"
        fallback_cnpj_match = re.search(fallback_cnpj_pattern, text)
        if fallback_cnpj_match:
            cnpj = fallback_cnpj_match.group(1)

    # Regex Nome Empregador
    enterprise_pattern = r"(?:Nome Empregador)\s*[:\s\n]+([A-ZÀ-ÿ\s\.,\d&-]+)(?:\n\s*(CNPJ|Qtd|Endereço)|\Z)"
    enterprise_match = re.search(enterprise_pattern, text, re.IGNORECASE | re.DOTALL)
    if enterprise_match:
        name_capture = enterprise_match.group(1).strip()
        name_capture = re.sub(r"\s+", " ", name_capture)
        if "Qtd Trabalhadores" not in name_capture:
            enterprise_name = name_capture

    # Regex Qtd Trabalhadores
    employees_pattern = r"(?:Qtd Trabalhadores FGTS).*?(\d+)"
    employees_match = re.search(employees_pattern, text, re.IGNORECASE | re.DOTALL)
    if employees_match:
        total_employees = employees_match.group(1).strip()

    return total_employees, enterprise_name, cnpj


def extract_all_cnpjs_and_prioritize(text: str) -> Optional[str]:
    """Extrai e prioriza CNPJs (Matriz vs Filial)."""
    cnpj_pattern_capture = (
        r"((?:\d{2}[\.\s\-]?\d{3}[\.\s\-]?\d{3}[\/\s\-]?\d{4}[\-\s\.]?\d{2}))"
    )

    # 1. Tenta encontrar CNPJ do EMPREGADOR/EMITENTE por RÓTULO
    matriz_label_pattern = r"(?:Empregador|Emitida por).*?" + cnpj_pattern_capture
    matriz_label_match = re.search(
        matriz_label_pattern, text, re.IGNORECASE | re.DOTALL
    )
    if matriz_label_match:
        cnpj_raw = matriz_label_match.group(1)
        cnpj_clean = re.sub(r"[\.\-\/\s\n]", "", cnpj_raw)
        if len(cnpj_clean) == 14:
            return cnpj_clean

    # 2. Fallback Heurístico
    raw_cnpjs = re.findall(cnpj_pattern_capture, text)
    cnpjs_unicos = []
    for raw_cnpj in raw_cnpjs:
        cnpj_limpo = re.sub(r"[\.\-\/\s\n]", "", raw_cnpj)
        if len(cnpj_limpo) == 14 and cnpj_limpo not in cnpjs_unicos:
            cnpjs_unicos.append(cnpj_limpo)

    cnpj_matriz_fallback = None
    for c in cnpjs_unicos:
        if not c.endswith("0001"):
            return c
        elif c.endswith("0001") and cnpj_matriz_fallback is None:
            cnpj_matriz_fallback = c

    return cnpj_matriz_fallback


def identify_duplicity(employees_list: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Identifica duplicidade de Nome ou CPF na lista de funcionários."""
    name_to_cpf: Dict[str, str] = {}
    cpf_to_name: Dict[str, str] = {}
    duplicity_list: List[Dict[str, Any]] = []
    for emp in employees_list:
        name = clean_value(emp.get("Nome Trabalhador", "")).upper()
        cpf = clean_value(emp.get("CPF", ""))

        if not name or not cpf:
            continue

        # Conflito 1: Mesmo Nome, CPF Diferente
        if name in name_to_cpf and name_to_cpf[name] != cpf:
            new_entry = {**emp, "Motivo": "Duplicidade de Nome (CPFs diferentes)"}
            if new_entry not in duplicity_list:
                duplicity_list.append(new_entry)

            original = next(
                (
                    e
                    for e in employees_list
                    if clean_value(e.get("CPF", "")) == name_to_cpf[name]
                ),
                None,
            )
            if original:
                original_entry = {
                    **original,
                    "Motivo": "Duplicidade de Nome (CPFs diferentes)",
                }
                if original_entry not in duplicity_list:
                    duplicity_list.append(original_entry)
        name_to_cpf[name] = cpf

        # Conflito 2: Mesmo CPF, Nome Diferente
        if cpf in cpf_to_name and cpf_to_name[cpf] != name:
            new_entry = {**emp, "Motivo": "Duplicidade de CPF (Nomes diferentes)"}
            if new_entry not in duplicity_list:
                duplicity_list.append(new_entry)

            original = next(
                (
                    e
                    for e in employees_list
                    if clean_value(e.get("Nome Trabalhador", "")).upper()
                    == cpf_to_name[cpf]
                ),
                None,
            )
            if original:
                original_entry = {
                    **original,
                    "Motivo": "Duplicidade de CPF (Nomes diferentes)",
                }
                if original_entry not in duplicity_list:
                    duplicity_list.append(original_entry)
        cpf_to_name[cpf] = name

    # Remove duplicatas exatas na lista final
    unique_duplicity = []
    seen = set()
    for item in duplicity_list:
        key = (item.get("Nome Trabalhador"), item.get("CPF"), item.get("Motivo"))
        if key not in seen:
            unique_duplicity.append(item)
            seen.add(key)

    return unique_duplicity


CONTEXT_WINDOW = 500


class PreAnalysisGFIP:
    def __init__(
        self,
        files,
        option: int,
        sub_option: int,
        cpf_busca: str = None,
        nome_busca: str = None,
        file_to_compare=None,
    ):
        if not isinstance(files, list):
            self.files = [files]
        else:
            self.files = files

        self.option = option
        self.sub_option = sub_option
        self.file_to_compare = file_to_compare

        # Limpeza de inputs
        if cpf_busca:
            self.cpf_busca = cpf_busca.replace(".", "").replace("-", "")
        else:
            self.cpf_busca = ""
        self.nome_busca = nome_busca if nome_busca else ""
        # Validação Inicial
        if self.sub_option == 2 and not self.cpf_busca:
            raise ValueError(
                "Erro de Validação: A Sub-opção 2 (Busca por CPF) requer 'cpf_busca'."
            )
        elif self.sub_option == 3 and not self.nome_busca:
            raise ValueError(
                "Erro de Validação: A Sub-opção 3 (Busca por Nome) requer 'nome_busca'."
            )
        elif self.sub_option == 4 and (not self.files or not self.file_to_compare):
            raise ValueError(
                "Erro de Validação: A Sub-opção 4 (Comparação) requer dois arquivos."
            )
        self.workflow = self._setup_pre_analysis_gfip_workflow()

    def _setup_pre_analysis_gfip_workflow(self):
        if self.sub_option == 1:
            return self._setup_pre_analysis_gfip_workflow_geral().compile()
        elif self.sub_option == 2 or self.sub_option == 3:
            return self._setup_pre_analysis_gfip_workflow_verificacao().compile()
        elif self.sub_option == 4:
            # 🆕 Setup do Workflow de Comparação
            return self._setup_pre_analysis_gfip_workflow_comparacao().compile()
        else:
            raise ValueError(f"Sub-opção GFIP inválida: {self.sub_option}")

    def _setup_pre_analysis_gfip_workflow_geral(self):
        workflow = StateGraph(DataGFIPState)
        workflow.add_node("extraction_node", self.extraction_node_geral)
        workflow.add_node("analysis_node", self.analysis_node_geral)
        workflow.add_node("format_node", self.format_node_geral)
        workflow.add_edge(START, "extraction_node")
        workflow.add_edge("extraction_node", "analysis_node")
        workflow.add_edge("analysis_node", "format_node")
        workflow.add_edge("format_node", END)
        return workflow

    def _setup_pre_analysis_gfip_workflow_verificacao(self):
        workflow = StateGraph(FuncionarioGFIPState)
        workflow.add_node("extraction_node", self.extraction_node_geral)
        workflow.add_node("analysis_node", self.analysis_node_verificacao)
        workflow.add_node("duplicity_node", self.duplicity_node)
        workflow.add_node("format_node", self.format_node_verificacao)
        workflow.add_edge(START, "extraction_node")
        workflow.add_edge("extraction_node", "analysis_node")
        workflow.add_edge("analysis_node", "duplicity_node")
        workflow.add_edge("duplicity_node", "format_node")
        workflow.add_edge("format_node", END)
        return workflow

    def _setup_pre_analysis_gfip_workflow_comparacao(self):
        """Configura o grafo para a Opção 4: Comparação de Documentos."""
        workflow = StateGraph(ComparacaoDocState)

        # 1. Extração de texto de ambos os documentos
        workflow.add_node("extraction_node_comparacao", self.extraction_node_comparacao)
        # 2. Extração das listas de nomes/CPFs
        workflow.add_node("extraction_lists_node", self.extraction_lists_node)
        # 3. Lógica de comparação (Match/Mismatch)
        workflow.add_node("comparison_node", self.comparison_node)
        # 4. Formatação para CSV
        workflow.add_node("format_node_comparacao", self.format_node_comparacao)

        workflow.add_edge(START, "extraction_node_comparacao")
        workflow.add_edge("extraction_node_comparacao", "extraction_lists_node")
        workflow.add_edge("extraction_lists_node", "comparison_node")
        workflow.add_edge("comparison_node", "format_node_comparacao")
        workflow.add_edge("format_node_comparacao", END)
        return workflow

    def process_documents(self, config):
        """
        Inicializa o estado com base na sub-opção selecionada, executa o workflow
        e formata a saída para o Streamlit (especialmente para a sub-opção 4).
        """

        # --- OPÇÃO 1: GERAL ---
        if self.sub_option == 1:
            initial_state = {
                "files": self.files,
                "start_time": get_time_counter(),
                "documents": [],
                "extracted_data": {},
                "total_employees": "",
                "enterprise_name": "",
                "cnpj": "",
                "category": "",
                "result": {},
                "end_time": 0.0,
                "elapsed_time": None,
            }

        # --- OPÇÃO 2: CPF | OPÇÃO 3: NOME ---
        elif self.sub_option in [2, 3]:
            initial_state = {
                "files": self.files,
                "start_time": get_time_counter(),
                "documents": [],
                "cpf_busca": self.cpf_busca,
                "nome_busca": self.nome_busca,
                "sub_option": self.sub_option,
                "nome_trabalhador": "",
                "matricula": "",
                "cpf": "",
                "categoria": "",
                "nome_empregador": "",
                "cnpj": "",
                "status_verificacao": "",
                "final_duplicidade": "",
                "extracted_data": {},
                "duplicity_data": [],
                "result": {},
                "end_time": 0.0,
                "elapsed_time": None,
            }

        # --- OPÇÃO 4: COMPARAÇÃO ---
        elif self.sub_option == 4:
            # Prepara as listas de arquivos.
            files_gfip = self.files
            files_afastamento = [self.file_to_compare] if self.file_to_compare else []

            initial_state = {
                "files_gfip": files_gfip,
                "files_afastamento": files_afastamento,
                "documents_gfip": [],
                "documents_afastamento": [],
                "gfip_employees_list": [],
                "afastamento_data": [],
                "result_comparacao": [],
                "result": {},
                "start_time": get_time_counter(),
                "end_time": 0.0,
                "elapsed_time": None,
            }

        else:
            raise ValueError(f"Sub-opção GFIP inválida: {self.sub_option}")

        if self.workflow:
            # 1. Executa o Workflow
            final_state = self.workflow.invoke(initial_state, config=config)

            # 2. Formata a Saída para o Streamlit
            # A formatação é necessária para o Streamlit consumir as chaves esperadas.
            if self.sub_option == 4:

                return {
                    "comparison_data": final_state.get(
                        "result_comparacao", []
                    ),  # <-- CHAVE CORRIGIDA
                    "result": final_state.get(
                        "result", []
                    ),  # Arquivo CSV para download
                    "end_time": final_state.get("end_time"),
                    "elapsed_time": final_state.get("elapsed_time"),
                }
            elif self.sub_option in [2, 3]:
                # Mapeia a saída para as opções de Verificação
                return {
                    "extracted_data": final_state.get("extracted_data"),
                    "duplicity_data": final_state.get("duplicity_data"),
                    "result": final_state.get(
                        "result", []
                    ),  # CSV de Duplicidade para download
                    "end_time": final_state.get("end_time"),
                    "elapsed_time": final_state.get("elapsed_time"),
                }
            # Opção 1 (Geral) e outros retornos genéricos podem ser retornados diretamente
            return final_state
        else:
            return {"error": "Workflow not configured"}

    # --- NODES GERAIS (OPÇÕES 1, 2, 3) ---
    def extraction_node_geral(self, state):
        """Extrai texto dos documentos (comum opções 1-3)."""
        temp_files = create_temp_files(state["files"])
        documents = []
        for f in temp_files:
            documents.append(
                extract_pages_from_pdf_di(
                    f["metadata"]["temp_name"], f["metadata"]["original_name"]
                )
            )
        return {"documents": documents}

    def analysis_node_geral(self, state: DataGFIPState):
        """Analisa dados gerais da GFIP (Opção 1)."""
        documents = state["documents"]
        all_text = ""
        for document in documents:
            for page in document:
                all_text += page["text"] + "\n\n"

        regex_employees, regex_enterprise, regex_cnpj = extract_gfip_info_regex(
            all_text
        )

        pre_fill_prompt = f"""
        # Dados de Pré-Análise via Regex:
        - Numero Total de Funcionários: {regex_employees}
        - Nome Empregador: {regex_enterprise}
        - CNPJ: {regex_cnpj}
        """

        final_prompt_template = PromptTemplate(
            template=pre_analysis_gfip_prompt.replace(
                "Texto do documento da GFIP: {texto}",
                f"{pre_fill_prompt}\n\nTexto do documento da GFIP: {{texto}}",
            ),
            input_variables=["texto"],
        )

        structured_llm = llm.with_structured_output(GFIP)
        gfip_chain = final_prompt_template | structured_llm
        gfip = gfip_chain.invoke({"texto": all_text})

        return {
            "extracted_data": gfip.to_csv_dict(),
            "cnpj": gfip.cnpj or "",
            "enterprise_name": gfip.enterprise_name or "",
            "total_employees": gfip.total_employees or "",
            "category": gfip.category or "",
        }

    def format_node_geral(self, state: DataGFIPState):
        """Gera CSV para Classificação Geral."""
        extracted_data = state["extracted_data"]
        time_counter = calc_time_counter(state["start_time"])
        file_name = "Analise_GFIP_Geral"
        df = pd.DataFrame([extracted_data])
        column_order = [
            "CNPJ do Estabelecimento",
            "Nome Empregador",
            "Numero Total de Funcionários",
            "Categoria do Empregado",
        ]
        df = df.reindex(columns=column_order, fill_value="")
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8", sep=";")
        csv_content_str = csv_buffer.getvalue()
        BOM = b"\xef\xbb\xbf"
        csv_content_bytes = BOM + csv_content_str.encode("utf-8")
        result_files = [{"csv_file": csv_content_bytes, "file_name": file_name}]
        return {
            "result": result_files,
            "end_time": time_counter["end_time"],
            "elapsed_time": time_counter["elapsed_time"],
        }

    def analysis_node_verificacao(self, state: Dict[str, Any]):
        """Analisa dados de verificação por CPF/Nome (Opções 2 e 3)."""
        documents = state.get("documents", [])
        # Fallback para self attributes se state estiver vazio
        cpf_busca = (state.get("cpf_busca", "") or self.cpf_busca) or ""
        nome_busca = (state.get("nome_busca", "") or self.nome_busca) or ""
        sub_option = state.get("sub_option", self.sub_option)
        raw_text = "".join(
            page.get("text", "") + " " for document in documents for page in document
        )
        context_text = raw_text
        final_prompt = None
        # Definição de Prompt e Chunking
        if sub_option == 2 and cpf_busca.strip():
            final_prompt = verification_gfip_prompt_cpf_raw_text
            search_term_cpf = re.sub(r"\D", "", cpf_busca)
            match_original = re.search(re.escape(search_term_cpf), raw_text)
            if match_original:
                start = match_original.start()
                c_start = max(0, start - CONTEXT_WINDOW)
                c_end = min(
                    len(raw_text), start + len(search_term_cpf) + CONTEXT_WINDOW
                )
                context_text = raw_text[c_start:c_end]
        elif sub_option == 3 and nome_busca.strip():
            final_prompt = verification_gfip_prompt_nome_raw_text
            # Para nome, mantemos o texto completo ou poderíamos implementar busca fuzzy aqui
            # para reduzir contexto, mas a busca por nome se beneficia de mais contexto.

        if not final_prompt:
            raise ValueError("Prompt não definido. Verifique os parâmetros de busca.")
        # Extrações Regex de Apoio
        final_cnpj_estab_prioritario = extract_all_cnpjs_and_prioritize(raw_text)
        _, nome_empregador_val_raw, _ = extract_gfip_info_regex(raw_text)
        nome_empregador_val = (
            nome_empregador_val_raw if nome_empregador_val_raw != "null" else None
        )
        # Chamada LLM
        verification_chain = (
            PromptTemplate(
                template=final_prompt,
                input_variables=["texto", "cpf_busca", "nome_busca"],
            )
            | llm
        )

        raw_result = verification_chain.invoke(
            {"texto": context_text, "cpf_busca": cpf_busca, "nome_busca": nome_busca}
        )

        # Processamento da String Pura retornada pelo LLM
        raw_result_string = getattr(raw_result, "content", "")
        parsed_data = {}
        for line in raw_result_string.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                parsed_data[key.strip().upper().replace("_", " ")] = value.strip()

        status = parsed_data.get("STATUS", "NÃO ENCONTRADO")
        encontrado = status == "ENCONTRADO"

        # Consolidação dos Dados
        final_nome = parsed_data.get("NOME TRABALHADOR") if encontrado else None
        final_cpf = parsed_data.get("CPF ENCONTRADO") if encontrado else cpf_busca
        final_matricula = parsed_data.get("MATRICULA") if encontrado else None
        final_categoria = parsed_data.get("CATEGORIA") if encontrado else None

        # Refinamento de Matrícula (se for igual ao CPF, descarta)
        if final_matricula and final_matricula not in ["NULO", "null"]:
            mat_clean = re.sub(r"\D", "", final_matricula)
            cpf_clean = re.sub(r"\D", "", cpf_busca or "")
            if cpf_clean and (mat_clean == cpf_clean or len(mat_clean) >= 11):
                final_matricula = None

        # Consolidação de CNPJ
        cnpj_llm = parsed_data.get("CNPJ")
        final_cnpj_bruto = (
            final_cnpj_estab_prioritario if final_cnpj_estab_prioritario else cnpj_llm
        )
        final_cnpj = None
        if final_cnpj_bruto and final_cnpj_bruto not in ["null", "NULO", None]:
            c_limpo = re.sub(r"[\.\-\/\s\n]", "", final_cnpj_bruto)
            if len(c_limpo) == 14:
                final_cnpj = c_limpo

        # Consolidação Nome Empregador
        llm_emp = parsed_data.get("NOME EMPREGADOR")
        final_emp = (
            nome_empregador_val
            if (nome_empregador_val and "Qtd." not in nome_empregador_val)
            else llm_emp
        )
        if final_emp:
            final_emp = re.sub(
                r"[\s\d\.]+Qtd\.\s*Trabalhadores.*$", "", final_emp, flags=re.IGNORECASE
            ).strip()
        extracted_data = {
            "Nome Trabalhador": clean_value(final_nome),
            "Matrícula": clean_value(final_matricula),
            "CPF": clean_value(final_cpf),
            "Categoria": clean_value(final_categoria),
            "Nome Empregador": clean_value(final_emp),
            "CNPJ da empresa/estabelecimento": clean_value(final_cnpj),
            "Status da Verificação": clean_value(status),
            "Duplicidade de Nome": clean_value(parsed_data.get("DUPLICIDADE")),
        }

        return {
            "extracted_data": extracted_data,
            "nome_trabalhador": final_nome,
            "cpf": final_cpf,
            "cnpj": final_cnpj,
            "nome_empregador": final_emp,
            "status_verificacao": status,
            "final_duplicidade": parsed_data.get("DUPLICIDADE"),
        }

    def duplicity_node(self, state: Dict[str, Any]):
        """Verifica duplicidades na lista completa (Opções 2 e 3)."""
        documents = state.get("documents", [])
        raw_text = "".join(
            page.get("text", "") + " " for doc in documents for page in doc
        )

        chain = PromptTemplate(
            template="Extraia a lista completa de funcionários: NOME, CPF, MATRICULA.",
            input_variables=["texto"],
        ) | llm.with_structured_output(FuncionariosGFIPList)

        try:
            res = chain.invoke({"texto": raw_text})
            emp_list = [e.dict() for e in res.funcionarios]
            duplicity_data = identify_duplicity(emp_list)
        except Exception as e:
            print(f"Erro duplicidade: {e}")
            duplicity_data = []

        return {"duplicity_data": duplicity_data}

    def format_node_verificacao(self, state: FuncionarioGFIPState):
        """Formata CSV para Verificação (Opções 2 e 3)."""
        extracted_data = state["extracted_data"]
        duplicity_data = state.get("duplicity_data", [])
        time_counter = calc_time_counter(state["start_time"])

        # Nome do arquivo
        busca = (
            state.get("nome_trabalhador")
            or state.get("cpf_busca")
            or state.get("nome_busca")
            or "busca"
        )
        busca_fmt = re.sub(r"[^a-zA-Z0-9_]", "", str(busca).replace(" ", "_")).upper()
        file_name = f"Verificacao_GFIP_{busca_fmt}"

        # CSV Principal
        df = pd.DataFrame([extracted_data])
        # Tipagem forte para evitar notação científica
        for col in ["CNPJ da empresa/estabelecimento", "CPF", "Matrícula"]:
            if col in df.columns:
                df[col] = df[col].astype(str)

        col_order = [
            "Nome Trabalhador",
            "Matrícula",
            "CPF",
            "Categoria",
            "Nome Empregador",
            "CNPJ da empresa/estabelecimento",
            "Status da Verificação",
            "Duplicidade de Nome",
        ]
        df = df.reindex(columns=col_order, fill_value="")

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8", sep=";")
        csv_bytes = b"\xef\xbb\xbf" + csv_buffer.getvalue().encode("utf-8")

        result_files = [{"csv_file": csv_bytes, "file_name": file_name}]

        # CSV Duplicidade
        if duplicity_data:
            df_dup = pd.DataFrame(duplicity_data)
            for col in ["CPF", "Matrícula"]:
                if col in df_dup.columns:
                    df_dup[col] = df_dup[col].astype(str)

            csv_buf_dup = io.StringIO()
            df_dup.to_csv(csv_buf_dup, index=False, encoding="utf-8", sep=";")
            csv_bytes_dup = b"\xef\xbb\xbf" + csv_buf_dup.getvalue().encode("utf-8")

            result_files.append(
                {
                    "csv_file": csv_bytes_dup,
                    "file_name": f"Duplicidade_GFIP_{busca_fmt}",
                }
            )

        return {
            "result": result_files,
            "end_time": time_counter["end_time"],
            "elapsed_time": time_counter["elapsed_time"],
        }

    # --- NODES PARA OPÇÃO 4: COMPARAÇÃO ---
    def extraction_node_comparacao(self, state: Dict[str, Any]):
        """Extrai texto dos dois documentos separadamente."""

        # 1. GFIP Principal
        temp_files_gfip = create_temp_files(state["files_gfip"])
        docs_gfip = []
        for f in temp_files_gfip:
            docs_gfip.append(
                extract_pages_from_pdf_di(
                    f["metadata"]["temp_name"], f["metadata"]["original_name"]
                )
            )
        # 2. Documento de Comparação (Afastamento/Outro)
        temp_files_afast = create_temp_files(state["files_afastamento"])
        docs_afast = []
        for f in temp_files_afast:
            docs_afast.append(
                extract_pages_from_pdf_di(
                    f["metadata"]["temp_name"], f["metadata"]["original_name"]
                )
            )
        return {
            "documents_gfip": docs_gfip,
            "documents_afastamento": docs_afast,
        }

    def extraction_lists_node(self, state: Dict[str, Any]):
        """
        Extrai a lista de Nomes/CPFs da GFIP e a lista de Afastamento do Documento 2.
        Inclui logs de depuração para verificar se o texto está sendo lido corretamente.
        """
        # 1. Juntar todo o texto das páginas extraídas da GFIP
        raw_text_gfip = "".join(
            page.get("text", "") + " "
            for doc in state.get("documents_gfip", [])
            for page in doc
        )

        # 2. Juntar todo o texto das páginas extraídas do documento de Comparação (Afastamento)
        raw_text_afast = "".join(
            page.get("text", "") + " "
            for doc in state.get("documents_afastamento", [])
            for page in doc
        )

        print("\n" + "=" * 40)
        print("🔍 INÍCIO DO DEBUG DE EXTRAÇÃO")
        print(f"📄 Tamanho do texto GFIP extraído: {len(raw_text_gfip)} caracteres")

        if len(raw_text_gfip) < 100:
            print(
                "⚠️ AVISO: Texto da GFIP parece muito curto ou vazio. Verifique se o PDF é uma imagem (necessita OCR)."
            )

        else:
            print(f"📝 Amostra GFIP: {raw_text_gfip[:200].replace(chr(10), ' ')}...")

        print(
            f"📄 Tamanho do texto Afastamento extraído: {len(raw_text_afast)} caracteres"
        )

        if len(raw_text_afast) < 100:
            print("⚠️ AVISO: Texto de Afastamento parece muito curto ou vazio.")

        else:
            print(
                f"📝 Amostra Afastamento: {raw_text_afast[:200].replace(chr(10), ' ')}..."
            )

        print("=" * 40 + "\n")

        gfip_chain = PromptTemplate(
            template=extraction_employees_list_gfip_prompt, input_variables=["texto"]
        ) | llm.with_structured_output(FuncionariosNomeCpfList)

        gfip_list = []

        try:

            print("🤖 Enviando GFIP para o LLM...")

            res_gfip = gfip_chain.invoke({"texto": raw_text_gfip})
            gfip_list = [e.model_dump(by_alias=True) for e in res_gfip.funcionarios]

            print(f"✅ Sucesso GFIP: {len(gfip_list)} funcionários encontrados.")

        except Exception as e:

            print(f"❌ ERRO CRÍTICO na extração da lista GFIP: {e}")

        # 4. Processamento LLM - Lista Afastamento

        afast_chain = PromptTemplate(
            template=extraction_afastamento_prompt, input_variables=["texto"]
        ) | llm.with_structured_output(ListaAfastamentos)

        afast_data = []

        try:

            print("🤖 Enviando Afastamento para o LLM...")
            res_afast = afast_chain.invoke({"texto": raw_text_afast})
            afast_data = [a.model_dump(by_alias=True) for a in res_afast.afastamentos]

            print(f"✅ Sucesso Afastamento: {len(afast_data)} registros encontrados.")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO na extração da lista Afastamento: {e}")

        return {
            "gfip_employees_list": gfip_list,
            "afastamento_data": afast_data,
        }

    def comparison_node(self, state: Dict[str, Any]):
        """
        Compara as duas listas extraídas (GFIP e Afastamento), garantindo que os dados
        solicitados (Nome, CPF, Data Afastamento, Tipo Afastamento) sejam incluídos
        no relatório final (result_comparacao).
        CORRIGIDO: Busca pelas chaves do Afastamento em minúsculo e com underscore.
        ADICIONADO: Filtro para retornar APENAS status "Match" e remover a coluna "Matrícula (GFIP)".
        """
        # Assume que 'clean_value' e 'normalize_text_for_search' estão definidos globalmente ou na classe.
        gfip_list = state["gfip_employees_list"]
        afast_list = state["afastamento_data"]
        # Lista temporária para armazenar TODOS os resultados da comparação (Match, Mismatch, etc.)
        temp_comparacao = []
        # Mapeamento GFIP para busca O(1) com chave normalizada
        gfip_map: Dict[str, List[Dict]] = {}

        # ----------------------------------------------------
        # DEBUG: Inspecionando o conteúdo BRUTO do Afastamento
        print("\n" + "=" * 50)
        print("🔍 DEBUG: Conteúdo Bruto do Afastamento")
        for i, item in enumerate(afast_list):
            print(f"Item #{i+1} de Afastamento Bruto: {item}")
        print("=" * 50)
        # ----------------------------------------------------

        print("\n" + "=" * 50)
        print("🔍 DEBUG: Gerando chaves de normalização da GFIP")
        # 1. GERAÇÃO DAS CHAVES DA GFIP
        for emp in gfip_list:
            nome_raw = clean_value(emp.get("NOME", ""))
            cpf_gfip = clean_value(emp.get("CPF", ""))
            key = normalize_text_for_search(nome_raw)
            # LOG COM CPF INCLUÍDO
            print(
                f"GFIP Raw: '{nome_raw[:25]}...' | CPF: {cpf_gfip[:3]}... | Key: '{key}'"
            )

            if key:
                if key not in gfip_map:
                    gfip_map[key] = []
                gfip_map[key].append(
                    {
                        "nome_trabalhador": nome_raw,
                        "cpf_gfip": cpf_gfip,
                        "matricula_gfip": clean_value(emp.get("MATRICULA", "")),
                    }
                )

        matched_keys = set()
        print("\n" + "=" * 50)
        print("🔍 DEBUG: Comparando Afastamento com chaves da GFIP (Chaves CORRIGIDAS)")
        # 2. ITERA SOBRE O DOCUMENTO DE AFASTAMENTO E BUSCA NA GFIP
        for item in afast_list:
            # --- LÓGICA DE FALLBACK PARA OBTENÇÃO DO NOME ---
            # Tenta pegar pelo nome_trabalhador (chave real) ou usa o fallback
            nome_afast_raw = clean_value(
                item.get("nome_trabalhador")
                or item.get("NOME")
                or item.get("NOME_TRABALHADOR")
                or item.get("TRABALHADOR")
                or ""
            )

            if not nome_afast_raw or len(nome_afast_raw.strip()) <= 3:
                fallback_name = ""
                for k, v in item.items():
                    val = clean_value(v)
                    # Evita usar as chaves de data/tipo no fallback de nome
                    if (
                        k.upper()
                        not in [
                            "TIPO_AFASTAMENTO",
                            "DATA_AFASTAMENTO",
                            "TIPO_AFASTAMENTO",
                            "DATA_AFASTAMENTO",
                        ]
                        and len(val) > len(fallback_name)
                        and len(val) > 5
                    ):
                        fallback_name = val
                nome_afast_raw = clean_value(
                    item.get("nome_trabalhador") or fallback_name
                )  # Tenta novamente com o nome_trabalhador

            tipo = clean_value(item.get("tipo_afastamento"))
            data = clean_value(item.get("data_afastamento", ""))
            # Tratamento para 'None' ou vazio
            if not tipo:
                tipo = "Não Informado no Documento"
            key = normalize_text_for_search(nome_afast_raw)
            # LOG DO ITEM DE AFASTAMENTO (Nome, Tipo, Data)
            print(
                f"Afastamento Raw: '{nome_afast_raw[:25]}...' | Tipo: {tipo} | Data: {data} | Key: '{key}'"
            )
            found = False
            if key in gfip_map:
                for match in gfip_map[key]:
                    temp_comparacao.append(
                        {
                            "Nome Trabalhador": match["nome_trabalhador"],
                            "CPF (GFIP)": match["cpf_gfip"],
                            "Matrícula (GFIP)": match[
                                "matricula_gfip"
                            ],  # Mantido aqui temporariamente
                            "Tipo de Afastamento": tipo,
                            "Data de Afastamento": data,
                            "Status da Comparação": "Encontrado",
                        }
                    )
                matched_keys.add(key)
                found = True
                # LOG DE MATCH
                print(
                    f"✅ MATCH ENCONTRADO! GFIP CPF: {match['cpf_gfip']} | Afastamento Tipo: {tipo} | Data: {data}"
                )
            if not found:
                # Caso "Apenas Doc. Comparação"
                temp_comparacao.append(
                    {
                        "Nome Trabalhador": nome_afast_raw,
                        "CPF (GFIP)": "N/A (Apenas Afastamento)",
                        "Matrícula (GFIP)": "N/A",  # Mantido aqui temporariamente
                        "Tipo de Afastamento": tipo,
                        "Data de Afastamento": data,
                        "Status da Comparação": "Apenas Doc. Comparação",
                    }
                )
                print(f"❌ MISMATCH para a chave: {key}")

        # 3. VERIFICA QUEM SOBROU NA GFIP (Apenas GFIP)
        for key, matches in gfip_map.items():
            if key not in matched_keys:
                if len(key) < 5:
                    continue
                for match in matches:
                    # Caso "Apenas GFIP"
                    temp_comparacao.append(
                        {
                            "Nome Trabalhador": match["nome_trabalhador"],
                            "CPF (GFIP)": match["cpf_gfip"],
                            "Tipo de Afastamento": "N/A (Apenas GFIP)",
                            "Data de Afastamento": "N/A (Apenas GFIP)",
                            "Status da Comparação": "Apenas GFIP",
                        }
                    )

        # =======================================================
        # 4. APLICAÇÃO DOS FILTROS FINAIS (Match e Remoção de Coluna)
        # =======================================================
        result_comparacao = []
        for item in temp_comparacao:
            # Filtro 1: Exibir APENAS status "Match"
            if item.get("Status da Comparação") == "Encontrado":
                # Filtro 2: Remove a coluna Matrícula (GFIP)
                if "Matrícula (GFIP)" in item:
                    del item["Matrícula (GFIP)"]
                result_comparacao.append(item)
        print("\n" + "=" * 50)
        print("🔍 FIM DO DEBUG")
        print(
            f"Total de linhas no relatório final (APÓS FILTRO 'Match'): {len(result_comparacao)}"
        )
        print("=" * 50 + "\n")

        # ATENÇÃO: Verifique se o nome da chave de retorno é 'result_comparacao' ou 'comparison_data'
        return {"result_comparacao": result_comparacao}

    def format_node_comparacao(self, state: Dict[str, Any]):
        """Formata CSV da comparação."""

        # 1. PEGA OS DADOS PROCESSADOS
        data = state["result_comparacao"]
        time_counter = calc_time_counter(state["start_time"])
        file_name = "Comparacao_GFIP_Analise"

        if not data:
            return {
                "result": [{"error": "Nenhum dado gerado na comparação."}],
                "end_time": time_counter["end_time"],
                "elapsed_time": time_counter["elapsed_time"],
            }

        df = pd.DataFrame(data)
        col_order = [
            "Nome Trabalhador",
            "CPF (GFIP)",
            "Tipo de Afastamento",
            "Data de Afastamento",
            "Status da Comparação",
        ]

        df = df.reindex(columns=col_order, fill_value="")

        # Força string para CPFs/Matrículas

        for col in ["CPF (GFIP)", "Matrícula (GFIP)"]:
            if col in df.columns:
                df[col] = df[col].astype(str)

        # 3. GERA CSV COM BOM E PONTO E VÍRGULA

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8", sep=";")
        csv_content_str = csv_buffer.getvalue()
        BOM = b"\xef\xbb\xbf"
        csv_bytes = BOM + csv_content_str.encode("utf-8")

        return {
            "result": [{"csv_file": csv_bytes, "file_name": file_name}],
            "comparison_data": data,
            "end_time": time_counter["end_time"],
            "elapsed_time": time_counter["elapsed_time"],
        }
