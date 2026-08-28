"""Serviço de aplicação que orquestra o pipeline completo de processamento de um
ato (seção 6/35 do desafio):

PDF/texto → extração de texto → preparação de conteúdo (segmentação) → modelo de
linguagem → structured output → validação Pydantic → validação de evidências →
tratamento de inconsistências → persistência.

Este é o único módulo que conhece a ordem completa do pipeline. A camada de API
(app/api/atos.py) só chama os métodos públicos daqui e traduz exceções de negócio
em respostas HTTP amigáveis — nunca implementa regra de negócio ela mesma.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.ato import Ato
from app.schemas.extraction_contract import AtoExtraido
from app.services.ai.factory import get_ai_provider
from app.services.ai.provider import AIExtractionError
from app.services.extraction.segmentation import preparar_conteudo_para_modelo
from app.services.pdf.extractor import (
    PdfExtractionError,
    TextoExtraido,
    extrair_texto_pdf,
    validar_texto_colado,
)
from app.services.validation.confidence import calcular_confianca
from app.services.validation.evidence import EvidenceCheck, campos_suspeitos, validar_evidencias

logger = logging.getLogger(__name__)

# Campos de topo do contrato que o usuário pode corrigir manualmente. `meta` fica
# de fora: é metadado do processo de extração, não um dado do ato em si.
CAMPOS_CORRIGIVEIS: tuple[str, ...] = (
    "tipo_ato",
    "numero",
    "ano",
    "orgao_emissor",
    "data_assinatura",
    "data_publicacao",
    "assunto",
    "resumo",
    "signatarios",
    "pessoas_citadas",
    "fundamentacao_legal",
    "atos_relacionados",
    "vigencia",
    "palavras_chave",
)


class ExtractionService:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()

    def processar_pdf(self, db: Session, *, conteudo: bytes, nome_arquivo: str) -> Ato:
        texto = extrair_texto_pdf(conteudo)
        ato = self._processar(db, texto=texto, origem="pdf", nome_arquivo=nome_arquivo)
        self._salvar_arquivo_original(ato.id, conteudo, sufixo=".pdf")
        ato.caminho_arquivo_original = str(self._settings.storage_dir / f"{ato.id}.pdf")
        db.commit()
        db.refresh(ato)
        return ato

    def processar_texto(self, db: Session, *, texto_colado: str) -> Ato:
        texto = validar_texto_colado(texto_colado)
        return self._processar(db, texto=texto, origem="texto", nome_arquivo=None)

    # -- internos -----------------------------------------------------------------

    def _processar(
        self, db: Session, *, texto: TextoExtraido, origem: str, nome_arquivo: str | None
    ) -> Ato:
        conteudo_modelo = preparar_conteudo_para_modelo(
            texto.texto,
            max_chars=self._settings.segmentation_max_chars,
            head_ratio=self._settings.segmentation_head_ratio,
        )

        prompt_sistema = self._settings.prompt_path.read_text(encoding="utf-8")
        provider = get_ai_provider(self._settings)

        try:
            resultado = provider.extrair(
                texto_documento=conteudo_modelo.texto, prompt_sistema=prompt_sistema
            )
        except AIExtractionError:
            logger.exception("Falha ao obter extração estruturada da IA")
            raise

        checks = validar_evidencias(texto.texto, resultado.ato)
        suspeitos = campos_suspeitos(resultado.ato, checks)
        confianca_calculada = calcular_confianca(resultado.ato, checks)

        ato_resultado = resultado.ato.model_copy(deep=True)
        ato_resultado.meta.confianca_geral = confianca_calculada

        fontes_dos_campos = {campo: "ia" for campo in CAMPOS_CORRIGIVEIS}

        ato = Ato(
            origem=origem,
            nome_arquivo_original=nome_arquivo,
            texto_extraido=texto.texto,
            texto_enviado_ao_modelo=conteudo_modelo.texto,
            truncado=conteudo_modelo.truncado,
            status="concluido",
            resultado_estruturado=ato_resultado.model_dump(mode="json"),
            resultado_ia_original=resultado.raw_json,
            campos_suspeitos=suspeitos,
            evidencias_validadas=[
                {
                    "campo": c.campo,
                    "evidencia": c.evidencia,
                    "encontrada": c.encontrada,
                    "match_type": c.match_type,
                }
                for c in checks
            ],
            campos_nao_encontrados=ato_resultado.meta.campos_nao_encontrados,
            fontes_dos_campos=fontes_dos_campos,
            confianca_geral=confianca_calculada,
            prompt_versao=self._settings.prompt_version,
            modelo_ia=resultado.modelo,
            tokens_entrada=resultado.tokens_entrada,
            tokens_saida=resultado.tokens_saida,
            latencia_ms=resultado.latencia_ms,
            custo_estimado_usd=resultado.custo_estimado_usd,
            tentativas_ia=resultado.tentativas,
            **_campos_denormalizados(ato_resultado),
        )
        db.add(ato)
        db.commit()
        db.refresh(ato)
        return ato

    def _salvar_arquivo_original(self, ato_id: str, conteudo: bytes, *, sufixo: str) -> None:
        self._settings.storage_dir.mkdir(parents=True, exist_ok=True)
        caminho = self._settings.storage_dir / f"{ato_id}{sufixo}"
        caminho.write_bytes(conteudo)


def _campos_denormalizados(ato: AtoExtraido) -> dict:
    return {
        "tipo_ato": ato.tipo_ato.value,
        "numero": ato.numero,
        "ano": ato.ano,
        "orgao_emissor": ato.orgao_emissor,
        "data_assinatura": ato.data_assinatura.isoformat() if ato.data_assinatura else None,
        "data_publicacao": ato.data_publicacao.isoformat() if ato.data_publicacao else None,
        "assunto": ato.assunto,
    }
