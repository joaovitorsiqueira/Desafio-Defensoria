"""Implementação do AIProvider usando a API da Anthropic (Claude).

Usa o helper `client.messages.parse(..., output_format=AtoExtraido)` do SDK
oficial: a chamada à API já pede saída estruturada nativa (JSON Schema derivado do
nosso modelo Pydantic, via `output_config` internamente) e o próprio SDK valida a
resposta contra esse schema antes de devolvê-la em `response.parsed_output`. Ou
seja, a extração nunca passa por "texto livre + regex" — isso é o que o desafio
proíbe explicitamente (seção 6/45).

Ainda assim, tratamos essa validação do SDK como a primeira camada de defesa, não a
única: o resultado segue depois para validação de evidências (seção 8) antes de
qualquer persistência.

Recuperação de erros (seção 22): se a chamada falhar por schema/JSON inválido,
timeout ou erro transitório da API, tentamos novamente uma vez com uma instrução
corretiva anexada, respeitando um limite explícito de tentativas
(`settings.ai_max_attempts`) para nunca entrar em loop infinito.
"""
from __future__ import annotations

import time

import anthropic
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.extraction_contract import AtoExtraido
from app.services.ai.pricing import calcular_custo_usd
from app.services.ai.provider import AIExtractionError, AIExtractionOutcome, AIProvider


class AnthropicProvider(AIProvider):
    def __init__(self, settings: Settings):
        if not settings.anthropic_api_key:
            raise AIExtractionError(
                "Nenhuma chave de API da Anthropic configurada (ANTHROPIC_API_KEY)."
            )
        self._settings = settings
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.ai_request_timeout_seconds,
        )

    def extrair(self, *, texto_documento: str, prompt_sistema: str) -> AIExtractionOutcome:
        max_tentativas = max(1, self._settings.ai_max_attempts)
        ultimo_erro: Exception | None = None
        instrucao_corretiva = ""

        for tentativa in range(1, max_tentativas + 1):
            conteudo_usuario = (
                f"{instrucao_corretiva}Documento a ser analisado "
                f"(texto extraído de PDF ou colado pelo usuário):\n\n{texto_documento}"
            )
            inicio = time.perf_counter()
            try:
                response = self._client.messages.parse(
                    model=self._settings.ai_model,
                    max_tokens=8000,
                    system=prompt_sistema,
                    thinking={"type": "adaptive"},
                    messages=[{"role": "user", "content": conteudo_usuario}],
                    output_format=AtoExtraido,
                )
            except anthropic.APIStatusError as exc:
                ultimo_erro = exc
                instrucao_corretiva = (
                    "[Nova tentativa após erro da API na chamada anterior. Responda "
                    "novamente seguindo estritamente o schema solicitado.]\n\n"
                )
                continue
            except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
                ultimo_erro = exc
                instrucao_corretiva = (
                    "[Nova tentativa após timeout/erro de conexão na chamada anterior.]\n\n"
                )
                continue
            except ValidationError as exc:
                ultimo_erro = exc
                instrucao_corretiva = (
                    "[A resposta anterior não seguiu exatamente o schema solicitado "
                    f"({exc}). Responda novamente respeitando rigorosamente os tipos, "
                    "enums e formatos de data pedidos, usando null/[] quando a "
                    "informação não constar do documento.]\n\n"
                )
                continue

            latencia_ms = int((time.perf_counter() - inicio) * 1000)

            if response.stop_reason == "refusal":
                ultimo_erro = AIExtractionError("O modelo recusou a solicitação por política de segurança.")
                instrucao_corretiva = ""
                continue

            ato = response.parsed_output
            if ato is None:
                ultimo_erro = AIExtractionError(
                    "O modelo não devolveu uma saída estruturada válida (resposta incompleta)."
                )
                instrucao_corretiva = (
                    "[A resposta anterior veio incompleta ou sem a estrutura pedida. "
                    "Responda novamente preenchendo todos os campos do contrato, usando "
                    "null/[] onde não houver informação no documento.]\n\n"
                )
                continue

            tokens_entrada = response.usage.input_tokens
            tokens_saida = response.usage.output_tokens
            custo = calcular_custo_usd(response.model, tokens_entrada, tokens_saida)

            return AIExtractionOutcome(
                ato=ato,
                raw_json=ato.model_dump(mode="json"),
                modelo=response.model,
                tokens_entrada=tokens_entrada,
                tokens_saida=tokens_saida,
                latencia_ms=latencia_ms,
                tentativas=tentativa,
                custo_estimado_usd=custo,
            )

        raise AIExtractionError(
            "Não foi possível obter uma extração estruturada válida do modelo após "
            f"{max_tentativas} tentativa(s)."
        ) from ultimo_erro
