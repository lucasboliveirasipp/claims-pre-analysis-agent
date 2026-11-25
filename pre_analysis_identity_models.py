from pydantic import BaseModel, Field
from typing import Optional, Dict

class CarteiraIdentidade(BaseModel):
    """Estrutura simplificada da carteira de identidade a ser autenticada"""
    rg: Optional[str] = Field(None, alias="rg_individuo", description="RG do indivíduo")
    cpf: Optional[str] = Field(None, alias="cpf_individuo", description="CPF do usuário")
    name: Optional[str] = Field(None, alias="nome_individuo", description="Nome do indivíduo")

    def to_csv_dict(self) -> Dict[str, str]:
        """Converte o modelo Pydantic para um dicionário para o CSV"""
        return {
            "Nome do Indivíduo": self.name or "",
            "RG do Indivíduo": self.rg or "",
            "CPF do Indivíduo": self.cpf or ""
        }

    class Config:
        allow_population_by_field_name = True  # Para compatibilidade com V1