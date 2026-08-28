"""Validação programática das evidências (seção 8 do desafio — "a parte mais
importante").

Para cada campo crítico que a IA preencheu e para o qual forneceu um trecho de
evidência, verificamos se esse trecho realmente existe no texto original extraído
do documento. Não confiamos apenas na palavra do modelo.

Estratégia de comparação (deliberadamente simples — ver DECISOES.md):
1. Normalização controlada: colapsa espaços/quebras de linha em um único espaço e
   remove espaços nas pontas. Isso tolera diferenças de quebra de linha entre o
   texto extraído do PDF e o trecho copiado pelo modelo, sem alterar o conteúdo.
2. Comparação literal (substring) do trecho normalizado dentro do texto
   normalizado.
3. Tolerância adicional única: se a comparação exata falhar, tenta novamente
   comparando em caixa baixa (case-insensitive). Isso cobre casos onde o modelo
   copia o trecho correto mas normaliza a capitalização (comum em cabeçalhos em
   caixa alta). Essa é a única flexibilidade extra do sistema — não há
   fuzzy-matching, distância de edição ou similar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.extraction_contract import CAMPOS_CRITICOS, AtoExtraido, campo_esta_preenchido


@dataclass(frozen=True)
class EvidenceCheck:
    campo: str
    evidencia: str
    encontrada: bool
    match_type: str  # "exata" | "case_insensitive" | "nao_encontrada" | "sem_evidencia"


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _evidencia_bate_no_texto(evidencia: str, texto_normalizado: str) -> str:
    """Retorna o match_type: "exata", "case_insensitive" ou "nao_encontrada"."""
    evidencia_normalizada = _normalizar(evidencia)
    if not evidencia_normalizada:
        return "nao_encontrada"
    if evidencia_normalizada in texto_normalizado:
        return "exata"
    if evidencia_normalizada.lower() in texto_normalizado.lower():
        return "case_insensitive"
    return "nao_encontrada"


def validar_evidencias(texto_original: str, ato: AtoExtraido) -> list[EvidenceCheck]:
    """Verifica cada evidência fornecida pela IA contra o texto original completo.

    Importante: a verificação é feita contra o texto ORIGINAL extraído do PDF (não
    contra o trecho eventualmente truncado que foi enviado ao modelo), pois o que
    importa para auditoria é se a informação está sustentada pelo documento real.

    Só avaliamos evidência para campos que o modelo efetivamente preencheu.
    Alguns modelos (sobretudo os menores/locais) por vezes escrevem algo como
    "não mencionado" no campo de evidência mesmo quando o campo principal já foi
    corretamente deixado vazio — nesse caso não há nada de fato a auditar, e
    gerar um resultado "evidência não encontrada" ali só criaria ruído na
    interface para um campo que já está corretamente marcado como ausente.
    """
    texto_normalizado = _normalizar(texto_original)
    resultados: list[EvidenceCheck] = []
    evidencias_por_campo = ato.meta.evidencias.model_dump()
    for campo in CAMPOS_CRITICOS:
        evidencia = evidencias_por_campo.get(campo)
        if not evidencia or not campo_esta_preenchido(ato, campo):
            continue
        match_type = _evidencia_bate_no_texto(evidencia, texto_normalizado)
        resultados.append(
            EvidenceCheck(
                campo=campo,
                evidencia=evidencia,
                encontrada=match_type != "nao_encontrada",
                match_type=match_type,
            )
        )
    return resultados


def campos_suspeitos(ato: AtoExtraido, checks: list[EvidenceCheck]) -> list[str]:
    """Determina quais campos críticos devem ser marcados como "suspeitos".

    Um campo crítico preenchido é considerado suspeito quando:
    - a IA não forneceu nenhuma evidência para ele, ou
    - a evidência fornecida não foi encontrada no texto original.

    Comportamento conservador (seção 9 do desafio): o valor do campo NÃO é
    apagado/nulificado automaticamente. Ele é preservado, mas marcado como
    suspeito, para que a interface o exiba como "não confirmado" em vez de
    apresentá-lo como informação validada. Isso evita esconder do revisor humano
    uma informação que pode estar correta mas cuja evidência falhou na checagem
    automática — a decisão final fica com a pessoa, não com o sistema.
    """
    checks_by_campo = {c.campo: c for c in checks}
    suspeitos: list[str] = []
    for campo in CAMPOS_CRITICOS:
        if not campo_esta_preenchido(ato, campo):
            continue
        check = checks_by_campo.get(campo)
        if check is None or not check.encontrada:
            suspeitos.append(campo)
    return suspeitos
