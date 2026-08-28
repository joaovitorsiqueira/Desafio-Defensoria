"""Estratégia para documentos longos (seção 11 do desafio).

Não enviamos cegamente o texto inteiro ao modelo. A estratégia escolhida é
deliberadamente simples e genérica — não depende do formato de nenhum órgão
específico:

1. Se o texto extraído cabe dentro do limite configurado
   (`settings.segmentation_max_chars`), ele é enviado por completo.
2. Se for maior, aplicamos truncamento por cabeçalho + trecho final: mantemos os
   primeiros `head_ratio` caracteres e os últimos `(1 - head_ratio)`, descartando o
   meio. A justificativa é estrutural, não específica de nenhum documento: atos
   administrativos brasileiros seguem convencionalmente o padrão
   [cabeçalho/ementa/"considerandos"] → [corpo/artigos] → [assinatura/data/local],
   e os campos do contrato (tipo, número, ano, órgão, ementa, fundamentação legal,
   e depois assinatura e data) concentram-se tipicamente no início e no fim do
   documento. O meio — normalmente o detalhamento do "corpo" do ato, anexos,
   tabelas extensas — é o conteúdo com menor densidade desses campos.
3. O ponto de corte nunca parte uma linha ao meio: ajusta para a quebra de linha
   mais próxima, e insere um marcador textual explícito indicando que houve
   omissão, para que o modelo (e qualquer auditor humano) saiba que aquele não é o
   texto completo.

Esta estratégia é registrada nos metadados de auditoria de cada processamento
(campo `truncado`), para que fique claro quando uma extração foi feita a partir de
um recorte do documento.
"""
from __future__ import annotations

from dataclasses import dataclass

_MARCADOR_OMISSAO = "\n\n[... trecho intermediário omitido por limite de tamanho ...]\n\n"


@dataclass(frozen=True)
class ConteudoParaModelo:
    texto: str
    truncado: bool
    caracteres_originais: int
    caracteres_enviados: int


def _cortar_na_quebra_de_linha_mais_proxima(texto: str, posicao: int, buscar_para_frente: bool) -> int:
    if buscar_para_frente:
        indice = texto.find("\n", posicao)
        return indice if indice != -1 else posicao
    indice = texto.rfind("\n", 0, posicao)
    return indice if indice != -1 else posicao


def preparar_conteudo_para_modelo(
    texto_original: str, max_chars: int, head_ratio: float
) -> ConteudoParaModelo:
    total = len(texto_original)
    if total <= max_chars:
        return ConteudoParaModelo(
            texto=texto_original,
            truncado=False,
            caracteres_originais=total,
            caracteres_enviados=total,
        )

    tamanho_cabecalho = int(max_chars * head_ratio)
    tamanho_final = max_chars - tamanho_cabecalho

    corte_inicio = _cortar_na_quebra_de_linha_mais_proxima(
        texto_original, tamanho_cabecalho, buscar_para_frente=False
    )
    corte_fim = _cortar_na_quebra_de_linha_mais_proxima(
        texto_original, total - tamanho_final, buscar_para_frente=True
    )
    corte_fim = max(corte_fim, corte_inicio)

    cabecalho = texto_original[:corte_inicio].rstrip()
    trecho_final = texto_original[corte_fim:].lstrip()

    texto_montado = f"{cabecalho}{_MARCADOR_OMISSAO}{trecho_final}"
    return ConteudoParaModelo(
        texto=texto_montado,
        truncado=True,
        caracteres_originais=total,
        caracteres_enviados=len(texto_montado),
    )
