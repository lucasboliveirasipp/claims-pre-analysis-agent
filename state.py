from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, TypedDict, Annotated
from pre_analysis_gfip_models import (
    AfastamentoNovoDocumento,
)


# Definição do estado do workflow
class WorkflowState(TypedDict):
    """Estado do workflow para processamento paralelo"""

    files: List[Dict]
    documents: List[Dict]
    result: Any
    start_time: float
    end_time: float
    elapsed_time: str


class MedicalRecordState(TypedDict):
    """Estado específico para processamento de prontuários médicos"""

    files: List[Dict]
    documents: List[Dict]
    extracted_data: List[Dict[str, str]]
    result: Any
    start_time: float
    end_time: float
    elapsed_time: str


class DocumentTermRecisionState(TypedDict):
    """Estado específico para a verificação da estrutura do documento de recisão"""

    documents: List[Dict]
    extracted_data: Dict[str, str]
    start_time: float
    result: Dict[str, Any]
    date_admission: List[Dict[str, str]]
    date_dismissal: List[Dict[str, str]]
    type_employment_contract: str
    reason_dismissal: str


class CarteiraIdentidadePreAnaliseState(TypedDict):
    files: List[Dict]
    start_time: float
    documents: List[Dict]
    extracted_data: Dict[str, str]
    rg: str
    cpf: str
    name: str
    result: Dict[str, Any]
    end_time: float
    elapsed_time: Optional[str]
    # CORREÇÃO: Adicionado para permitir a passagem do arquivo temporário
    temp_file: Dict[str, Any] | None


class DeathCertificateState(TypedDict):
    files: List[Dict]
    start_time: float
    documents: List[Dict]
    extracted_data: Dict[str, str]
    rg: str
    cpf: str
    name: str
    reason_of_death: str
    date_of_death: str
    autentication: str
    result: Dict[str, Any]
    end_time: float
    elapsed_time: Optional[str]
    # CORREÇÃO: Adicionado para permitir a passagem do arquivo temporário
    temp_file: Dict[str, Any] | None


class DeclarationOfHeirsState(TypedDict):
    files: List[Dict]
    start_time: float
    documents: List[Dict]
    extracted_data: Dict[str, str]
    rg: str
    cpf: str
    name: str
    autentication: str
    result: Dict[str, Any]
    end_time: float
    elapsed_time: Optional[str]
    # CORREÇÃO: Adicionado para permitir a passagem do arquivo temporário
    temp_file: Dict[str, Any] | None


class ProofResidenceState(TypedDict):
    documents: List[Dict]
    extracted_data: Dict[str, str]
    start_time: float
    result: Dict[str, Any]
    cpf: str
    name: str
    autentication: str
    emission_date: Optional[str]
    # CORREÇÃO: Adicionado para permitir a passagem do arquivo temporário
    temp_file: Dict[str, Any] | None


class DataGFIPState(TypedDict):
    files: List[Dict]
    extracted_data: Dict[str, str]
    start_time: float
    documents: List[Dict]
    result: Dict[str, Any]
    total_employees: str
    enterprise_name: str
    cnpj: str
    category: str


class FuncionarioGFIPState(TypedDict):
    files: List[Dict]
    start_time: float
    documents: List[Dict]
    cpf_busca: str
    nome_trabalhador: str
    matricula: str
    cpf: str
    categoria: str
    nome_empregador: str
    cnpj: str
    status_verificacao: str
    duplicidade: str
    extracted_data: Dict[str, str]
    result: Dict[str, Any]
    end_time: float
    elapsed_time: Optional[str]


class ComparacaoDocState(TypedDict):
    """Estado para a nova Sub-opção 4: Comparação de Documentos (GFIP vs. Afastamento)."""

    files_gfip: List[Dict]  # Documento 1 (GFIP - arquivos originais)
    files_afastamento: List[
        Dict
    ]  # Documento 2 (Novo Documento/Afastamento - arquivos originais)
    documents_gfip: List[Dict]  # Documento 1 (GFIP - texto extraído/processado)
    documents_afastamento: List[
        Dict
    ]  # Documento 2 (Novo Documento - texto extraído/processado)
    # Extração de todos os funcionários GFIP (apenas Nome/CPF) para busca/comparação.
    # Usaremos uma lista de dicionários com as chaves NOME, CPF.
    gfip_employees_list: List[Dict[str, Any]]
    # Extração de dados do novo documento. Lista de objetos AfastamentoNovoDocumento ou seus dicionários.
    afastamento_data: List[Dict[str, Any]]
    # Resultado Consolidado (Lista de dicionários formatados para CSV, usando ComparacaoResult.to_csv_dict)
    result_comparacao: List[Dict[str, Any]]
    # Metadados de resultado final (geralmente o arquivo CSV)
    result: Any
    start_time: float
    end_time: float
    elapsed_time: Optional[str]
