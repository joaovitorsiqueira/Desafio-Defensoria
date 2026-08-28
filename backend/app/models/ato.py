"""Modelo de persistência (seção 21 do desafio).

Deliberadamente simples: duas tabelas.
- `atos`: um registro por documento processado, guardando o texto extraído, o
  resultado estruturado atual (já refletindo eventuais correções humanas), um
  retrato do resultado original da IA (para auditoria — nunca sobrescrito), os
  resultados da validação de evidências, e os metadados de observabilidade
  (tokens, latência, custo, versão do prompt, modelo).
- `correcoes`: um registro por edição humana feita em um campo, preservando o
  histórico de "quem mudou o quê" mesmo que o valor atual em `atos` já reflita a
  correção mais recente.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


def _agora() -> datetime:
    return datetime.now(UTC)


def _novo_id() -> str:
    return uuid.uuid4().hex


class Ato(Base):
    __tablename__ = "atos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_novo_id)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_agora)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=_agora, onupdate=_agora
    )

    # Ingestão
    origem: Mapped[str] = mapped_column(String(10))  # "pdf" | "texto"
    nome_arquivo_original: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caminho_arquivo_original: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    texto_extraido: Mapped[str] = mapped_column(Text)
    texto_enviado_ao_modelo: Mapped[str] = mapped_column(Text)
    truncado: Mapped[bool] = mapped_column(default=False)

    status: Mapped[str] = mapped_column(String(20), default="concluido")  # concluido | erro
    mensagem_erro: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Campos denormalizados do contrato, para listagem/filtro/busca eficientes
    tipo_ato: Mapped[str | None] = mapped_column(String(30), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orgao_emissor: Mapped[str | None] = mapped_column(String(300), nullable=True)
    data_assinatura: Mapped[str | None] = mapped_column(String(10), nullable=True)
    data_publicacao: Mapped[str | None] = mapped_column(String(10), nullable=True)
    assunto: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Resultado estruturado completo (contrato inteiro), fonte de verdade para a UI
    resultado_estruturado: Mapped[dict] = mapped_column(JSON)
    # Retrato do resultado exatamente como a IA devolveu + evidências validadas,
    # nunca alterado após a criação — usado para diferenciar "gerado pela IA" de
    # "corrigido por humano" na interface.
    resultado_ia_original: Mapped[dict] = mapped_column(JSON)

    campos_suspeitos: Mapped[list] = mapped_column(JSON, default=list)
    evidencias_validadas: Mapped[list] = mapped_column(JSON, default=list)
    campos_nao_encontrados: Mapped[list] = mapped_column(JSON, default=list)
    fontes_dos_campos: Mapped[dict] = mapped_column(JSON, default=dict)  # campo -> "ia" | "humano"
    confianca_geral: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Observabilidade (seção 24)
    prompt_versao: Mapped[str | None] = mapped_column(String(50), nullable=True)
    modelo_ia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_entrada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_saida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latencia_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custo_estimado_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    tentativas_ia: Mapped[int | None] = mapped_column(Integer, nullable=True)

    correcoes: Mapped[list["Correcao"]] = relationship(back_populates="ato", cascade="all, delete-orphan")


class Correcao(Base):
    __tablename__ = "correcoes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_novo_id)
    ato_id: Mapped[str] = mapped_column(ForeignKey("atos.id"))
    campo: Mapped[str] = mapped_column(String(100))
    valor_anterior: Mapped[dict] = mapped_column(JSON)
    valor_novo: Mapped[dict] = mapped_column(JSON)
    corrigido_em: Mapped[datetime] = mapped_column(DateTime, default=_agora)

    ato: Mapped[Ato] = relationship(back_populates="correcoes")
