from __future__ import annotations

from app.core.config import Settings
from app.services.ai.provider import AIProvider


def get_ai_provider(settings: Settings) -> AIProvider:
    """Ponto único de escolha do provedor de IA, a partir de `AI_PROVIDER`.

    Trocar de provedor no futuro é adicionar um `elif` aqui e uma nova classe que
    implemente `AIProvider` — o resto da aplicação não muda. Os SDKs de cada
    provedor só são importados sob demanda (dentro de cada ramo), para que a
    aplicação suba mesmo sem uma das duas dependências instaladas.
    """
    if settings.ai_provider == "ollama":
        from app.services.ai.ollama_provider import OllamaProvider

        return OllamaProvider(settings)
    if settings.ai_provider == "anthropic":
        from app.services.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    raise ValueError(f"Provedor de IA não suportado: {settings.ai_provider!r}")
