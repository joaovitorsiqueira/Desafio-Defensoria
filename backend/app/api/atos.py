"""Endpoints REST (seção 20 do desafio).

Os handlers aqui só fazem tradução HTTP <-> serviço: validam entrada de forma
superficial (tamanho/tipo de arquivo), chamam o serviço de aplicação
correspondente e traduzem exceções de negócio em respostas HTTP com mensagens
amigáveis. Nenhuma regra de negócio (extração, validação de evidência, cálculo de
confiança) mora neste módulo.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.database import get_db
from app.schemas.api import (
    AtoDetail,
    AtoListItem,
    AtoListResponse,
    Auditoria,
    CorrecaoRequest,
    EvidenceCheckOut,
    TextoUploadRequest,
)
from app.schemas.extraction_contract import AtoExtraido
from app.services import atos_service
from app.services.ai.provider import AIExtractionError
from app.services.extraction_service import ExtractionService
from app.services.pdf.extractor import PdfExtractionError

router = APIRouter(prefix="/api/atos", tags=["atos"])


def _ato_para_detail(ato) -> AtoDetail:
    return AtoDetail(
        id=ato.id,
        criado_em=ato.criado_em,
        atualizado_em=ato.atualizado_em,
        status=ato.status,
        mensagem_erro=ato.mensagem_erro,
        origem=ato.origem,
        nome_arquivo_original=ato.nome_arquivo_original,
        tem_arquivo_original=ato.origem == "pdf" and bool(ato.caminho_arquivo_original),
        texto_extraido=ato.texto_extraido,
        resultado=AtoExtraido.model_validate(ato.resultado_estruturado),
        resultado_ia_original=AtoExtraido.model_validate(ato.resultado_ia_original),
        campos_suspeitos=ato.campos_suspeitos,
        evidencias_validadas=[EvidenceCheckOut(**e) for e in ato.evidencias_validadas],
        fontes_dos_campos=ato.fontes_dos_campos,
        auditoria=Auditoria(
            prompt_versao=ato.prompt_versao,
            modelo_ia=ato.modelo_ia,
            tokens_entrada=ato.tokens_entrada,
            tokens_saida=ato.tokens_saida,
            latencia_ms=ato.latencia_ms,
            custo_estimado_usd=ato.custo_estimado_usd,
            tentativas_ia=ato.tentativas_ia,
            truncado=ato.truncado,
        ),
    )


@router.post("/upload", response_model=AtoDetail, status_code=201)
async def enviar_pdf(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AtoDetail:
    if arquivo.content_type not in ("application/pdf", "application/octet-stream") and not (
        arquivo.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um arquivo no formato PDF.")

    conteudo = await arquivo.read()
    limite_bytes = settings.max_upload_mb * 1024 * 1024
    if len(conteudo) > limite_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo maior que o limite permitido ({settings.max_upload_mb} MB).",
        )
    if not conteudo:
        raise HTTPException(status_code=400, detail="O arquivo enviado está vazio.")

    try:
        ato = ExtractionService(settings).processar_pdf(
            db, conteudo=conteudo, nome_arquivo=arquivo.filename or "documento.pdf"
        )
    except PdfExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _ato_para_detail(ato)


@router.post("/texto", response_model=AtoDetail, status_code=201)
def enviar_texto(
    payload: TextoUploadRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AtoDetail:
    if len(payload.texto) > settings.max_text_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Texto maior que o limite permitido ({settings.max_text_chars} caracteres).",
        )
    try:
        ato = ExtractionService(settings).processar_texto(db, texto_colado=payload.texto)
    except PdfExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _ato_para_detail(ato)


@router.get("", response_model=AtoListResponse)
def listar(
    db: Session = Depends(get_db),
    tipo_ato: str | None = None,
    orgao_emissor: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    busca: str | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AtoListResponse:
    itens, total = atos_service.listar_atos(
        db,
        tipo_ato=tipo_ato,
        orgao_emissor=orgao_emissor,
        data_inicio=data_inicio,
        data_fim=data_fim,
        busca=busca,
        limit=limit,
        offset=offset,
    )
    return AtoListResponse(
        items=[
            AtoListItem(
                id=ato.id,
                criado_em=ato.criado_em,
                status=ato.status,
                tipo_ato=ato.tipo_ato,
                numero=ato.numero,
                ano=ato.ano,
                orgao_emissor=ato.orgao_emissor,
                data_assinatura=ato.data_assinatura,
                data_publicacao=ato.data_publicacao,
                assunto=ato.assunto,
                confianca_geral=ato.confianca_geral,
                campos_suspeitos=ato.campos_suspeitos,
                tem_correcao_humana=any(v == "humano" for v in ato.fontes_dos_campos.values()),
            )
            for ato in itens
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{ato_id}", response_model=AtoDetail)
def detalhar(ato_id: str, db: Session = Depends(get_db)) -> AtoDetail:
    try:
        ato = atos_service.obter_ato(db, ato_id)
    except atos_service.AtoNaoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ato_para_detail(ato)


@router.get("/{ato_id}/documento")
def baixar_documento_original(
    ato_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    try:
        caminho = atos_service.caminho_arquivo_original(db, ato_id, settings)
    except atos_service.AtoNaoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except atos_service.ArquivoOriginalIndisponivelError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(caminho, media_type="application/pdf", filename=caminho.name)


@router.patch("/{ato_id}/campos", response_model=AtoDetail)
def corrigir_campo(ato_id: str, payload: CorrecaoRequest, db: Session = Depends(get_db)) -> AtoDetail:
    try:
        ato = atos_service.corrigir_campo(db, ato_id, campo=payload.campo, novo_valor=payload.valor)
    except atos_service.AtoNaoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except atos_service.CampoInvalidoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ato_para_detail(ato)
