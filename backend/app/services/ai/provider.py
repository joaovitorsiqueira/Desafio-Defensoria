"""Abstração do provedor de IA (seção 35/36 do desafio).

A camada de aplicação (extraction_service) depende apenas desta interface, nunca do
SDK de um provedor específico. Trocar de provedor/modelo no futuro (Anthropic →
OpenAI/Gemini/modelo local) significa escrever uma nova implementação de
`AIProvider`, sem tocar no restante do sistema.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.extraction_contract import AtoExtraido


@dataclass(frozen=True)
class AIExtractionOutcome:
    ato: AtoExtraido
    raw_json: dict
    modelo: str
    tokens_entrada: int
    tokens_saida: int
    latencia_ms: int
    tentativas: int
    custo_estimado_usd: float | None


class AIExtractionError(Exception):
    """Erro de negócio ao obter uma extração estruturada válida do modelo, após
    esgotadas as tentativas de recuperação. Deve virar mensagem amigável na API."""


class AIProvider(ABC):
    @abstractmethod
    def extrair(self, *, texto_documento: str, prompt_sistema: str) -> AIExtractionOutcome:
        """Envia o texto do documento ao modelo e devolve uma extração estruturada
        já validada pelo schema Pydantic do contrato (`AtoExtraido`)."""
        raise NotImplementedError
