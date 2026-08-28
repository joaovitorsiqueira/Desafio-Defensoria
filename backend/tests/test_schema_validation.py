"""Teste 3 da seção 27 do desafio: validação de schema/enums do contrato de
extração. Garante que valores fora do enum são rejeitados (nunca aceitos
silenciosamente) e que os campos ausentes assumem null/[] em vez de serem
inventados."""
import pytest
from pydantic import ValidationError

from app.schemas.extraction_contract import AtoExtraido, PapelPessoa, TipoAto


def _payload_minimo(**overrides):
    base = {
        "tipo_ato": "PORTARIA",
        "meta": {"campos_nao_encontrados": [], "confianca_geral": 0.8},
    }
    base.update(overrides)
    return base


def test_enum_invalido_de_tipo_ato_e_rejeitado():
    with pytest.raises(ValidationError):
        AtoExtraido.model_validate(_payload_minimo(tipo_ato="MEMORANDO"))


def test_enum_invalido_de_papel_pessoa_e_rejeitado():
    payload = _payload_minimo(
        pessoas_citadas=[{"nome": "Fulano de Tal", "papel": "PROMOVIDO"}]
    )
    with pytest.raises(ValidationError):
        AtoExtraido.model_validate(payload)


def test_confianca_fora_do_intervalo_e_rejeitada():
    payload = _payload_minimo(meta={"campos_nao_encontrados": [], "confianca_geral": 1.5})
    with pytest.raises(ValidationError):
        AtoExtraido.model_validate(payload)


def test_campos_ausentes_viram_null_ou_lista_vazia_por_padrao():
    ato = AtoExtraido.model_validate(_payload_minimo())

    assert ato.numero is None
    assert ato.ano is None
    assert ato.orgao_emissor is None
    assert ato.data_assinatura is None
    assert ato.signatarios == []
    assert ato.pessoas_citadas == []
    assert ato.fundamentacao_legal == []
    assert ato.atos_relacionados == []
    assert ato.palavras_chave == []


def test_payload_valido_e_aceito_com_enums_corretos():
    payload = _payload_minimo(
        tipo_ato=TipoAto.DESPACHO.value,
        pessoas_citadas=[
            {"nome": "Fulano de Tal", "identificador": None, "cargo": "Defensor Público", "papel": PapelPessoa.DESIGNADO.value}
        ],
    )
    ato = AtoExtraido.model_validate(payload)
    assert ato.tipo_ato == TipoAto.DESPACHO
    assert ato.pessoas_citadas[0].papel == PapelPessoa.DESIGNADO
