"""Serviço de aplicação para consulta e correção de atos já processados (seções 9,
19 e 20 do desafio). Mantém regra de negócio fora dos endpoints da API.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.ato import Ato, Correcao
from app.schemas.extraction_contract import AtoExtraido
from app.services.extraction_service import CAMPOS_CORRIGIVEIS


class AtoNaoEncontradoError(Exception):
    pass


class CampoInvalidoError(Exception):
    pass


class ArquivoOriginalIndisponivelError(Exception):
    pass


def listar_atos(
    db: Session,
    *,
    tipo_ato: str | None = None,
    orgao_emissor: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    busca: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Ato], int]:
    query = db.query(Ato)

    if tipo_ato:
        query = query.filter(Ato.tipo_ato == tipo_ato)
    if orgao_emissor:
        query = query.filter(Ato.orgao_emissor.ilike(f"%{orgao_emissor}%"))
    if data_inicio:
        query = query.filter(Ato.data_publicacao >= data_inicio.isoformat())
    if data_fim:
        query = query.filter(Ato.data_publicacao <= data_fim.isoformat())
    if busca:
        termo = f"%{busca}%"
        query = query.filter(
            or_(
                Ato.assunto.ilike(termo),
                Ato.orgao_emissor.ilike(termo),
                Ato.numero.ilike(termo),
                Ato.nome_arquivo_original.ilike(termo),
            )
        )

    total = query.count()
    itens = (
        query.order_by(Ato.criado_em.desc()).offset(offset).limit(limit).all()
    )
    return itens, total


def obter_ato(db: Session, ato_id: str) -> Ato:
    ato = db.get(Ato, ato_id)
    if ato is None:
        raise AtoNaoEncontradoError(f"Ato {ato_id} não encontrado.")
    return ato


def caminho_arquivo_original(db: Session, ato_id: str, settings: Settings | None = None) -> Path:
    ato = obter_ato(db, ato_id)
    if ato.origem != "pdf" or not ato.caminho_arquivo_original:
        raise ArquivoOriginalIndisponivelError(
            "Este ato foi enviado como texto colado; não há arquivo PDF original."
        )
    caminho = Path(ato.caminho_arquivo_original)
    if not caminho.exists():
        raise ArquivoOriginalIndisponivelError("O arquivo original não foi encontrado no armazenamento.")
    return caminho


def corrigir_campo(db: Session, ato_id: str, *, campo: str, novo_valor: Any) -> Ato:
    """Aplica uma correção humana a um campo de topo do contrato.

    A correção é validada revalidando o AtoExtraido inteiro com o novo valor
    (garante que a correção humana também respeita o schema/enums do contrato), e
    fica registrada em duas frentes: o histórico em `correcoes` (auditoria
    completa) e `fontes_dos_campos[campo] = "humano"` no registro atual (para a
    interface distinguir "gerado pela IA" de "corrigido por pessoa").
    """
    if campo not in CAMPOS_CORRIGIVEIS:
        raise CampoInvalidoError(f"Campo '{campo}' não é corrigível ou não existe no contrato.")

    ato = obter_ato(db, ato_id)
    resultado_atual = dict(ato.resultado_estruturado)
    valor_anterior = resultado_atual.get(campo)

    resultado_atual[campo] = novo_valor
    try:
        ato_validado = AtoExtraido.model_validate(resultado_atual)
    except Exception as exc:
        raise CampoInvalidoError(f"Valor inválido para o campo '{campo}': {exc}") from exc

    ato.resultado_estruturado = ato_validado.model_dump(mode="json")
    fontes = dict(ato.fontes_dos_campos)
    fontes[campo] = "humano"
    ato.fontes_dos_campos = fontes

    # Uma correção humana é, por definição, a informação correta segundo quem
    # revisou o documento — não faz sentido continuar marcando o campo como
    # suspeito por falta de evidência automática.
    if campo in ato.campos_suspeitos:
        ato.campos_suspeitos = [c for c in ato.campos_suspeitos if c != campo]

    _sincronizar_colunas_denormalizadas(ato, ato_validado)

    db.add(
        Correcao(
            ato_id=ato.id,
            campo=campo,
            valor_anterior={"valor": valor_anterior},
            valor_novo={"valor": novo_valor},
        )
    )
    db.commit()
    db.refresh(ato)
    return ato


def _sincronizar_colunas_denormalizadas(ato: Ato, resultado: AtoExtraido) -> None:
    ato.tipo_ato = resultado.tipo_ato.value
    ato.numero = resultado.numero
    ato.ano = resultado.ano
    ato.orgao_emissor = resultado.orgao_emissor
    ato.data_assinatura = resultado.data_assinatura.isoformat() if resultado.data_assinatura else None
    ato.data_publicacao = resultado.data_publicacao.isoformat() if resultado.data_publicacao else None
    ato.assunto = resultado.assunto
