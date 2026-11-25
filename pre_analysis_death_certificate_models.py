from pydantic import BaseModel, Field
from typing import Optional, Dict

class CertidaoDeObito(BaseModel):
    """Estrutura simplificada da certidão de óbito a ser autenticada"""
    rg: Optional[str] = Field(None, alias="rg_individuo", description="RG do declarante")
    cpf: Optional[str] = Field(None, alias="cpf_individuo", description="CPF do declarante")
    name: Optional[str] = Field(None, alias="nome_individuo", description="Nome do declarante")
    name_deceased: Optional[str] = Field(None, alias="nome_falecido", description="Nome do falecido")
    cpf_deceased: Optional[str] = Field(None, alias="cpf_falecido", description="CPF do falecido")
    reason_of_death: Optional[str] = Field(None, alias="causa_da_morte", description="Causa da morte")
    date_of_death: Optional[str] = Field(None, description="Data do Óbito")
    autentication: Optional[str] = Field(None, alias="autenticacao_documento", description="Autenticação do Documento")


    def to_csv_dict(self) -> Dict[str, str]:
        """Converte o modelo Pydantic para um dicionário para o CSV"""
        return {
            "Nome do Declarante": self.name or "",
            "RG do Declarante": self.rg or "",
            "CPF do Declarante": self.cpf or "",
            "Nome do Falecido": self.name_deceased or "",
            "CPF do Falecido": self.cpf_deceased or "",
            "Causa da Morte": self.reason_of_death or "",
            "Data do Óbito": self.date_of_death or "",
            "Autenticidade": self.autentication or ""
        }

    class Config:
        allow_population_by_field_name = True  # Para compatibilidade com V1