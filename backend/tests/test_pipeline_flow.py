"""Teste do fluxo principal de processamento (seção 27 do desafio, item opcional
"se houver tempo"), com o provedor de IA substituído por um dublê determinístico —
não faz chamada de rede, então roda em qualquer ambiente sem chave de API.
"""
from app.core.config import Settings
from app.schemas.extraction_contract import AtoExtraido, Evidencias, Meta
from app.services import extraction_service as extraction_service_module
from app.services.ai.provider import AIExtractionOutcome
from app.services.extraction_service import ExtractionService

TEXTO_ATO = """
PORTARIA Nº 250, DE 8 DE ABRIL DE 2025

O Defensor Público-Geral do Estado de Goiás resolve:

Art. 1º Reconduzir ÂNGELA CRISTINA DOS SANTOS FERREIRA no cargo de Ouvidora-Geral.

Gabinete do Defensor Público-Geral do Estado, em Goiânia, 8 de abril de 2025.

TIAGO GREGÓRIO FERNANDES
Defensor Público-Geral do Estado
"""


class _FakeProvider:
    def __init__(self, ato: AtoExtraido):
        self._ato = ato

    def extrair(self, *, texto_documento: str, prompt_sistema: str) -> AIExtractionOutcome:
        return AIExtractionOutcome(
            ato=self._ato,
            raw_json=self._ato.model_dump(mode="json"),
            modelo="claude-sonnet-5",
            tokens_entrada=1200,
            tokens_saida=400,
            latencia_ms=1500,
            tentativas=1,
            custo_estimado_usd=0.0064,
        )


def _ato_extraido_de_teste() -> AtoExtraido:
    return AtoExtraido.model_validate(
        {
            "tipo_ato": "PORTARIA",
            "numero": "250",
            "ano": 2025,
            "orgao_emissor": "Defensoria Pública-Geral do Estado",
            "data_assinatura": "2025-04-08",
            "assunto": "Recondução de Ouvidora-Geral da Defensoria Pública do Estado",
            "resumo": "A portaria reconduz Ângela Cristina dos Santos Ferreira ao cargo de Ouvidora-Geral.",
            "signatarios": [
                {"nome": "TIAGO GREGÓRIO FERNANDES", "cargo": "Defensor Público-Geral do Estado"}
            ],
            "pessoas_citadas": [
                {
                    "nome": "ÂNGELA CRISTINA DOS SANTOS FERREIRA",
                    "identificador": None,
                    "cargo": "Ouvidora-Geral",
                    "papel": "OUTRO",
                }
            ],
            "meta": {
                "campos_nao_encontrados": ["data_publicacao"],
                "confianca_geral": 0.9,
                "evidencias": {
                    "numero": "PORTARIA Nº 250, DE 8 DE ABRIL DE 2025",
                    "data_assinatura": "Goiânia, 8 de abril de 2025",
                    "orgao_emissor": "Órgão inventado que não está no texto",
                },
            },
        }
    )


def test_pipeline_persiste_ato_com_evidencias_validadas_e_confianca_recalculada(
    db_session, tmp_path, monkeypatch
):
    settings = Settings(storage_dir=tmp_path, anthropic_api_key="sk-fake")
    monkeypatch.setattr(
        extraction_service_module,
        "get_ai_provider",
        lambda _settings: _FakeProvider(_ato_extraido_de_teste()),
    )

    service = ExtractionService(settings)
    ato = service.processar_texto(db_session, texto_colado=TEXTO_ATO)

    assert ato.status == "concluido"
    assert ato.tipo_ato == "PORTARIA"
    assert ato.numero == "250"

    # Evidência de orgao_emissor foi inventada (não está no texto) -> deve ser
    # marcada como suspeita, mas o valor não deve ser apagado.
    assert "orgao_emissor" in ato.campos_suspeitos
    assert ato.resultado_estruturado["orgao_emissor"] == "Defensoria Pública-Geral do Estado"

    # Evidência de data_assinatura bate no texto -> não deve ficar suspeita.
    assert "data_assinatura" not in ato.campos_suspeitos

    # Confiança recalculada programaticamente (não é mais o 0.9 "achismo" da IA).
    assert ato.confianca_geral != 0.9
    assert 0.0 <= ato.confianca_geral <= 1.0

    assert ato.fontes_dos_campos["orgao_emissor"] == "ia"
    assert ato.tokens_entrada == 1200
    assert ato.modelo_ia == "claude-sonnet-5"
