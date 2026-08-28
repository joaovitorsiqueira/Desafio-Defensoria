"""Teste 1 e 2 da seção 27 do desafio: evidência válida e evidência inexistente."""
from app.schemas.extraction_contract import AtoExtraido
from app.services.validation.evidence import validar_evidencias

TEXTO_ORIGINAL = """
PORTARIA Nº 250, DE 8 DE ABRIL DE 2025

O Defensor Público-Geral do Estado de Goiás, no uso de suas atribuições legais...

Art. 1º Reconduzir ÂNGELA CRISTINA DOS SANTOS FERREIRA no cargo de Ouvidora-Geral.

Gabinete do Defensor Público-Geral do Estado, em Goiânia, 8 de abril de 2025.

TIAGO GREGÓRIO FERNANDES
Defensor Público-Geral do Estado
"""


def _ato(**overrides) -> AtoExtraido:
    """Constrói um AtoExtraido mínimo válido, com o(s) campo(s) sob teste
    preenchido(s) (a validação de evidência só roda para campos preenchidos)."""
    base = {
        "tipo_ato": "PORTARIA",
        "data_assinatura": "2025-04-08",
        "orgao_emissor": "Defensoria Pública-Geral do Estado",
        "signatarios": [{"nome": "Tiago", "cargo": "Defensor"}],
        "meta": {"campos_nao_encontrados": [], "confianca_geral": 0.9, "evidencias": {}},
    }
    base.update(overrides)
    return AtoExtraido.model_validate(base)


def _com_evidencias(**evidencias) -> AtoExtraido:
    return _ato(meta={"campos_nao_encontrados": [], "confianca_geral": 0.9, "evidencias": evidencias})


def test_evidencia_encontrada_no_texto_original():
    ato = _com_evidencias(data_assinatura="Goiânia, 8 de abril de 2025.")
    resultados = validar_evidencias(TEXTO_ORIGINAL, ato)

    assert len(resultados) == 1
    assert resultados[0].campo == "data_assinatura"
    assert resultados[0].encontrada is True
    assert resultados[0].match_type == "exata"


def test_evidencia_inexistente_e_marcada_como_nao_encontrada():
    ato = _com_evidencias(orgao_emissor="Secretaria de Fazenda do Município de Goiânia")
    resultados = validar_evidencias(TEXTO_ORIGINAL, ato)

    assert len(resultados) == 1
    assert resultados[0].encontrada is False
    assert resultados[0].match_type == "nao_encontrada"


def test_evidencia_com_quebras_de_linha_diferentes_ainda_e_encontrada():
    """A normalização de espaços/quebras de linha deve tolerar que o modelo copie
    um trecho que no PDF original estava quebrado em múltiplas linhas."""
    ato = _com_evidencias(signatarios="TIAGO GREGÓRIO FERNANDES\nDefensor Público-Geral do Estado")
    resultados = validar_evidencias(TEXTO_ORIGINAL, ato)

    assert resultados[0].encontrada is True


def test_evidencia_case_insensitive_e_marcada_com_tolerancia_explicita():
    ato = _com_evidencias(orgao_emissor="gabinete do defensor público-geral do estado")
    resultados = validar_evidencias(TEXTO_ORIGINAL, ato)

    assert resultados[0].encontrada is True
    assert resultados[0].match_type == "case_insensitive"


def test_campos_sem_evidencia_nao_geram_resultado():
    resultados = validar_evidencias(TEXTO_ORIGINAL, _com_evidencias())
    assert resultados == []


def test_evidencia_de_campo_nao_preenchido_e_ignorada():
    """Se o campo principal está vazio/nulo, uma evidência espúria não deve gerar
    ruído — não há nada de fato a auditar."""
    ato = _ato(fundamentacao_legal=[], meta={
        "campos_nao_encontrados": ["fundamentacao_legal"],
        "confianca_geral": 0.9,
        "evidencias": {"fundamentacao_legal": "não mencionada"},
    })
    resultados = validar_evidencias(TEXTO_ORIGINAL, ato)
    assert resultados == []
