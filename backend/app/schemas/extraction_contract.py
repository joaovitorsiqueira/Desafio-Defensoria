"""Contrato de saída da extração (seção 4 do desafio).

Este módulo é a fonte de verdade do formato que o modelo de IA deve produzir. Ele é
usado de duas formas:
1. Como `output_format` na chamada ao provedor de IA (saída estruturada nativa).
2. Como schema de validação independente logo após a resposta do modelo — a IA nunca
   é confiada "às cegas": tudo que ela devolve passa por este Pydantic model antes de
   seguir para validação de evidências e persistência.

Campos são deliberadamente opcionais (`| None` ou lista vazia) mesmo quando o
exemplo do contrato não mostra "| null" explicitamente (ex.: `numero`, `ano`,
`orgao_emissor`). Isso é uma decisão consciente: a regra fundamental do domínio
("uma informação inventada é pior que uma informação ausente") vale para todo
campo, não só para os que o exemplo anotou como nulináveis. Ver DECISOES.md.
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class TipoAto(str, Enum):
    PORTARIA = "PORTARIA"
    RESOLUCAO = "RESOLUCAO"
    DESPACHO = "DESPACHO"
    EDITAL = "EDITAL"
    INSTRUCAO_NORMATIVA = "INSTRUCAO_NORMATIVA"
    OUTRO = "OUTRO"


class PapelPessoa(str, Enum):
    NOMEADO = "NOMEADO"
    EXONERADO = "EXONERADO"
    DESIGNADO = "DESIGNADO"
    DISPENSADO = "DISPENSADO"
    CEDIDO = "CEDIDO"
    BENEFICIARIO = "BENEFICIARIO"
    OUTRO = "OUTRO"


class RelacaoAto(str, Enum):
    REVOGA = "REVOGA"
    ALTERA = "ALTERA"
    RETIFICA = "RETIFICA"
    COMPLEMENTA = "COMPLEMENTA"


class Signatario(BaseModel):
    nome: str
    cargo: str


class PessoaCitada(BaseModel):
    nome: str
    identificador: str | None = None
    cargo: str | None = None
    papel: PapelPessoa


class AtoRelacionado(BaseModel):
    referencia: str
    relacao: RelacaoAto


class Vigencia(BaseModel):
    inicio: date | None = None
    fim: date | None = None
    retroativa: bool | None = None


class Evidencias(BaseModel):
    """Trechos literais do documento que sustentam cada campo crítico.

    Um campo por informação crítica do contrato (em vez de um dicionário livre)
    para que o schema de saída estruturada seja explícito e o modelo saiba
    exatamente quais evidências pode/deve fornecer.
    """

    numero: str | None = None
    ano: str | None = None
    orgao_emissor: str | None = None
    data_assinatura: str | None = None
    data_publicacao: str | None = None
    signatarios: str | None = None
    pessoas_citadas: str | None = None
    fundamentacao_legal: str | None = None
    atos_relacionados: str | None = None
    vigencia: str | None = None


class Meta(BaseModel):
    campos_nao_encontrados: list[str] = Field(default_factory=list)
    confianca_geral: float = Field(ge=0.0, le=1.0)
    evidencias: Evidencias = Field(default_factory=Evidencias)


class AtoExtraido(BaseModel):
    """Estrutura completa devolvida pela IA (e, após correção humana, pelo sistema)."""

    tipo_ato: TipoAto
    numero: str | None = None
    ano: int | None = None
    orgao_emissor: str | None = None
    data_assinatura: date | None = None
    data_publicacao: date | None = None
    assunto: str | None = Field(default=None, max_length=200)
    resumo: str | None = None

    signatarios: list[Signatario] = Field(default_factory=list)
    pessoas_citadas: list[PessoaCitada] = Field(default_factory=list)
    fundamentacao_legal: list[str] = Field(default_factory=list)
    atos_relacionados: list[AtoRelacionado] = Field(default_factory=list)
    vigencia: Vigencia = Field(default_factory=Vigencia)
    palavras_chave: list[str] = Field(default_factory=list)

    meta: Meta


# Campos considerados "críticos" para fins de evidência e cálculo de confiança:
# são os campos para os quais o prompt instrui o modelo a fornecer uma evidência
# literal em `meta.evidencias` (seção 8 do desafio).
CAMPOS_CRITICOS: tuple[str, ...] = (
    "numero",
    "ano",
    "orgao_emissor",
    "data_assinatura",
    "data_publicacao",
    "signatarios",
    "pessoas_citadas",
    "fundamentacao_legal",
    "atos_relacionados",
    "vigencia",
)


def campo_esta_preenchido(ato: AtoExtraido, campo: str) -> bool:
    """Verifica se um campo crítico tem valor (não-nulo / lista não-vazia)."""
    valor = getattr(ato, campo)
    if valor is None:
        return False
    if isinstance(valor, list):
        return len(valor) > 0
    if isinstance(valor, Vigencia):
        return valor.inicio is not None or valor.fim is not None or valor.retroativa is not None
    return True
