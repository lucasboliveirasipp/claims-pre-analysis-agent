import io
import pandas as pd
from uuid import uuid4
from typing import Dict, Any, List, Tuple
from .pre_analysis_death_certificate import PreAnalysisDeathCertificate
from .pre_analysis_declaration_heirs import PreAnalysisDeclarationHeirs
from .pre_analysis_identity import PreAnalysisIdentityCard
from .pre_analysis_proof_residence import PreAnalysisProofResidence


class PreAnalysisGlobalAgent:
    """
    Agente global para pré-análise de documentos.
    Projetado para gerar DataFrames separados por cada documento INDIVIDUAL.
    """

    AGENT_CLASSES = {
        "death_certificate": PreAnalysisDeathCertificate,
        "declaration_heirs": PreAnalysisDeclarationHeirs,
        "identity_card": PreAnalysisIdentityCard,
        "proof_residence": PreAnalysisProofResidence,
    }
    COMMON_FIELDS = ["name", "cpf"]

    def __init__(self, files_dict: Dict[str, List[Any]]):
        self.files_dict = files_dict
        self.results: Dict[str, List[Dict[str, Any]]] = {}
        self.agent_dfs: Dict[str, List[pd.DataFrame]] = {
            key: [] for key in self.AGENT_CLASSES.keys()
        }

    def process_all(self, config=None):
        """Processa todos os PDFs enviados e popula self.agent_dfs com DataFrames individuais."""
        if config is None:
            config = {"configurable": {"thread_id": str(uuid4())}}
        validation_fields_map = {}
        for key, agent_class in self.AGENT_CLASSES.items():
            files = self.files_dict.get(key)
            if files and len(files) > 0:
                agent = agent_class(files, option=4)
                results_list = agent.process_documents(config)
                if not isinstance(results_list, list):
                    results_list = [results_list] if results_list is not None else []
                self.results[key] = results_list
                for i, res in enumerate(results_list):
                    if not isinstance(res, dict):
                        print(
                            f"Aviso: Resultado do agente {key} índice {i} não é um dicionário de estado."
                        )
                        continue

                    if i == 0:
                        validation_fields_map[key] = {
                            field: res.get(field) or "null"
                            for field in self.COMMON_FIELDS
                        }

                    csv_bytes = res.get("result", {}).get("csv_file")
                    if csv_bytes:
                        try:
                            csv_data = csv_bytes.decode("utf-8-sig")
                            df = pd.read_csv(io.StringIO(csv_data), sep=";")
                            self.agent_dfs[key].append(df)
                        except Exception as e:
                            print(
                                f"Erro ao converter CSV para DataFrame para {key} índice {i}: {e}"
                            )
            else:
                self.results[key] = []
        self._validate_common_fields_from_map(validation_fields_map)
        return self.results

    def _validate_common_fields_from_map(self, agent_values: Dict[str, Dict[str, str]]):
        """Compara campos comuns e adiciona flag 'validated' ao primeiro resultado de cada tipo."""
        validation = {}
        for field in self.COMMON_FIELDS:
            values = [
                v.get(field)
                for v in agent_values.values()
                if isinstance(v, dict) and v.get(field) not in ["null", None, "None"]
            ]
            validation[field] = all(v == values[0] for v in values) if values else True
        for key, results_list in self.results.items():
            if (
                results_list
                and isinstance(results_list, list)
                and len(results_list) > 0
            ):
                if isinstance(results_list[0], dict):
                    results_list[0]["validated"] = validation
            elif isinstance(results_list, dict):
                results_list["validated"] = validation

    def get_csv(self, agent_key: str, index: int = 0):
        """Retorna CSV do documento individual especificado como bytes."""
        res_list = self.results.get(agent_key)
        if res_list and isinstance(res_list, list) and len(res_list) > index:
            res = res_list[index]
            if isinstance(res, dict):
                csv_data = res.get("result", {}).get("csv_file")
                return csv_data
        return None

    def get_consolidated_excel(self):
        """
        Gera um único arquivo Excel (xlsx) com uma aba para cada tipo de agente,
        concatenando os DataFrames individuais daquele agente.
        Usa o engine 'openpyxl' para evitar a dependência de 'xlsxwriter'.
        """
        if not self.agent_dfs:
            return None

        validation_flags = None
        for res_list in self.results.values():
            if res_list and isinstance(res_list, list) and len(res_list) > 0:
                first_res = res_list[0]
                if isinstance(first_res, dict) and first_res.get("validated"):
                    validation_flags = first_res["validated"]
                    break
        output = io.BytesIO()

        try:
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                for agent_name, df_list in self.agent_dfs.items():
                    if not df_list:
                        continue

                    try:
                        consolidated_agent_df = pd.concat(
                            df_list, ignore_index=True, join="outer"
                        )
                    except Exception as e:
                        print(f"Erro ao concatenar DataFrames para {agent_name}: {e}")
                        continue
                    if validation_flags:
                        for field, is_valid in validation_flags.items():
                            status = "OK" if is_valid else "ERRO"
                            consolidated_agent_df[f"Consistencia_{field.upper()}"] = (
                                status
                            )
                    sheet_name = agent_name.replace("_", " ").title()
                    # Trata nomes longos para caber no limite de 31 caracteres do Excel
                    sheet_name = sheet_name.replace(
                        "Declaration Heirs", "Declaração Herdeiros"
                    )
                    sheet_name = sheet_name.replace("Identity Card", "Identidade")
                    sheet_name = sheet_name.replace(
                        "Proof Residence", "Comprovante Residência"
                    )
                    sheet_name = sheet_name.replace(
                        "Death Certificate", "Certidão de Óbito"
                    )

                    # Escreve a aba
                    consolidated_agent_df.to_excel(
                        writer, sheet_name=sheet_name, index=False
                    )
        except ImportError:
            print(
                "Erro: O engine 'openpyxl' não está instalado. Não é possível gerar o Excel."
            )
            return None
        output.seek(0)
        return output.getvalue()
