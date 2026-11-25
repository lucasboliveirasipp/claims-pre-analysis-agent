from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class GFIP(BaseModel):
    total_employees: Optional[str] = Field(None, title="Numero Total de Funcionários")
    enterprise_name: Optional[str] = Field(None, title="Nome Empregador")
    cnpj: Optional[str] = Field(None, title="CNPJ do Estabelecimento")
    category: Optional[str] = Field(None, title="Categoria do Empregado")

    def to_csv_dict(self) -> dict:

        data = self.model_dump(exclude_none=True)

        return {
            "Numero Total de Funcionários": data.get("total_employees"),
            "Nome Empregador": data.get("enterprise_name"),
            "CNPJ do Estabelecimento": data.get("cnpj"),
            "Categoria do Empregado": data.get("category"),
        }

    class Config:
        validate_by_name = True


class FuncionarioGFIP(BaseModel):
    """Modelo para extrair detalhes de um funcionário específico em GFIP."""

    nome_trabalhador: Optional[str] = Field(None, title="Nome Trabalhador")
    matricula: Optional[str] = Field(None, title="Matrícula")
    cpf: Optional[str] = Field(None, title="CPF")
    categoria: Optional[str] = Field(None, title="Categoria")
    nome_empregador: Optional[str] = Field(None, title="Nome Empregador")
    cnpj: Optional[str] = Field(None, title="CNPJ da empresa/estabelecimento")
    status_verificacao: Optional[str] = Field(None, title="Status da Verificação")
    duplicidade: Optional[str] = Field(None, title="Duplicidade de Nome")

    def to_csv_dict(self) -> dict:

        data = self.model_dump(exclude_none=True)

        """Retorna os dados no formato de dicionário para criação do DataFrame CSV."""
        return {
            "Nome Trabalhador": data.get("nome_trabalhador"),
            "Matrícula": data.get("matricula"),
            "CPF": data.get("cpf"),
            "Categoria": data.get("categoria"),
            "Nome Empregador": data.get("nome_empregador"),
            "CNPJ da empresa/estabelecimento": data.get(
                "cnpj"
            ),  # Adicionado CNPJ aqui para completar o dict
            "Status da Verificação": data.get("status_verificacao"),
            "Duplicidade de Nome": data.get("duplicidade"),
        }

    class Config:
        validate_by_name = True


class FuncionariosGFIPList(BaseModel):
    """Modelo para extrair UMA LISTA de todos os funcionários e os dados de cabeçalho do documento."""

    funcionarios: List[FuncionarioGFIP] = Field(
        ...,
        description="Lista de todos os registros de trabalhadores encontrados no corpo tabular do documento.",
    )
    nome_empregador: Optional[str] = Field(None, title="Nome Empregador")
    cnpj: Optional[str] = Field(None, title="CNPJ da empresa/estabelecimento")


class FuncionarioNomeCpf(BaseModel):
    """Modelo simplificado para extrair apenas nome e CPF da GFIP."""

    NOME: Optional[str] = Field(
        None, description="Nome completo do trabalhador na GFIP."
    )
    CPF: Optional[str] = Field(None, description="CPF do trabalhador na GFIP.")

    class Config:
        validate_by_name = True


class FuncionariosNomeCpfList(BaseModel):
    """Container para uma lista de Nome/CPF extraída da GFIP."""

    funcionarios: List[FuncionarioNomeCpf] = Field(
        ...,
        description="Lista de todos os trabalhadores, contendo Nome e CPF, encontrados no documento GFIP.",
    )


class AfastamentoNovoDocumento(BaseModel):
    """Modelo para extrair dados de afastamento do Novo Documento (Declaração Contador)."""

    NOME: Optional[str] = Field(
        None, title="Nome Trabalhador (Afastamento)", alias="nome_trabalhador"
    )
    TIPO_AFASTAMENTO: Optional[str] = Field(
        None, title="Tipo de Afastamento", alias="tipo_afastamento"
    )
    DATA_AFASTAMENTO: Optional[str] = Field(
        None, title="Data de Afastamento", alias="data_afastamento"
    )

    def to_csv_dict(self) -> dict:
        data = self.model_dump(exclude_none=True, by_alias=True)
        return {
            "Nome Trabalhador (Afastamento)": data.get("nome_trabalhador"),
            "Tipo de Afastamento": data.get("tipo_afastamento"),
            "Data de Afastamento": data.get("data_afastamento"),
        }

    class Config:
        validate_by_name = True
        populate_by_name = True


# Modelo que o LLM Structured Output irá usar para o Documento 2 (Declaração Contador)
class ListaAfastamentos(BaseModel):
    """Container para a lista completa de afastamentos extraídos do Documento de Afastamento."""

    afastamentos: List[AfastamentoNovoDocumento] = Field(
        ...,
        description="Lista de todos os registros de afastamento, incluindo nome, tipo e data, encontrados no documento.",
    )


class ComparacaoResult(BaseModel):
    """Modelo consolidado para o resultado da comparação."""

    nome_trabalhador: Optional[str] = Field(None, title="Nome Trabalhador")
    cpf_gfip: Optional[str] = Field(None, title="CPF (GFIP)")
    matricula_gfip: Optional[str] = Field(None, title="Matrícula (GFIP)")
    tipo_afastamento: Optional[str] = Field(None, title="Tipo de Afastamento")
    data_afastamento: Optional[str] = Field(None, title="Data de Afastamento")
    status_comparacao: Optional[str] = Field(
        None,
        title="Status da Comparação",
        description="Indica se o nome foi encontrado em ambos os documentos (Ex: 'Match' ou 'Apenas GFIP' ou 'Apenas Afastamento')",
    )

    def to_csv_dict(self) -> dict:
        data = self.model_dump(exclude_none=True)
        return {
            "Nome Trabalhador": data.get("nome_trabalhador"),
            "CPF (GFIP)": data.get("cpf_gfip"),
            "Matrícula (GFIP)": data.get("matricula_gfip"),
            "Tipo de Afastamento": data.get("tipo_afastamento"),
            "Data de Afastamento": data.get("data_afastamento"),
            "Status da Comparação": data.get("status_comparacao"),
        }

    class Config:
        validate_by_name = True
