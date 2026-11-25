from pydantic import BaseModel, Field
from typing import Optional, List

class DocumentoRecisao(BaseModel):
    date_admission: Optional[str] = Field(None, description="Data de Admissão")
    date_dismissal: Optional[str] = Field(None, description="Data do Afastamento")
    type_employment_contract: Optional[str] = Field(None, description="Tipo do Contrato")
    reason_dismissal: Optional[str] = Field(None, description="Causa do Afastamento")


    def to_csv_dict(self) -> dict:
        return {
            "Data de Admissão": self.date_admission or "",
            "Data de Afastamento": self.date_dismissal or "",
            "Tipo de Contrato": self.type_employment_contract or "",
            "Causa do Afastamento": self.reason_dismissal or ""
        }
