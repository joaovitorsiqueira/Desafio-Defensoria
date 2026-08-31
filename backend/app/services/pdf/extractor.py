"""Extração programática de texto de PDF (seção 12 do desafio).

Usa pypdf, uma biblioteca pura-Python madura para leitura de PDF, sem dependências
nativas extras — mantém a instalação simples em qualquer máquina. Não faz OCR: PDFs
sem camada de texto (escaneados como imagem) são tratados como erro esperado, não
como bug (ver DocumentoSemTextoError). OCR está fora do escopo do desafio, mas é
citado como próximo passo em DECISOES.md.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

# Algumas ferramentas de geração de PDF (observado em documentos exportados pelo
# sistema SEI de governo, entre outras) embutem fontes cuja ligadura "ti" tem um
# mapeamento Unicode quebrado: em vez de decompor para as letras "t"+"i", o
# ToUnicode CMap da fonte aponta para um código Unicode não relacionado. Isso não
# é específico de nenhum documento em particular — é uma falha de geração de PDF
# que pode aparecer em qualquer ato exportado pela mesma ferramenta, e sem essa
# correção o texto extraído fica com erros como "ConsƟtuição" em vez de
# "Constituição", o que tanto prejudica a compreensão do modelo quanto quebra a
# validação de evidências (o modelo tende a "corrigir" a palavra ao citar a
# evidência, e a comparação literal contra o texto original — que ainda contém o
# caractere quebrado — falha por engano). Mapeamento construído a partir de um
# caso real encontrado em testes; se novos padrões aparecerem, adicionar aqui.
_LIGADURAS_QUEBRADAS: dict[str, str] = {
    "Ɵ": "ti",  # "Ɵ" usado no lugar da ligadura "ti"
}


def _corrigir_ligaduras_quebradas(texto: str) -> str:
    for quebrado, correto in _LIGADURAS_QUEBRADAS.items():
        texto = texto.replace(quebrado, correto)
    # NFKC decompõe ligaduras Unicode legítimas (ex.: "ﬁ" -> "fi", "ﬂ" -> "fl"),
    # que alguns extratores de PDF preservam como um único glifo — normalizar
    # aqui evita o mesmo tipo de falha de correspondência literal na validação
    # de evidências para esses casos padrão.
    return unicodedata.normalize("NFKC", texto)


# Limiar de linhas consecutivas de 1 caractere para considerar que a página foi
# quebrada caractere-a-caractere (ver _reconstruir_linhas_de_caractere_unico).
_LIMIAR_RECONSTRUCAO = 6


def _reconstruir_linhas_de_caractere_unico(texto: str) -> str:
    """Reconstrói trechos em que o pypdf extraiu um caractere por linha.

    Observado em produção (não é específico de nenhum documento): em algumas
    páginas — tipicamente onde há cabeçalhos/rodapés com espaçamento de fonte
    incomum — o pypdf devolve cada letra do texto como uma "linha" própria
    (ex.: "P\\nr\\ni\\nm\\ne\\ni\\nr\\na" em vez de "Prima"). Isso infla
    artificialmente o tamanho do documento (aumentando a chance de truncamento
    desnecessário) e torna o trecho praticamente ilegível tanto para a busca de
    evidências quanto para o próprio modelo de IA.

    A correção é puramente estrutural: sempre que houver uma sequência de pelo
    menos `_LIMIAR_RECONSTRUCAO` linhas consecutivas com exatamente 1 caractere
    cada (incluindo espaços, que aqui também viram uma "linha" própria), essas
    linhas são concatenadas de volta em uma única linha. Uma sequência curta de
    linhas de 1 caractere (ex.: uma lista numerada real) não aciona a
    reconstrução — o limiar existe justamente para isso.
    """
    linhas = texto.split("\n")
    resultado: list[str] = []
    buffer: list[str] = []

    def esvaziar_buffer() -> None:
        if len(buffer) >= _LIMIAR_RECONSTRUCAO:
            resultado.append("".join(buffer))
        else:
            resultado.extend(buffer)
        buffer.clear()

    for linha in linhas:
        if len(linha) == 1:
            buffer.append(linha)
        else:
            esvaziar_buffer()
            resultado.append(linha)
    esvaziar_buffer()
    return "\n".join(resultado)


class PdfExtractionError(Exception):
    """Erro de negócio ao processar um PDF — sempre deve virar mensagem amigável."""


class PdfInvalidoError(PdfExtractionError):
    pass


class PdfSemTextoError(PdfExtractionError):
    pass


class PdfConteudoInsuficienteError(PdfExtractionError):
    pass


@dataclass(frozen=True)
class TextoExtraido:
    texto: str
    numero_paginas: int
    caracteres: int


_MIN_CARACTERES_UTEIS = 30


def _normalizar_texto(texto: str) -> str:
    """Normalização leve: reconstrói texto quebrado caractere-a-caractere,
    corrige ligaduras quebradas conhecidas, preserva quebras de página/parágrafo,
    remove espaços redundantes dentro das linhas e linhas totalmente vazias em
    excesso."""
    texto = _reconstruir_linhas_de_caractere_unico(texto)
    texto = _corrigir_ligaduras_quebradas(texto)
    linhas = [re.sub(r"[ \t]+", " ", linha).strip() for linha in texto.splitlines()]
    linhas_sem_excesso: list[str] = []
    linha_vazia_anterior = False
    for linha in linhas:
        if linha == "":
            if linha_vazia_anterior:
                continue
            linha_vazia_anterior = True
        else:
            linha_vazia_anterior = False
        linhas_sem_excesso.append(linha)
    return "\n".join(linhas_sem_excesso).strip()


def extrair_texto_pdf(conteudo: bytes) -> TextoExtraido:
    """Extrai e normaliza o texto de um PDF a partir dos bytes do arquivo.

    Levanta subclasses de PdfExtractionError com mensagens já pensadas para
    tradução direta em texto amigável na API/tela — nunca stack trace bruto.
    """
    try:
        leitor = PdfReader(BytesIO(conteudo))
    except PdfReadError as exc:
        raise PdfInvalidoError("O arquivo enviado não é um PDF válido ou está corrompido.") from exc
    except Exception as exc:  # pypdf pode levantar outros erros para arquivos malformados
        raise PdfInvalidoError("Não foi possível abrir o arquivo como PDF.") from exc

    if leitor.is_encrypted:
        try:
            leitor.decrypt("")
        except Exception as exc:
            raise PdfInvalidoError("O PDF está protegido por senha e não pôde ser lido.") from exc

    paginas_texto: list[str] = []
    for pagina in leitor.pages:
        try:
            paginas_texto.append(pagina.extract_text() or "")
        except Exception:
            paginas_texto.append("")

    texto_bruto = "\n\n".join(paginas_texto)
    texto = _normalizar_texto(texto_bruto)

    if len(texto) < _MIN_CARACTERES_UTEIS:
        raise PdfSemTextoError(
            "Não foi possível extrair texto deste PDF. Ele provavelmente é um "
            "documento escaneado (imagem) sem camada de texto — reconhecimento "
            "óptico (OCR) não é suportado nesta versão."
        )

    return TextoExtraido(texto=texto, numero_paginas=len(leitor.pages), caracteres=len(texto))


def validar_texto_colado(texto: str) -> TextoExtraido:
    """Aplica a mesma normalização e os mesmos limites mínimos ao texto colado
    manualmente pelo usuário, para que os dois fluxos de ingestão (PDF e texto)
    compartilhem a mesma régua de qualidade."""
    normalizado = _normalizar_texto(texto)
    if len(normalizado) < _MIN_CARACTERES_UTEIS:
        raise PdfConteudoInsuficienteError(
            "O texto colado é muito curto para representar um ato administrativo."
        )
    return TextoExtraido(texto=normalizado, numero_paginas=1, caracteres=len(normalizado))
