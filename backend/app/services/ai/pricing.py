"""Preços por modelo, centralizados em um único lugar (seção 25 do desafio).

Valores em USD por 1 milhão de tokens, conforme a tabela de preços pública da
Anthropic vigente na data de desenvolvimento deste projeto (ver DECISOES.md para a
fonte e a data de referência). Se o provedor mudar os preços, ou se um novo modelo
for adicionado, basta atualizar este dicionário — nenhum outro módulo precisa
mudar.

Modelos locais (executados via Ollama) não têm custo por token — o preço
marginal de uma chamada é efetivamente zero (o custo real é o hardware/energia
já amortizados, que este projeto não tenta estimar). `MODELOS_LOCAIS` lista os
modelos tratados dessa forma; qualquer nome de modelo do Ollama (com ou sem
sufixo de tag, ex. "qwen3:8b") é reconhecido automaticamente.

Se o modelo usado não constar em nenhuma das duas listas, o custo estimado é
reportado como `None` em vez de um valor inventado — coerente com a regra do
domínio de nunca fabricar informação.
"""
from __future__ import annotations

PRECOS_USD_POR_MILHAO_TOKENS: dict[str, dict[str, float]] = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

MODELOS_LOCAIS_CONHECIDOS: set[str] = {"qwen3:8b", "qwen2.5:7b-instruct", "qwen2.5:14b-instruct"}


def _e_modelo_local(modelo: str) -> bool:
    return modelo in MODELOS_LOCAIS_CONHECIDOS or ":" in modelo


def calcular_custo_usd(modelo: str, tokens_entrada: int, tokens_saida: int) -> float | None:
    if _e_modelo_local(modelo):
        return 0.0
    preco = PRECOS_USD_POR_MILHAO_TOKENS.get(modelo)
    if preco is None:
        return None
    custo = (tokens_entrada / 1_000_000) * preco["input"] + (tokens_saida / 1_000_000) * preco["output"]
    return round(custo, 6)
