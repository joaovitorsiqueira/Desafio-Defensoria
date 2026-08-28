"""Implementação do AIProvider usando um modelo local via Ollama.

Alternativa ao provedor Anthropic (`anthropic_provider.py`) por trás da mesma
interface `AIProvider` — trocar de um para o outro é só mudar `AI_PROVIDER` no
`.env`, sem alterar `extraction_service.py`, a API ou o front-end. Ver
DECISOES.md para a justificativa de usar um modelo local (qwen3:8b) como
provedor padrão deste projeto.

Assim como o provedor Anthropic, usa saída estruturada nativa: o parâmetro
`format` da API do Ollama recebe o JSON Schema derivado do nosso modelo
Pydantic (`AtoExtraido.model_json_schema()`), o que restringe a geração do
modelo a produzir apenas JSON que já respeita tipos e enums — não é
"texto livre + regex". A resposta ainda passa por uma segunda validação
Pydantic explícita antes de seguir para a validação de evidências.
"""
from __future__ import annotations

import json
import time

import httpx
import ollama
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.extraction_contract import AtoExtraido
from app.services.ai.pricing import calcular_custo_usd
from app.services.ai.provider import AIExtractionError, AIExtractionOutcome, AIProvider

_ESQUEMA_ATO = AtoExtraido.model_json_schema()


class OllamaProvider(AIProvider):
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = ollama.Client(host=settings.ollama_base_url, timeout=settings.ai_request_timeout_seconds)

    def extrair(self, *, texto_documento: str, prompt_sistema: str) -> AIExtractionOutcome:
        max_tentativas = max(1, self._settings.ai_max_attempts)
        ultimo_erro: Exception | None = None
        ultima_causa: str | None = None
        instrucao_corretiva = ""
        tempo_total_s = 0.0

        for tentativa in range(1, max_tentativas + 1):
            conteudo_usuario = (
                f"{instrucao_corretiva}Documento a ser analisado "
                f"(texto extraído de PDF ou colado pelo usuário):\n\n{texto_documento}"
            )
            inicio = time.perf_counter()
            try:
                response = self._client.chat(
                    model=self._settings.ai_model,
                    messages=[
                        {"role": "system", "content": prompt_sistema},
                        {"role": "user", "content": conteudo_usuario},
                    ],
                    format=_ESQUEMA_ATO,
                    think=self._settings.ollama_think,
                    options={"temperature": 0, "num_ctx": self._settings.ollama_num_ctx},
                    # Mantém o modelo carregado em memória entre chamadas (inclusive
                    # entre tentativas de retry). Sem isso, o Ollama pode descarregar
                    # o modelo após um período ocioso e a próxima chamada paga de novo
                    # o custo de carregar ~5GB de pesos antes mesmo de começar a gerar
                    # — o que, em documentos grandes, é o suficiente para estourar o
                    # timeout mesmo quando a geração em si teria cabido no prazo.
                    keep_alive="30m",
                )
            except (ollama.RequestError, ConnectionError, TimeoutError, httpx.TimeoutException, httpx.TransportError) as exc:
                # httpx.TimeoutException/TransportError cobrem os erros reais de
                # rede/timeout que o cliente HTTP interno do pacote `ollama`
                # propaga (ex.: httpx.ReadTimeout quando a geração do modelo local
                # demora mais que `ai_request_timeout_seconds`) — eles NÃO herdam
                # de TimeoutError/ConnectionError do Python, então precisam ser
                # capturados explicitamente para não vazar como erro não tratado.
                ultimo_erro = exc
                tempo_total_s += time.perf_counter() - inicio
                ultima_causa = (
                    f"tempo limite de {self._settings.ai_request_timeout_seconds:.0f}s excedido "
                    "aguardando o modelo local"
                    if isinstance(exc, (httpx.TimeoutException, TimeoutError))
                    else "não foi possível conectar ao servidor Ollama"
                )
                instrucao_corretiva = (
                    "[Nova tentativa após erro de conexão/timeout com o modelo local na "
                    "chamada anterior.]\n\n"
                )
                continue
            except ollama.ResponseError as exc:
                ultimo_erro = exc
                tempo_total_s += time.perf_counter() - inicio
                ultima_causa = f"o servidor Ollama respondeu com um erro ({exc})"
                instrucao_corretiva = "[Nova tentativa após erro do servidor de IA na chamada anterior.]\n\n"
                continue

            latencia_ms = int((time.perf_counter() - inicio) * 1000)
            tempo_total_s += latencia_ms / 1000
            conteudo_resposta = response.message.content or ""

            try:
                dados = json.loads(conteudo_resposta)
                ato = AtoExtraido.model_validate(dados)
            except (json.JSONDecodeError, ValidationError) as exc:
                ultimo_erro = exc
                ultima_causa = f"a resposta do modelo não seguiu o schema esperado ({exc})"
                instrucao_corretiva = (
                    "[A resposta anterior não veio como um JSON válido seguindo o schema "
                    f"pedido ({exc}). Responda novamente respeitando rigorosamente os "
                    "tipos, enums e formatos de data pedidos, usando null/[] quando a "
                    "informação não constar do documento.]\n\n"
                )
                continue

            tokens_entrada = response.get("prompt_eval_count") or 0
            tokens_saida = response.get("eval_count") or 0
            custo = calcular_custo_usd(self._settings.ai_model, tokens_entrada, tokens_saida)

            return AIExtractionOutcome(
                ato=ato,
                raw_json=ato.model_dump(mode="json"),
                modelo=self._settings.ai_model,
                tokens_entrada=tokens_entrada,
                tokens_saida=tokens_saida,
                latencia_ms=latencia_ms,
                tentativas=tentativa,
                custo_estimado_usd=custo,
            )

        causa = ultima_causa or "motivo desconhecido"
        sugestao_timeout = (
            " Se a causa foi tempo limite excedido, documentos grandes podem "
            "genuinamente precisar de mais tempo em hardware local — considere "
            "aumentar AI_REQUEST_TIMEOUT_SECONDS no .env (atualmente "
            f"{self._settings.ai_request_timeout_seconds:.0f}s)."
            if ultima_causa and "tempo limite" in ultima_causa
            else ""
        )
        raise AIExtractionError(
            "Não foi possível obter uma extração estruturada válida do modelo local "
            f"após {max_tentativas} tentativa(s) em {tempo_total_s:.0f}s no total. "
            f"Causa da última tentativa: {causa}.{sugestao_timeout} Verifique também se "
            f"o Ollama está em execução em {self._settings.ollama_base_url} e se o modelo "
            f"'{self._settings.ai_model}' está baixado (`ollama pull {self._settings.ai_model}`)."
        ) from ultimo_erro
