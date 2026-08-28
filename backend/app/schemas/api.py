"""Schemas de request/response da API REST — separados do contrato de extração da
IA (schemas/extraction_contract.py) para que a interface pública da API possa
evoluir (paginação, metadados de auditoria, etc.) sem misturar responsabilidades
com o formato que o modelo de linguagem precisa produzir.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.extraction_contract import AtoExtraido


class EvidenceCheckOut(BaseModel):
    campo: str
    evidencia: str
    encontrada: bool
    match_type: str


class AtoListItem(BaseModel):
    id: str
    criado_em: datetime
    status: str
    tipo_ato: str | None
    numero: str | None
    ano: int | None
    orgao_emissor: str | None
    data_assinatura: str | None
    data_publicacao: str | None
    assunto: str | None
    confianca_geral: float | None
    campos_suspeitos: list[str] = Field(default_factory=list)
    tem_correcao_humana: bool = False

    model_config = {"from_attributes": True}


class AtoListResponse(BaseModel):
    items: list[AtoListItem]
    total: int
    limit: int
    offset: int


class Auditoria(BaseModel):
    prompt_versao: str | None
    modelo_ia: str | None
    tokens_entrada: int | None
    tokens_saida: int | None
    latencia_ms: int | None
    custo_estimado_usd: float | None
    tentativas_ia: int | None
    truncado: bool


class AtoDetail(BaseModel):
    id: str
    criado_em: datetime
    atualizado_em: datetime
    status: str
    mensagem_erro: str | None

    origem: str
    nome_arquivo_original: str | None
    tem_arquivo_original: bool
    texto_extraido: str

    resultado: AtoExtraido
    resultado_ia_original: AtoExtraido
    campos_suspeitos: list[str]
    evidencias_validadas: list[EvidenceCheckOut]
    fontes_dos_campos: dict[str, str]

    auditoria: Auditoria


class TextoUploadRequest(BaseModel):
    texto: str = Field(min_length=1)


class CorrecaoRequest(BaseModel):
    campo: str = Field(description="Nome do campo de topo do contrato a corrigir, ex.: 'orgao_emissor'.")
    valor: Any = Field(description="Novo valor do campo, no mesmo formato do contrato de extração.")


