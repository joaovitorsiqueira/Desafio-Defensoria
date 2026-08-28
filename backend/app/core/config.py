from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Configuração centralizada da aplicação, lida a partir de variáveis de ambiente.

    Mantida em um único lugar (em vez de espalhada por serviços) para que preço de
    modelo, limites de upload e caminhos de armazenamento sejam auditáveis e fáceis
    de alterar sem caçar valores mágicos pelo código.
    """

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    ai_provider: str = "ollama"
    ai_model: str = "qwen3:8b"
    anthropic_api_key: str | None = None

    ollama_base_url: str = "http://localhost:11434"
    # Contexto explícito enviado ao Ollama. O padrão de muitos modelos no Ollama é
    # bem menor que o suportado pelo modelo (frequentemente 2048-4096), então é
    # necessário pedir explicitamente um contexto maior para caber
    # prompt de sistema + documento + schema de saída.
    ollama_num_ctx: int = 16384
    # Qwen3 é um modelo "híbrido" com um modo de raciocínio interno opcional.
    # Desligado por padrão nesta tarefa: extração estruturada não se beneficia de
    # cadeia de raciocínio longa o suficiente para justificar o custo de latência,
    # e o modo padrão já produz JSON válido de forma confiável nos testes.
    ollama_think: bool = False

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'storage' / 'atos.db').as_posix()}"
    storage_dir: Path = BACKEND_DIR / "storage" / "atos"

    max_upload_mb: int = 15
    max_text_chars: int = 200_000

    # Limite de caracteres do texto enviado ao modelo antes de acionar a estratégia
    # de truncamento (cabeçalho + trecho final). Ver DECISOES.md, seção "Documentos
    # longos".
    segmentation_max_chars: int = 24_000
    segmentation_head_ratio: float = 0.7

    prompt_version: str = "extraction_v1"
    prompts_dir: Path = PROJECT_ROOT / "prompts"

    ai_max_attempts: int = 2
    # Inferência local (Ollama) em CPU/GPU de desenvolvimento pode ser bem mais
    # lenta que uma API de nuvem, especialmente em documentos longos truncados
    # perto do limite de SEGMENTATION_MAX_CHARS. Em testes reais, um despacho de
    # 72 páginas levou entre ~4 e ~4,5 minutos (258s medidos em uma execução) —
    # perto o suficiente do teto anterior de 300s para estourar por variações
    # normais de carga da máquina (por isso o valor foi elevado). Como cada
    # tentativa malsucedida só é reportada ao usuário depois desse tempo todo
    # (multiplicado por AI_MAX_ATTEMPTS), esse número é um teto de segurança,
    # não a duração esperada da maioria dos documentos.
    ai_request_timeout_seconds: float = 600.0

    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def prompt_path(self) -> Path:
        return self.prompts_dir / f"{self.prompt_version}.txt"


@lru_cache
def get_settings() -> Settings:
    return Settings()
