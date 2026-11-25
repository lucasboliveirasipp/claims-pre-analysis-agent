from pydantic import BaseModel, Field
from typing import Optional, Dict

class ComprovanteResidencia(BaseModel):
    """Estrutura simplificada da certidão de óbito a ser autenticada"""
    cpf: Optional[str] = Field(None, alias="cpf_individuo", description="CPF do indivíduo")
    name: Optional[str] = Field(None, alias="nome_individuo", description="Nome do indivíduo")
    emission_date: Optional[str] = Field(None, description="Data de Emissão")
    autentication: Optional[str] = Field(None, alias="autenticacao_documento", description="Autenticação do Documento")

    def to_csv_dict(self) -> Dict[str, str]:
        """Converte o modelo Pydantic para um dicionário para o CSV"""
        return {
            "Nome do indivíduo": self.name or "",
            "CPF do indivíduo": self.cpf or "",
            "Data de Emissão": self.emission_date or "",
            "Autenticação do Documento": self.autentication or ""
        }

    class Config:
        allow_population_by_field_name = True  # Para compatibilidade com V1