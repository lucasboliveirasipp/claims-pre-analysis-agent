from typing import List, Dict, Any
from langgraph.graph import END, StateGraph, START
from langchain_core.prompts import PromptTemplate
import concurrent.futures
from .tools import calc_time_counter, create_temp_files, criar_pdf_html, extract_pages_from_pdf, extract_pages_from_pdf_di, get_time_counter, has_text
from .prompts import translator_prompt
from .config import gpt_4_1_mini
from .state import WorkflowState

class DocumentProcessor:
    def __init__(self, files: List, module):
        """
        Inicializa o processador de documentos
        
        Args:
            doc_files: Lista de caminhos para arquivos ou objetos de arquivo            
        """        
        self.files = files
        self.module = module
        self.workflow = self._setup_translate()

    def _setup_translate(self):
        """Configura o fluxo de trabalho para processamento paralelo"""
        workflow = StateGraph(WorkflowState)    
        workflow.add_node("extraction_node", self.extraction_node)
        workflow.add_node("translate_node", self.translate_node)

        workflow.add_edge(START, "extraction_node")        
        workflow.add_edge("extraction_node", "translate_node")
        workflow.add_edge("translate_node", END)
        return workflow.compile()
    
    def process_documents(self, config):
        
        # Invocar o workflow para processamento paralelo
        result = self.workflow.invoke({
            "files": self.files,
            "start_time": get_time_counter()
        }, config=config)
        
        return result 
    
    def extraction_node(self, state: WorkflowState):        
        temp_files = create_temp_files(self.files)
        documents = []
        for f in temp_files:
                if has_text(f['metadata']['temp_name']):            
                    documents.append(extract_pages_from_pdf(f['metadata']['temp_name'], f['metadata']['original_name']))                    
                else:
                    documents.append(extract_pages_from_pdf_di(f['metadata']['temp_name'], f['metadata']['original_name']))
        return {"documents": documents}
    
    def translate_node(self, state: WorkflowState):        
        def build_book(translator_chain, page):
            result = translator_chain.invoke({"texto": page["text"]})                 
            return {
                "text": result.content,
                "metadata": {
                    "document_name": page["metadata"]["document_name"],
                    "page_number": page["metadata"]["page_number"],
                    "document_type": "pdf"
                }
            }

        documents = state["documents"]

        translator_template = PromptTemplate(template=translator_prompt, input_variables=["texto"])
    
        translator_chain = translator_template | gpt_4_1_mini
        
        book = []
        futures = []  
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:  
            for document in documents:
                for page in document:
                    futures.append(executor.submit(build_book, translator_chain, page))  
                    
                for f in concurrent.futures.as_completed(futures):  
                    book.append(f.result())    
        

        ordened_book = sorted(book, key=lambda x: x["metadata"]["page_number"])  

        pdf_bytes = criar_pdf_html(ordened_book)

        time_counter = calc_time_counter(state['start_time'])
        return {
                "result": 
                    {
                        "file": pdf_bytes, 
                        "file_name": book[0]["metadata"]["document_name"]
                    }, 
                "end_time": time_counter['end_time'], 
                "elapsed_time": time_counter['elapsed_time']
                }