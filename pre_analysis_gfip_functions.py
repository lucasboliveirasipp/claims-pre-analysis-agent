import pandas as pd
import io
import json
import re
from typing import List, Dict, Any, Tuple
import unicodedata


def clean_value(val):
    """Garante que None, 'NULO', 'NULL' e strings vazias retornem ''."""
    if val is None:
        return ""
    val_str = str(val).strip()
    if val_str.upper() in ["NULO", "NULL", "NONE", "N/A"]:
        return ""
    return val_str.replace("\n", " ")


def normalize_text_for_search(text: str) -> str:
    """Remove acentos, pontuações, hífens e espaços extras para busca robusta."""
    if not isinstance(text, str):
        return ""
    # 1. Normalização Unicode e remoção de acentos
    normalized_text = (
        unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    )
    # 2. Remoção agressiva de caracteres que não sejam letras (a-z), números (0-9) ou espaços
    # Isso elimina pontos, vírgulas, hífens, apóstrofos, etc.
    cleaned_text = re.sub(r"[^a-zA-Z0-9\s]", "", normalized_text)
    # 3. Remoção de espaços duplicados e conversão para maiúsculo
    final_text = re.sub(r"\s+", "", cleaned_text).strip().upper()
    return final_text


def extract_gfip_info_regex(text: str) -> Tuple[str, str, str]:
    """Extração via Regex otimizada para cabeçalho GFIP (mantida original do usuário)."""
    enterprise_name = "null"
    cnpj = "null"
    total_employees = "null"
    cnpj_pattern = r"(?:CNPJ\s*/\s*CEI|Estabelecimento)\s*[:\s\n]*((?:\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})|(?:\d{14}))"
    cnpj_match = re.search(cnpj_pattern, text, re.IGNORECASE | re.DOTALL)
    if cnpj_match:
        cnpj_val = cnpj_match.group(1).strip()
        if cnpj_val:
            cnpj = cnpj_val
    if cnpj == "null":
        fallback_cnpj_pattern = r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})"
        fallback_cnpj_match = re.search(fallback_cnpj_pattern, text)
        if fallback_cnpj_match:
            cnpj = fallback_cnpj_match.group(1)
    enterprise_pattern = r"(?:Nome Empregador)\s*[:\s\n]+([A-ZÀ-ÿ\s\.,\d&-]+)(?:\n\s*(CNPJ|Qtd|Endereço)|\Z)"
    enterprise_match = re.search(enterprise_pattern, text, re.IGNORECASE | re.DOTALL)
    if enterprise_match:
        name_capture = enterprise_match.group(1).strip()
        name_capture = re.sub(r"\s+", " ", name_capture)
        if "Qtd Trabalhadores" not in name_capture:
            enterprise_name = name_capture
    employees_pattern = r"(?:Qtd Trabalhadores FGTS).*?(\d+)"
    employees_match = re.search(employees_pattern, text, re.IGNORECASE | re.DOTALL)
    if employees_match:
        total_employees = employees_match.group(1).strip()
    return total_employees, enterprise_name, cnpj


def extract_all_cnpjs_and_prioritize(text: str) -> str:
    cnpj_pattern_capture = (
        r"((?:\d{2}[\.\s\-]?\d{3}[\.\s\-]?\d{3}[\/\s\-]?\d{4}[\-\s\.]?\d{2}))"
    )
    # 1. Tenta encontrar CNPJ do EMPREGADOR/EMITENTE por RÓTULO (Prioridade Matriz/0001)
    matriz_label_pattern = r"(?:Empregador|Emitida por).*?" + cnpj_pattern_capture
    matriz_label_match = re.search(
        matriz_label_pattern, text, re.IGNORECASE | re.DOTALL
    )
    if matriz_label_match:
        cnpj_matriz_rotulo_bruto = matriz_label_match.group(1)
        cnpj_matriz_rotulo_limpo = re.sub(r"[\.\-\/\s\n]", "", cnpj_matriz_rotulo_bruto)
        if len(cnpj_matriz_rotulo_limpo) == 14:
            print(
                f"DEBUG FINAL REGEX: CNPJ Empregador/Matriz ENCONTRADO POR RÓTULO: {cnpj_matriz_rotulo_limpo}"
            )
            return cnpj_matriz_rotulo_limpo
    # 2. Fallback Heurístico para todos os CNPJs
    raw_cnpjs = re.findall(cnpj_pattern_capture, text)
    cnpjs_unicos = []
    for raw_cnpj in raw_cnpjs:
        cnpj_limpo = re.sub(r"[\.\-\/\s\n]", "", raw_cnpj)
        if len(cnpj_limpo) == 14 and cnpj_limpo not in cnpjs_unicos:
            cnpjs_unicos.append(cnpj_limpo)
    cnpj_matriz_fallback = None
    for c in cnpjs_unicos:
        # Se for o 0002-36, retorna (Próxima melhor opção se Matriz falhar)
        if not c.endswith("0001"):
            print(
                f"DEBUG FINAL REGEX: CNPJ Filial HEURÍSTICO (NÃO 0001) ENCONTRADO: {c}"
            )
            return c
        # Armazena o primeiro 0001 como fallback (último recurso)
        elif c.endswith("0001") and cnpj_matriz_fallback is None:
            cnpj_matriz_fallback = c
    if cnpj_matriz_fallback:
        print(
            f"DEBUG FINAL REGEX: Retornando Matriz (0001) como Fallback Geral: {cnpj_matriz_fallback}"
        )
        return cnpj_matriz_fallback
    return None


def identify_duplicity(employees_list: List[Dict[str, str]]) -> List[Dict[str, str]]:
    name_to_cpf: Dict[str, str] = {}
    cpf_to_name: Dict[str, str] = {}
    duplicity_list: List[Dict[str, Any]] = []  # Alterado para Any para incluir Motivo
    for emp in employees_list:
        name = clean_value(emp.get("Nome Trabalhador", "")).upper()
        cpf = clean_value(emp.get("CPF", ""))
        if not name or not cpf:
            continue
        # Conflito 1: Mesmo Nome, CPF Diferente
        if name in name_to_cpf and name_to_cpf[name] != cpf:
            # Adiciona o novo
            new_entry = {**emp, "Motivo": "Duplicidade de Nome (CPFs diferentes)"}
            if new_entry not in duplicity_list:
                duplicity_list.append(new_entry)
            # Adiciona o existente
            original = next(
                (
                    e
                    for e in employees_list
                    if clean_value(e.get("CPF", "")) == name_to_cpf[name]
                ),
                None,
            )
            if original:
                original_entry = {
                    **original,
                    "Motivo": "Duplicidade de Nome (CPFs diferentes)",
                }
                if original_entry not in duplicity_list:
                    duplicity_list.append(original_entry)
        name_to_cpf[name] = cpf
        # Conflito 2: Mesmo CPF, Nome Diferente
        if cpf in cpf_to_name and cpf_to_name[cpf] != name:
            # Adiciona o novo
            new_entry = {**emp, "Motivo": "Duplicidade de CPF (Nomes diferentes)"}
            if new_entry not in duplicity_list:
                duplicity_list.append(new_entry)
            # Adiciona o existente
            original = next(
                (
                    e
                    for e in employees_list
                    if clean_value(e.get("Nome Trabalhador", "")).upper()
                    == cpf_to_name[cpf]
                ),
                None,
            )
            if original:
                original_entry = {
                    **original,
                    "Motivo": "Duplicidade de CPF (Nomes diferentes)",
                }
                if original_entry not in duplicity_list:
                    duplicity_list.append(original_entry)
        cpf_to_name[cpf] = name
    unique_duplicity = []
    seen = set()
    for item in duplicity_list:
        key = (item.get("Nome Trabalhador"), item.get("CPF"), item.get("Motivo"))
        if key not in seen:
            unique_duplicity.append(item)
            seen.add(key)
    return unique_duplicity
