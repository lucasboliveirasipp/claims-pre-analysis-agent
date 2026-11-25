from pydantic import BaseModel, Field
from typing import Optional, List, Dict
 
class Herdeiro(BaseModel):
    name: Optional[str] = Field(None, alias="nome_individuo")
    rg: Optional[str] = Field(None, alias="rg_individuo")
    cpf: Optional[str] = Field(None, alias="cpf_individuo")
    autentication: Optional[str] = Field(None, alias="autenticacao_documento")
 
    def to_csv_dict(self) -> Dict[str, str]:
        return {
            "Nome do Indivíduo": self.name or "",
            "RG do Indivíduo": self.rg or "",
            "CPF do Indivíduo": self.cpf or "",
            "Autenticação do Documento": self.autentication or ""
        }
 
class DeclaracaoHerdeiros(BaseModel):
    heirs: List[Herdeiro] = Field(default_factory=list)