import pandas as pd
import io
import json
from typing import List, Dict, Any
from langgraph.graph import END, StateGraph, START
from langchain_core.prompts import PromptTemplate
from .tools import calc_time_counter, create_temp_files, extract_pages_from_pdf_di, get_time_counter
from .prompts import medical_record_prompt
from .config import gpt_4_1_mini
from .state import MedicalRecordState
from .medical_models import ProntuarioMedico
 
class MedicalRecordProcessor:
    def __init__(self, files, option: int):
        """
        Inicializa o processador de prontuários médicos
       
        Args:
            files: Arquivo ou lista de arquivos para processar
            option: Opção selecionada (módulo)
        """
        # Garantir que files seja sempre uma lista
        if not isinstance(files, list):
            self.files = [files]
        else:
            self.files = files
        self.option = option
        self.workflow = self._setup_medical_workflow()
 
    def _setup_medical_workflow(self):
        """Configura o fluxo específico para prontuários médicos"""
        workflow = StateGraph(MedicalRecordState)
       
        workflow.add_node("extraction_node", self.extraction_node)
        workflow.add_node("analysis_node", self.analysis_node)
        workflow.add_node("format_node", self.format_node)
 
        workflow.add_edge(START, "extraction_node")
        workflow.add_edge("extraction_node", "analysis_node")
        workflow.add_edge("analysis_node", "format_node")
        workflow.add_edge("format_node", END)
       
        return workflow.compile()
 
    def process_documents(self, config):
        """Processa os documentos médicos"""
        result = self.workflow.invoke({
            "files": self.files,
            "start_time": get_time_counter()
        }, config=config)
        return result
 
    def extraction_node(self, state: MedicalRecordState):
        """Extrai texto dos prontuários médicos usando Document Intelligence"""
        temp_files = create_temp_files(self.files)
        documents = []
       
        for f in temp_files:
            # Usar sempre Document Intelligence para máxima precisão
            documents.append(extract_pages_from_pdf_di(f['metadata']['temp_name'], f['metadata']['original_name']))
       
        return {"documents": documents}
 
    def analysis_node(self, state: MedicalRecordState):
        """Analisa o conteúdo médico e extrai informações estruturadas usando Pydantic"""
        documents = state["documents"]
       
        # Consolidar todo o texto primeiro
        all_text = ""
        for document in documents:
            for page in document:
                all_text += page["text"] + "\n\n"
       
        # Usar structured output com Pydantic diretamente
        medical_template = PromptTemplate(template=medical_record_prompt, input_variables=["texto"])
        structured_llm = gpt_4_1_mini.with_structured_output(ProntuarioMedico)
        medical_chain = medical_template | structured_llm
       
        # Fazer uma única chamada para todo o conteúdo - retorna objeto Pydantic diretamente
        prontuario = medical_chain.invoke({"texto": all_text})
        print(f"DEBUG - Objeto Pydantic criado diretamente: {prontuario}")
       
        # Converter para formato CSV usando o método to_csv_dict
        csv_data = prontuario.to_csv_dict()
        print(f"DEBUG - CSV data: {csv_data}")
       
        return {"extracted_data": csv_data}
 
    def format_node(self, state: MedicalRecordState):
        """Formata o resultado final em CSV"""
        extracted_data = state["extracted_data"]
        print(f"DEBUG - Dados recebidos no format_node: {extracted_data}")
       
        time_counter = calc_time_counter(state['start_time'])
       
        # Obter nome do arquivo original
        file_name = "Analise_Prontuario"
        if state.get('files'):
            try:
                # Verificar se é uma lista e tem elementos
                if isinstance(state['files'], list) and len(state['files']) > 0:
                    original_name = getattr(state['files'][0], 'name', 'documento')
                elif hasattr(state['files'], 'name'):
                    # Se é um único arquivo com atributo name
                    original_name = state['files'].name
                else:
                    original_name = 'documento'
               
                if original_name and original_name != 'documento':
                    file_name = f"Analise_Prontuario_{original_name.replace('.pdf', '')}"
            except Exception:
                # Fallback em caso de erro
                file_name = "Analise_Prontuario"
       
        # Criar DataFrame com as 3 colunas específicas
        # extracted_data já é um dicionário do método to_csv_dict()
        df = pd.DataFrame([extracted_data])
        print(f"DEBUG - DataFrame criado: {df}")
        print(f"DEBUG - Colunas do DataFrame: {df.columns.tolist()}")
       
        # Garantir que as colunas estejam na ordem correta
        column_order = ["Nome do Paciente", "Causa da Internação", "Período da Internação"]
        df = df.reindex(columns=column_order, fill_value="")
        print(f"DEBUG - DataFrame final: {df}")
       
        # Gerar CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8')
        csv_content = csv_buffer.getvalue()
        print(f"DEBUG - Conteúdo CSV: {csv_content}")
       
        return {
            "result": {
                "csv_file": csv_content.encode('utf-8'),
                "file_name": file_name
            },
            "end_time": time_counter['end_time'],
            "elapsed_time": time_counter['elapsed_time']
        }