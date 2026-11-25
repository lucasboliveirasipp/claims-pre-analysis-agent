import base64
import streamlit as st
from uuid import uuid4
import io
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime
from feedback_local import update_feedback
from feedback_local import log_interaction
from .document_process import DocumentProcessor
from .medical_record_processor import MedicalRecordProcessor
from .document_recision import DocumentTermRecision
from .pre_analysis_global_agent import PreAnalysisGlobalAgent
from .pre_analysis_gfip import (
    PreAnalysisGFIP,
)

AGENT_NAME = "agente-pre-analise-sinistro"
option_dict = {
    "1. Tradução de documentos": 1,
    "2. Documento 'prontuário médico'": 2,
    "3. Documento 'Termo de Rescisão'": 3,
    "4. Pré-análise": 4,
    "7. GFIP": 7,
}


def initialize_chat_state():
    """Inicializa os estados necessários no 'st.session_state'"""
    if f"{AGENT_NAME}_chat_history" not in st.session_state:
        st.session_state[f"{AGENT_NAME}_chat_history"] = []
    if f"{AGENT_NAME}_thread_id" not in st.session_state:
        st.session_state[f"{AGENT_NAME}_thread_id"] = str(uuid4())


def reset_chat_state():
    """Reseta o estado do chat e gera um novo thread_id"""
    st.session_state[f"{AGENT_NAME}_chat_history"] = []
    st.session_state[f"{AGENT_NAME}_thread_id"] = str(uuid4())


def clear_session_response():
    if "response" in st.session_state:
        del st.session_state["response"]


def reset_response_id():
    st.session_state["response_id"] = str(uuid4())


def get_response_id():
    if "response_id" in st.session_state:
        return st.session_state["response_id"]
    else:
        return None


def get_valid_files(file_list):
    """Retorna uma lista de arquivos válida (não-vazia) ou None, limitando a 3."""
    if file_list and len(file_list) > 0:
        return file_list[:3]
    return None


def flatten_agent_results(
    response: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Transforma o dicionário de listas de resultados do agente em uma única lista plana."""
    all_results_flat = []
    for results_list in response.values():
        if results_list and isinstance(results_list, list):
            all_results_flat.extend(results_list)
    return all_results_flat


def build_page(is_authenticated: bool):
    if is_authenticated:
        st.title("Pré Análise de Sinistro")
        # Variável para armazenar a instância do Agente Global fora do botão
        global_agent = None
        if "global_agent_instance" in st.session_state:
            global_agent = st.session_state["global_agent_instance"]
        doc_name = "N/A - Processamento não iniciado"
        # --- SEÇÃO DE INPUT ---
        with st.container(border=True):
            option = st.selectbox("Modulo", (option_dict.keys()), key="seletor_modulo")
            selected_option = option_dict[option]
            # Variáveis específicas do Módulo 7 (GFIP)
            sub_option_code = None
            upload_file = None
            # NOVO: Variável para o segundo arquivo de comparação
            upload_file_comparacao = None
            cpf_busca = None
            # NOVO CAMPO
            nome_busca = None
            if selected_option == 4:
                # Pré-análise Global (Múltiplos arquivos)
                st.subheader("Upload de Documentos para Análise")
                # Arquivos do Agente 1 (Máx 3)
                death_certificate_file = st.file_uploader(
                    "Certidão de Óbito (máx. 10)",
                    type=["pdf"],
                    key="death_certificate_file",
                    accept_multiple_files=True,
                )
                # Arquivos do Agente 2 (Máx 3)
                declaration_heirs_file = st.file_uploader(
                    "Declaração de Herdeiros (máx. 10)",
                    type=["pdf"],
                    key="declaration_heirs_file",
                    accept_multiple_files=True,
                )
                # Arquivos do Agente 3 (Máx 3)
                identity_file = st.file_uploader(
                    "Carteira de Identidade (máx. 10)",
                    type=["pdf"],
                    key="identity_file",
                    accept_multiple_files=True,
                )
                # Arquivos do Agente 4 (Máx 3)
                proof_residence_file = st.file_uploader(
                    "Comprovante de Residência (máx. 10)",
                    type=["pdf"],
                    key="proof_residence_file",
                    accept_multiple_files=True,
                )
                uploaded_files_global = {
                    "death_certificate": get_valid_files(death_certificate_file),
                    "declaration_heirs": get_valid_files(declaration_heirs_file),
                    "identity_card": get_valid_files(identity_file),
                    "proof_residence": get_valid_files(proof_residence_file),
                }
                # Controle do botão: Desativa se não houver NENHUM arquivo
                btn_control = all(f is None for f in uploaded_files_global.values())
            elif selected_option == 7:
                # Módulo GFIP (Com sub-opções)
                sub_option = st.radio(
                    "Selecione o tipo de análise GFIP:",
                    # OPÇÕES ATUALIZADAS
                    [
                        "1. Classificação Geral",
                        "2. Verificação por CPF",
                        "3. Verificação por Nome",
                        "4. Comparação entre Documentos",  # <-- NOVA OPÇÃO
                    ],
                    key="gfip_sub_option",
                    horizontal=True,
                )
                # CÓDIGO DA SUB-OPÇÃO
                if sub_option.startswith("1"):
                    sub_option_code = 1
                elif sub_option.startswith("2"):
                    sub_option_code = 2
                elif sub_option.startswith("3"):
                    sub_option_code = 3
                else:
                    sub_option_code = (
                        4  # Novo código para 'Comparação entre Documentos'
                    )
                if sub_option_code == 4:
                    # LÓGICA PARA COMPARAÇÃO (Requer 2 arquivos)
                    st.subheader("Upload dos Arquivos GFIP para Comparação")
                    upload_file = st.file_uploader(
                        "Arquivo GFIP Principal (PDF)",
                        type=["pdf"],
                        key="arquivo_gfip_principal",
                    )
                    upload_file_comparacao = st.file_uploader(
                        "Arquivo Declaração do Contador (PDF)",
                        type=["pdf"],
                        key="arquivo_gfip_secundario",
                    )
                    # Controle do botão: Requer os dois arquivos
                    btn_control = (upload_file is None) or (
                        upload_file_comparacao is None
                    )
                else:
                    # LÓGICA PARA GERAL, CPF, NOME (Requer 1 arquivo)
                    upload_file = st.file_uploader(
                        "Arquivo GFIP (PDF)", type=["pdf"], key="arquivo_pre_analise"
                    )
                    if sub_option_code == 2:
                        # Campo para CPF (só aparece na opção 2)
                        cpf_busca = st.text_input(
                            "Digite o CPF para verificação (XXX.XXX.XXX-XX):",
                            key="cpf_busca_input",
                            max_chars=14,
                        )
                        # Controle do botão para CPF: Requer arquivo E CPF
                        btn_control = (upload_file is None) or (not cpf_busca)
                    elif sub_option_code == 3:
                        # Campo para NOME (opção 3)
                        nome_busca = st.text_input(
                            "Digite o NOME completo para verificação:",
                            key="nome_busca_input",
                        )
                        # Controle do botão para NOME: Requer arquivo E Nome
                        btn_control = (upload_file is None) or (not nome_busca)
                    else:  # sub_option_code == 1 (Geral)
                        # Controle do botão para Geral: Requer apenas o arquivo
                        btn_control = upload_file is None
            else:
                # Outros módulos (1, 2, 3, etc.) - um único arquivo
                upload_file = st.file_uploader(
                    "Arquivo", type=["pdf"], key="arquivo_pre_analise"
                )
                btn_control = upload_file is None
            # --- BOTÕES DE CONTROLE ---
            c1, c2, c3 = st.columns([3, 11, 2])
            with c1:
                botao = st.button("Processar", disabled=btn_control)
            with c3:
                if st.button("Limpar"):
                    clear_session_response()
                    reset_chat_state()
                    reset_response_id()
                    # Também limpa a instância do agente global
                    if "global_agent_instance" in st.session_state:
                        del st.session_state["global_agent_instance"]
                    st.rerun()
            # --- LÓGICA DE PROCESSAMENTO ---
            if botao:
                reset_chat_state()
                reset_response_id()
                with st.spinner("Processando..."):
                    config = {
                        "configurable": {
                            "thread_id": st.session_state[f"{AGENT_NAME}_thread_id"]
                        }
                    }
                    # Processamento dependendo da opção selecionada
                    if selected_option == 1:  # Tradução
                        response = DocumentProcessor(
                            upload_file, selected_option
                        ).process_documents(config)
                    elif selected_option == 2:  # Prontuário médico
                        response = MedicalRecordProcessor(
                            upload_file, selected_option
                        ).process_documents(config)
                    elif selected_option == 3:  # Termo de Rescisão
                        response = DocumentTermRecision(
                            upload_file, selected_option
                        ).process_documents(config)
                    elif selected_option == 4:  # Pré-análise com múltiplos documentos
                        # Cria e armazena a instância do agente global
                        global_agent = PreAnalysisGlobalAgent(uploaded_files_global)
                        st.session_state["global_agent_instance"] = global_agent
                        response = global_agent.process_all(config)
                        # Define doc_name para o log
                        doc_name = "múltiplos documentos/Pré-análise Global"
                    elif selected_option == 7:  # GFIP (Com sub-opções)
                        # PASSANDO O NOME DE BUSCA E O NOVO ARQUIVO DE COMPARAÇÃO
                        response = PreAnalysisGFIP(
                            upload_file,
                            selected_option,
                            sub_option_code,
                            cpf_busca,
                            nome_busca,
                            file_to_compare=upload_file_comparacao,  # <-- NOVO PARÂMETRO
                        ).process_documents(config)
                        doc_name = "GFIP"
                    else:
                        # Para outras opções futuras, usar DocumentProcessor como padrão
                        response = DocumentProcessor(
                            upload_file, selected_option
                        ).process_documents(config)
                    st.session_state["response"] = response
                    # LOG (Lógica segura de doc_name)
                    # Para as opções 1, 2, 3, 5, 6, 8 (que retornam dicionário único com 'result')
                    if (
                        selected_option not in [4, 7]
                        and response
                        and response.get("result")
                    ):
                        doc_name = response["result"].get(
                            "file_name", "documento único"
                        )
                    log_interaction(
                        agent_name=AGENT_NAME,
                        thread_id=st.session_state[f"{AGENT_NAME}_thread_id"],
                        response_id=get_response_id(),
                        user_question=f"Processamento do documento {doc_name}",
                        chatbot_response=f"Documento {doc_name} processado.",
                    )
            # --- SEÇÃO DE SAÍDA E EXIBIÇÃO ---
            response = None
            if "response" in st.session_state:
                response = st.session_state["response"]
                if response:
                    # Determinar a opção para exibição
                    current_option_key = st.session_state.get("seletor_modulo")
                    selected_option = option_dict.get(current_option_key, 1)
                    # Para o Módulo 7, determinar a sub_option para formatação correta
                    current_sub_option = st.session_state.get(
                        "gfip_sub_option", "1. Classificação Geral"
                    )
                    sub_option_code = (
                        1
                        if current_sub_option.startswith("1")
                        else (
                            2
                            if current_sub_option.startswith("2")
                            else (
                                3 if current_sub_option.startswith("3") else 4
                            )  # <-- ADICIONADO CÓDIGO 4
                        )
                    )
                    with st.container(border=True):
                        # ----------------------------------------------------
                        # MÓDULOS QUE EXIBEM TABELAS (2, 3, 4, 7)
                        # ----------------------------------------------------
                        if selected_option in [2, 3, 7]:
                            # Módulos com saída única em tabela (Prontuário, Rescisão, GFIP)
                            module_name = {
                                2: "Prontuário Médico",
                                3: "Documento de Rescisão",
                                7: "Planilha GFIP",
                            }.get(selected_option, "Dados")
                            # INÍCIO DA LÓGICA DE EXIBIÇÃO DO GFIP
                            if selected_option == 7:
                                # Ajusta o título para a sub-opção GFIP
                                if sub_option_code == 2:
                                    module_name = "Verificação de Funcionário (CPF)"
                                elif sub_option_code == 3:
                                    module_name = "Verificação de Funcionário (Nome)"
                                elif sub_option_code == 4:
                                    module_name = "Relatório de Comparação GFIP"
                                else:
                                    module_name = "Classificação Geral"
                                try:
                                    # LÓGICA PARA SUB-OPÇÕES 2 e 3 (Verificação)
                                    if sub_option_code in [2, 3]:
                                        # 1. Exibir Tabela Principal (extracted_data)
                                        extracted_data = response.get("extracted_data")
                                        if extracted_data:
                                            # Cria DataFrame limpo a partir do dicionário (ideal para Streamlit)
                                            df_display = pd.DataFrame([extracted_data])
                                            # Garante que CNPJ/CPF/Matrícula são strings para exibição na tela
                                            for col in [
                                                "CNPJ da empresa/estabelecimento",
                                                "CPF",
                                                "Matrícula",
                                            ]:
                                                if col in df_display.columns:
                                                    df_display[col] = df_display[
                                                        col
                                                    ].astype(str)
                                            st.subheader(
                                                f"📊 Dados Extraídos: **{module_name}**"
                                            )
                                            st.dataframe(
                                                df_display,
                                                hide_index=True,
                                                use_container_width=True,
                                            )
                                            # 2. Exibir Tabela de Duplicidade (duplicity_data)
                                            duplicity_data = response.get(
                                                "duplicity_data"
                                            )
                                            if duplicity_data:
                                                df_duplicidade = pd.DataFrame(
                                                    duplicity_data
                                                )
                                                st.subheader(f"⚠️ Tabela de Duplicidade")
                                                st.dataframe(
                                                    df_duplicidade,
                                                    hide_index=True,
                                                    use_container_width=True,
                                                )
                                            # 3. Botões de Download
                                            # No caso das sub-opções 2 e 3, 'result' é uma lista com 1 CSV (o da duplicação)
                                            result_files = response.get("result", [])
                                            for result_dict in result_files:
                                                file_name = result_dict["file_name"]
                                                st.download_button(
                                                    label=f"💾 Baixar CSV - {file_name.replace('_', ' ')}",
                                                    data=result_dict["csv_file"],
                                                    file_name=f"{file_name}.csv",
                                                    mime="text/csv",
                                                    key=f"download_{file_name}",
                                                )
                                                st.markdown("---")
                                    # LÓGICA PARA SUB-OPÇÃO 4 (Comparação)
                                    elif sub_option_code == 4:
                                        st.subheader(f"📊 Resultado: **{module_name}**")
                                        comparison_data = response.get(
                                            "comparison_data"
                                        )
                                        if comparison_data and isinstance(
                                            comparison_data, list
                                        ):
                                            df_comparison = pd.DataFrame(
                                                comparison_data
                                            )
                                            st.dataframe(
                                                df_comparison,
                                                hide_index=True,
                                                use_container_width=True,
                                            )
                                            # --- CORREÇÃO APLICADA AQUI ---
                                            # Botão de Download
                                            # Acessa o primeiro elemento da lista de resultados
                                            result_dict_comparacao = response.get(
                                                "result", [{}]
                                            )[0]
                                            comparison_csv_bytes = (
                                                result_dict_comparacao.get("csv_file")
                                            )
                                            file_name_comparacao = (
                                                result_dict_comparacao.get(
                                                    "file_name",
                                                    "Relatorio_Comparacao_GFIP",
                                                )
                                            )
                                            if comparison_csv_bytes:
                                                st.download_button(
                                                    label="💾 Baixar CSV - Relatório de Comparação",
                                                    data=comparison_csv_bytes,
                                                    file_name=f"{file_name_comparacao}.csv",
                                                    mime="text/csv",
                                                    key="download_comparacao_gfip",
                                                )
                                            else:
                                                st.warning(
                                                    "Não foi possível gerar o arquivo CSV de comparação. O relatório de comparação pode estar vazio."
                                                )
                                        else:
                                            # Mensagem de fallback (exibida quando o comparison_data é vazio/nulo)
                                            st.info(
                                                "Nenhuma diferença significativa encontrada ou o relatório de comparação está vazio."
                                            )
                                    # LÓGICA PARA SUB-OPÇÃO 1 (Geral)
                                    elif sub_option_code == 1:
                                        # CORREÇÃO APLICADA: Acessa o primeiro elemento da lista de resultados
                                        result_dict = response["result"][0]
                                        csv_data = result_dict["csv_file"].decode(
                                            "utf-8"
                                        )
                                        df = pd.read_csv(
                                            io.StringIO(csv_data), sep=";"
                                        )  # Adicionando sep=';' para leitura
                                        st.subheader(f"Dados Extraídos: {module_name}")
                                        st.dataframe(df, use_container_width=True)
                                        # Botão de download
                                        st.download_button(
                                            label="📊 Baixar CSV",
                                            data=result_dict[
                                                "csv_file"
                                            ],  # Usa o dicionário corrigido
                                            file_name=f"{result_dict['file_name']}.csv",  # Usa o dicionário corrigido
                                            mime="text/csv",
                                        )
                                except Exception as e:
                                    st.error(
                                        f"Erro ao processar dados de {module_name}: {str(e)}"
                                    )
                            else:
                                # Outros módulos (Prontuário, Rescisão) - Lógica original
                                try:
                                    csv_data = response["result"]["csv_file"].decode(
                                        "utf-8"
                                    )
                                    # Para Prontuário e Rescisão, a separação padrão deve ser usada
                                    df = pd.read_csv(io.StringIO(csv_data))
                                    st.subheader(f"Dados Extraídos: {module_name}")
                                    st.dataframe(df, use_container_width=True)
                                    # Botão de download
                                    st.download_button(
                                        label="📊 Baixar CSV",
                                        data=response["result"]["csv_file"],
                                        file_name=f"{response['result']['file_name']}.csv",
                                        mime="text/csv",
                                    )
                                except Exception as e:
                                    st.error(
                                        f"Erro ao processar dados de {module_name}: {str(e)}"
                                    )
                        elif selected_option == 4:  # Pré-análise múltiplos documentos
                            st.subheader("Relatório de Consistência Global")
                            # Achata o dicionário de resultados em uma lista plana para validação
                            all_results_flat = flatten_agent_results(response)
                            # Busca o primeiro resultado validado (para obter as flags globais)
                            first_valid_result = next(
                                (
                                    res
                                    for res in all_results_flat
                                    if isinstance(res, dict) and res.get("validated")
                                ),
                                None,
                            )
                            # Itera sobre o dicionário de listas para EXIBIÇÃO INDIVIDUAL
                            for agent_name, results_list in response.items():
                                if results_list and isinstance(results_list, list):
                                    # Itera sobre CADA DOCUMENTO processado pelo agente
                                    for result_state in results_list:
                                        if isinstance(result_state, dict):
                                            try:
                                                result = result_state.get("result", {})
                                                csv_bytes = result.get("csv_file")
                                                if csv_bytes:
                                                    # Manter a leitura do CSV com utf-8-sig e sep=';' para o Módulo 4
                                                    csv_data = csv_bytes.decode(
                                                        "utf-8-sig"
                                                    )
                                                    df = pd.read_csv(
                                                        io.StringIO(csv_data), sep=";"
                                                    )
                                                    # Nome do arquivo/documento individual:
                                                    file_name = result.get(
                                                        "file_name", agent_name
                                                    )
                                                    unique_key = f"download_csv_{agent_name}_{file_name}"
                                                    st.subheader(
                                                        f"Dados extraídos: **{file_name.replace('_', ' ').title()}**"
                                                    )
                                                    st.dataframe(
                                                        df, use_container_width=True
                                                    )
                                                    # Download Individual
                                                    st.download_button(
                                                        label=f"💾 Baixar CSV - {file_name.replace('_', ' ').title()}",
                                                        data=csv_bytes,
                                                        file_name=f"{file_name}.csv",
                                                        mime="text/csv",
                                                        key=unique_key,
                                                    )
                                            except Exception as e:
                                                st.error(
                                                    f"Erro ao processar dados de {agent_name} (documento individual): {str(e)}"
                                                )
                            if global_agent:
                                excel_bytes = global_agent.get_consolidated_excel()
                                if excel_bytes:  # Usa a nova variável
                                    st.markdown("---")
                                    st.download_button(
                                        label="Baixar Relatório CONSOLIDADO (Excel)",
                                        data=excel_bytes,
                                        file_name=f"Relatorio_Consolidado_PreAnalise_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key="download_consolidado_global",
                                    )
                                else:
                                    st.warning(
                                        "Não foi possível gerar o relatório consolidado em Excel."
                                    )
                        else:
                            # Outros agentes (tradução, etc.) - exibição de PDF
                            pdf_base64 = base64.b64encode(
                                response["result"]["file"]
                            ).decode("utf-8")
                            pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="670" height="1000" type="application/pdf"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)
                            st.download_button(
                                label="Baixar PDF",
                                data=response["result"]["file"],
                                file_name=response["result"]["file_name"],
                                mime="application/pdf",
                            )
                        st.session_state[f"{AGENT_NAME}_chat_history"].append(
                            {
                                "role": "assistant",
                                "content": doc_name,
                                "response_id": get_response_id(),
                            }
                        )
                        update_feedback(
                            agent_name=AGENT_NAME,
                            thread_id=st.session_state[f"{AGENT_NAME}_thread_id"],
                            response_id=get_response_id(),
                        )
                else:
                    st.warning("Ocorreu um erro no processamento do documento!")
    else:
        st.error(
            "Você não está autenticado. Por favor, faça login para acessar esta página."
        )
