from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.atos import router as atos_router
from app.core.config import get_settings
from app.models.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Extração Estruturada de Atos Oficiais",
    description=(
        "API que recebe atos administrativos (PDF ou texto colado), extrai o "
        "conteúdo, envia a um modelo de linguagem para extração estruturada, "
        "valida schema e evidências, e persiste o resultado de forma auditável. "
        "Consulte também /api/atos para listar, filtrar e corrigir atos processados."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def erro_nao_tratado(request: Request, exc: Exception) -> JSONResponse:
    """Rede de segurança final: qualquer exceção não tratada explicitamente vira
    uma mensagem genérica e amigável, nunca um stack trace exposto ao usuário
    (seção 12/15/44 do desafio). O detalhe técnico vai para o log do servidor."""
    logger.exception("Erro não tratado ao processar %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Ocorreu um erro inesperado ao processar a solicitação."},
    )


app.include_router(atos_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
