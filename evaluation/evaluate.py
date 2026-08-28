#!/usr/bin/env python
"""Script de avaliação (seção 26 do desafio).

Processa cada PDF de `evaluation/dataset/pdfs/` através do mesmo pipeline usado
pela aplicação (extração de texto → segmentação → IA → validação de schema →
validação de evidências), compara o resultado com o gabarito em
`evaluation/dataset/ground_truth.json` e calcula a acurácia por campo.

A métrica é propositalmente simples e legível — nenhuma fórmula sofisticada:
para cada campo, conta-se a fração de documentos em que o valor extraído bate
com o gabarito, usando uma regra de comparação adequada a cada tipo de campo
(ver `_campos_bate`). Não há pesos, não há médias ponderadas por confiança.

Uso:
    ANTHROPIC_API_KEY=... python evaluation/evaluate.py

O resultado é impresso no terminal e também salvo em
`evaluation/results_latest.md` (texto legível) e `evaluation/results_latest.json`
(dados brutos), para que a "última execução" fique registrada no repositório
conforme exigido pelo desafio.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALUATION_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.services.ai.factory import get_ai_provider  # noqa: E402
from app.services.ai.provider import AIExtractionError  # noqa: E402
from app.services.extraction.segmentation import preparar_conteudo_para_modelo  # noqa: E402
from app.services.pdf.extractor import PdfExtractionError, extrair_texto_pdf  # noqa: E402
from app.services.validation.confidence import calcular_confianca  # noqa: E402
from app.services.validation.evidence import campos_suspeitos, validar_evidencias  # noqa: E402

CAMPOS_AVALIADOS = ["tipo_ato", "numero", "ano", "orgao_emissor", "data_assinatura", "data_publicacao"]

# Campos textuais "livres" (nome de órgão) são comparados de forma tolerante:
# correspondência por substring, normalizada, em vez de igualdade estrita — o
# mesmo órgão pode ser escrito de formas diferentes (sigla, nome completo,
# abreviações) tanto pelo modelo quanto pelo gabarito.
CAMPOS_TEXTO_LIVRE = {"orgao_emissor"}


def _normalizar(valor: str) -> str:
    return " ".join(valor.split()).strip().lower()


def _normalizar_numero(valor: str) -> str:
    """Remove zeros à esquerda para tolerar "001" vs "1", mantendo dígitos."""
    apenas_digitos = "".join(c for c in valor if c.isdigit())
    return apenas_digitos.lstrip("0") or "0"


def _campos_bate(campo: str, esperado, obtido) -> bool:
    if esperado is None and obtido is None:
        return True
    if esperado is None or obtido is None:
        return False
    if campo == "numero":
        return _normalizar_numero(str(esperado)) == _normalizar_numero(str(obtido))
    if campo in CAMPOS_TEXTO_LIVRE:
        a, b = _normalizar(str(esperado)), _normalizar(str(obtido))
        return a in b or b in a
    return str(esperado) == str(obtido)


def _processar_um(caminho_pdf: Path, settings) -> dict:
    conteudo = caminho_pdf.read_bytes()
    texto = extrair_texto_pdf(conteudo)
    conteudo_modelo = preparar_conteudo_para_modelo(
        texto.texto, max_chars=settings.segmentation_max_chars, head_ratio=settings.segmentation_head_ratio
    )
    prompt_sistema = settings.prompt_path.read_text(encoding="utf-8")
    provider = get_ai_provider(settings)

    inicio = time.perf_counter()
    resultado = provider.extrair(texto_documento=conteudo_modelo.texto, prompt_sistema=prompt_sistema)
    duracao_s = time.perf_counter() - inicio

    checks = validar_evidencias(texto.texto, resultado.ato)
    confianca = calcular_confianca(resultado.ato, checks)

    ato = resultado.ato
    return {
        "tipo_ato": ato.tipo_ato.value,
        "numero": ato.numero,
        "ano": ato.ano,
        "orgao_emissor": ato.orgao_emissor,
        "data_assinatura": ato.data_assinatura.isoformat() if ato.data_assinatura else None,
        "data_publicacao": ato.data_publicacao.isoformat() if ato.data_publicacao else None,
        "confianca_calculada": confianca,
        "campos_suspeitos": campos_suspeitos(ato, checks),
        "tokens_entrada": resultado.tokens_entrada,
        "tokens_saida": resultado.tokens_saida,
        "custo_estimado_usd": resultado.custo_estimado_usd,
        "latencia_s": round(duracao_s, 2),
        "truncado": conteudo_modelo.truncado,
    }


def main() -> None:
    settings = get_settings()
    gabarito = json.loads((EVALUATION_DIR / "dataset" / "ground_truth.json").read_text(encoding="utf-8"))

    linhas_relatorio: list[str] = []
    acertos_por_campo = {campo: 0 for campo in CAMPOS_AVALIADOS}
    total_documentos = 0
    resultados_brutos = []
    custo_total = 0.0

    for entrada in gabarito:
        caminho_pdf = EVALUATION_DIR / "dataset" / "pdfs" / entrada["arquivo"]
        if not caminho_pdf.exists():
            print(f"[AVISO] PDF não encontrado, pulando: {caminho_pdf}")
            continue

        print(f"Processando {entrada['arquivo']}...")
        try:
            predito = _processar_um(caminho_pdf, settings)
        except (PdfExtractionError, AIExtractionError) as exc:
            print(f"  ERRO ao processar {entrada['arquivo']}: {exc}")
            resultados_brutos.append({"arquivo": entrada["arquivo"], "erro": str(exc)})
            continue

        total_documentos += 1
        acertos_deste_documento = {}
        for campo in CAMPOS_AVALIADOS:
            bateu = _campos_bate(campo, entrada.get(campo), predito.get(campo))
            acertos_deste_documento[campo] = bateu
            if bateu:
                acertos_por_campo[campo] += 1

        custo_total += predito.get("custo_estimado_usd") or 0.0
        resultados_brutos.append(
            {
                "arquivo": entrada["arquivo"],
                "esperado": {c: entrada.get(c) for c in CAMPOS_AVALIADOS},
                "obtido": predito,
                "acertos_por_campo": acertos_deste_documento,
            }
        )

    if total_documentos == 0:
        print("Nenhum documento processado com sucesso. Abortando geração de relatório.")
        return

    linhas_relatorio.append(f"# Resultado da avaliação — {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z")
    linhas_relatorio.append("")
    linhas_relatorio.append(f"Modelo: `{settings.ai_model}` · Prompt: `{settings.prompt_version}`")
    linhas_relatorio.append(f"Documentos avaliados: {total_documentos} de {len(gabarito)}")
    linhas_relatorio.append(f"Custo estimado total: US$ {custo_total:.4f}")
    linhas_relatorio.append("")
    linhas_relatorio.append("| Campo | Acurácia |")
    linhas_relatorio.append("|---|---|")
    for campo in CAMPOS_AVALIADOS:
        acuracia = acertos_por_campo[campo] / total_documentos
        linhas_relatorio.append(f"| {campo} | {acuracia:.0%} ({acertos_por_campo[campo]}/{total_documentos}) |")

    acuracia_media = sum(acertos_por_campo.values()) / (len(CAMPOS_AVALIADOS) * total_documentos)
    linhas_relatorio.append("")
    linhas_relatorio.append(f"**Acurácia média entre campos: {acuracia_media:.0%}**")
    linhas_relatorio.append("")
    linhas_relatorio.append("## Detalhe por documento")
    for r in resultados_brutos:
        if "erro" in r:
            linhas_relatorio.append(f"- `{r['arquivo']}`: ERRO — {r['erro']}")
            continue
        campos_errados = [c for c, ok in r["acertos_por_campo"].items() if not ok]
        status = "todos os campos avaliados corretos" if not campos_errados else f"divergências em: {', '.join(campos_errados)}"
        linhas_relatorio.append(f"- `{r['arquivo']}`: {status}")

    relatorio_md = "\n".join(linhas_relatorio)
    print("\n" + relatorio_md)

    (EVALUATION_DIR / "results_latest.md").write_text(relatorio_md, encoding="utf-8")
    (EVALUATION_DIR / "results_latest.json").write_text(
        json.dumps(
            {
                "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "modelo": settings.ai_model,
                "prompt_versao": settings.prompt_version,
                "acuracia_por_campo": {c: acertos_por_campo[c] / total_documentos for c in CAMPOS_AVALIADOS},
                "acuracia_media": acuracia_media,
                "custo_total_usd": custo_total,
                "resultados": resultados_brutos,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\nRelatório salvo em evaluation/results_latest.md e evaluation/results_latest.json")


if __name__ == "__main__":
    main()
