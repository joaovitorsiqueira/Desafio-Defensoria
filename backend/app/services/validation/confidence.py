"""Cálculo de `meta.confianca_geral` (seção 10 do desafio).

O valor de confiança que a IA devolve é apenas uma autoavaliação subjetiva do
modelo — não uma probabilidade estatística calibrada. Em vez de repassar esse
número diretamente ao usuário, recalculamos um valor determinístico e auditável a
partir de dois sinais observáveis:

1. Cobertura: qual fração dos campos críticos do contrato foi efetivamente
   preenchida (não-nula)?
2. Sustentação: dentre os campos críticos preenchidos, qual fração tem evidência
   que de fato bateu no texto original?

confianca_geral = 0.5 * cobertura + 0.5 * sustentacao

Esta é uma fórmula simples e explicável, não uma medida estatística real — ela
mistura "o quanto foi encontrado" com "o quanto do que foi encontrado está
comprovado". Documentado assim para evitar a alegação (proibida pelo desafio) de
que representa uma probabilidade calibrada.
"""
from __future__ import annotations

from app.schemas.extraction_contract import CAMPOS_CRITICOS, AtoExtraido, campo_esta_preenchido
from app.services.validation.evidence import EvidenceCheck


def calcular_confianca(ato: AtoExtraido, checks: list[EvidenceCheck]) -> float:
    campos_preenchidos = [c for c in CAMPOS_CRITICOS if campo_esta_preenchido(ato, c)]
    cobertura = len(campos_preenchidos) / len(CAMPOS_CRITICOS)

    if not campos_preenchidos:
        sustentacao = 0.0
    else:
        checks_by_campo = {c.campo: c for c in checks}
        sustentados = sum(
            1 for campo in campos_preenchidos if checks_by_campo.get(campo, None) and checks_by_campo[campo].encontrada
        )
        sustentacao = sustentados / len(campos_preenchidos)

    confianca = 0.5 * cobertura + 0.5 * sustentacao
    return round(min(max(confianca, 0.0), 1.0), 2)
