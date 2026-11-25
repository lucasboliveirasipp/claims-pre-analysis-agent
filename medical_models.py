from pydantic import BaseModel, Field
from typing import Optional, List

class ProntuarioMedico(BaseModel):
    """Estrutura simplificada do prontuário médico para extração específica"""
    nome_paciente: Optional[str] = Field(None, description="Nome completo do paciente")
    periodo_internacao: Optional[str] = Field(None, description="Período de internação (data início - data fim ou duração)")
    causa_internacao: Optional[str] = Field(None, description="Causa ou motivo da internação")

    def to_csv_dict(self) -> dict:
        """Converte o modelo Pydantic para um dicionário para o CSV"""
        return {
                "Nome do Paciente": self.nome_paciente or "",
            "Causa da Internação": self.causa_internacao or "",
            "Período da Internação": self.periodo_internacao or ""
        }