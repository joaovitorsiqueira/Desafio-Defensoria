# Extração Estruturada de Atos Oficiais com IA

Prova de conceito que recebe um ato administrativo (portaria, resolução, despacho,
edital, instrução normativa) via upload de PDF ou texto colado, extrai o conteúdo,
envia a um modelo de linguagem para obter uma extração estruturada, valida o
resultado por schema e por evidências literais contra o texto original, persiste o
resultado e o apresenta de forma legível e auditável — com correção humana e
observabilidade (tokens, latência, custo).

Construída para o desafio técnico "Extração Estruturada de Atos Oficiais com
Inteligência Artificial". Decisões técnicas e o que ficou fora do escopo estão em
[`DECISOES.md`](DECISOES.md).

## 1. O problema

Diariamente são publicados atos administrativos em diário oficial. Hoje esse
acompanhamento é manual. O sistema resolve a extração estruturada de um ato por
vez, priorizando **confiabilidade e auditabilidade** sobre automação completa:
uma informação inventada é sempre pior do que uma informação ausente.

## 2. Arquitetura

```
Frontend (React + TS)
   │  REST (fetch)
   ▼
API (FastAPI) ──────────────────────────────► app/api/atos.py
   │  chama serviços de aplicação, nunca implementa regra de negócio
   ▼
Application Service ────────────────────────► app/services/extraction_service.py
   │
   ├─► PDF/Texto → extração de texto ───────► services/pdf/extractor.py
   ├─► Segmentação (documentos longos) ─────► services/extraction/segmentation.py
   ├─► IA (abstração de provedor) ──────────► services/ai/{provider,anthropic_provider,factory,pricing}.py
   │        └─ structured output + validação Pydantic (schemas/extraction_contract.py)
   ├─► Validação de evidências ──────────────► services/validation/evidence.py
   ├─► Cálculo de confiança ──────────────────► services/validation/confidence.py
   └─► Persistência (SQLAlchemy/SQLite) ─────► models/ato.py
```

A camada de IA não conhece a interface; a interface não conhece a API do provedor
de IA (toda chamada ao modelo passa pela abstração `AIProvider`). Ver seção 35 do
desafio e `DECISOES.md`.

## 3. Stack

- **Backend**: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite.
- **IA**: modelo local via **Ollama** (`qwen3:8b` por padrão) — structured output
  nativo (`format` com JSON Schema) + validação independente com Pydantic. Uma
  segunda implementação para **Anthropic Claude** também está pronta e é
  selecionável só trocando variáveis de ambiente (ver seção 3 abaixo e
  `DECISOES.md`).
- **PDF**: `pypdf` (extração de texto pura-Python, sem OCR).
- **Frontend**: React + TypeScript + Vite + Tailwind CSS (componentes próprios,
  no espírito do shadcn/ui — ver `DECISOES.md`).
- **Testes**: `pytest` (backend).

Justificativas completas em `DECISOES.md`.

## 4. Pré-requisitos

- Python 3.11+ (desenvolvido com 3.13)
- Node.js 20+ (desenvolvido com 24)
- **[Ollama](https://ollama.com/) instalado e em execução**, com o modelo
  `qwen3:8b` baixado — provedor de IA padrão deste projeto:
  ```bash
  ollama pull qwen3:8b
  ollama serve   # se não estiver rodando como serviço
  ```
  Alternativamente, uma chave de API da Anthropic
  (https://console.anthropic.com/) — ver "Usando a Anthropic em vez do Ollama"
  abaixo. Sem nenhum dos dois configurados, a aplicação sobe normalmente, mas o
  processamento de atos retorna um erro amigável.

## 5. Instalação e configuração

```bash
git clone <repositorio>
cd <repositorio>
cp .env.example .env
# os valores padrão já apontam para Ollama local em http://localhost:11434
```

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Usando a Anthropic em vez do Ollama

No `.env` da raiz do projeto:

```bash
AI_PROVIDER=anthropic
AI_MODEL=claude-sonnet-5
ANTHROPIC_API_KEY=sua-chave-aqui
```

Nenhuma outra mudança é necessária — a troca de provedor é só configuração (ver
`DECISOES.md`, seção "Modelo e provedor de IA").

A API sobe em `http://localhost:8000`. Documentação interativa (Swagger) em
`http://localhost:8000/docs`. O banco SQLite e os arquivos originais são criados
automaticamente em `backend/storage/` na primeira execução.

### Frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

A interface sobe em `http://localhost:5173` e já aponta para `http://localhost:8000`
por padrão (configurável via `VITE_API_BASE_URL` em `frontend/.env`, se necessário).

## 6. Como usar

- **Enviar um ato**: tela inicial (`/`) — arraste um PDF ou clique para selecionar,
  ou alterne para "Colar texto". O processamento leva alguns segundos (chamada ao
  modelo); há um indicador de carregamento explícito.
- **Consultar resultados**: `/atos` — lista os atos processados, com filtro por
  tipo de ato e por órgão, e busca textual (assunto, número, órgão, nome do
  arquivo). Estado vazio tratado.
- **Ver o detalhe**: clique em "Ver detalhe" — campos apresentados de forma legível
  (nunca o JSON cru), com distinção visual entre "não consta no documento" e "não
  foi possível extrair", badges para campos suspeitos (evidência não confirmada) e
  campos corrigidos por pessoa, botão "ver evidência" (mostra e destaca o trecho
  literal dentro do texto original) e link para o PDF original.
- **Corrigir um campo**: botão "editar" ao lado de qualquer campo no detalhe. A
  correção é salva, marcada como `humano` (distinta de `ia`), e registrada no
  histórico de correções.

## 7. API REST

Documentação completa e interativa em `/docs` (Swagger UI) ou `/redoc`. Endpoints
principais, todos sob `/api/atos`:

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/atos/upload` | Envia um PDF (multipart `arquivo`), roda o pipeline completo, retorna o ato processado. |
| POST | `/api/atos/texto` | Envia texto colado (`{"texto": "..."}`), mesmo pipeline. |
| GET | `/api/atos` | Lista atos, com filtros `tipo_ato`, `orgao_emissor`, `data_inicio`, `data_fim`, `busca`, paginação `limit`/`offset`. |
| GET | `/api/atos/{id}` | Detalhe completo: resultado estruturado, evidências validadas, campos suspeitos, fontes (ia/humano), auditoria. |
| GET | `/api/atos/{id}/documento` | Baixa o PDF original (quando o ato veio de upload). |
| PATCH | `/api/atos/{id}/campos` | Corrige um campo de topo do contrato (`{"campo": "...", "valor": ...}`). |

Todos os endpoints só traduzem HTTP ↔ serviço de aplicação; a regra de negócio
mora em `app/services/`.

## 8. Testes

```bash
cd backend
.venv/Scripts/activate  # ou source .venv/bin/activate
pytest -v
```

Cobertura deliberadamente enxuta (conforme o desafio pede): validação de evidência
(trecho existente vs. inexistente), validação de schema/enums, e um teste do fluxo
principal de processamento com um provedor de IA "dublê" (sem chamada de rede).

## 9. Avaliação

Com o Ollama em execução e `qwen3:8b` baixado (configuração padrão):

```bash
python evaluation/evaluate.py
```

(Se estiver usando o provedor Anthropic, basta ter `.env` configurado com
`AI_PROVIDER=anthropic` e `ANTHROPIC_API_KEY` antes de rodar o comando acima.)

Processa os 5 atos de desenvolvimento contra um gabarito manual e calcula
acurácia por campo (`tipo_ato`, `numero`, `ano`, `orgao_emissor`,
`data_assinatura`, `data_publicacao`). Resultado da última execução em
`evaluation/results_latest.md`. Detalhes em `evaluation/README.md`.

## 10. Estratégia para documentos longos

Um ato pode ter dezenas de páginas (tabelas, anexos). Em vez de enviar o texto
inteiro cegamente, a aplicação aplica um truncamento por cabeçalho + trecho final
quando o texto excede um limite configurável (`SEGMENTATION_MAX_CHARS`, padrão
24.000 caracteres): mantém o início (onde tipicamente estão tipo/número/ano/ementa/
fundamentação) e o fim (onde tipicamente está a assinatura/data), descartando o
meio, sem nunca cortar uma linha ao meio. O corte é registrado nos metadados de
auditoria do ato (`truncado: true/false`). Justificativa completa em
`DECISOES.md`.

## 11. Estratégia contra alucinação

- **Instrução de abstenção explícita** no prompt (`prompts/extraction_v1.txt`):
  nunca preencher por suposição, usar `null`/`[]` quando a informação não constar
  do documento, não usar conhecimento externo.
- **Saída estruturada nativa** (`output_format` via `client.messages.parse`), não
  regex sobre texto livre.
- **Validação de schema independente** (Pydantic) após a resposta do modelo.
- **Validação programática de evidências**: cada evidência literal fornecida pela
  IA é verificada contra o texto original extraído do PDF; se não bate, o campo é
  marcado como suspeito e a interface o exibe como não confirmado (nunca como
  informação validada).
- **Confiança recalculada de forma determinística**, não repassando a
  autoavaliação subjetiva do modelo como se fosse uma probabilidade calibrada.
- Sobre temperatura: com o provedor padrão (Ollama), `temperature=0` é enviado
  explicitamente. Mesmo assim, temperatura baixa por si só nunca eliminaria
  alucinação — apenas reduz a variância de amostragem token a token. O controle
  real vem da combinação de schema estruturado + validação de evidências +
  comportamento conservador diante de inconsistência, que é o que efetivamente
  capturou, nos testes reais deste projeto, casos em que o modelo local citou
  uma "evidência" parafraseada para um valor que, por acaso, estava correto (ver
  `DECISOES.md`).

Detalhes completos em `DECISOES.md`.

## 12. Observabilidade e custo

Por documento processado, são registrados: modelo usado, versão do prompt,
tokens de entrada/saída, latência, número de tentativas até sucesso, se o
documento foi truncado, e custo estimado em USD (calculado a partir de uma
tabela de preços centralizada em `app/services/ai/pricing.py` — nunca um valor
"chutado"). Com o provedor padrão (Ollama, modelo local), o custo estimado é
US$ 0,00 — não há cobrança por token; com o provedor Anthropic, o custo reflete
os preços públicos vigentes do modelo escolhido. Visível na tela de detalhe do
ato, seção "Confiança e auditoria".

## 13. Dados pessoais e envio a terceiros

Atos administrativos publicados em diário oficial são documentos públicos, mas
frequentemente contêm nomes, cargos e, ocasionalmente, números de
matrícula/CPF/RG de pessoas físicas.

Com o provedor padrão deste projeto (Ollama, modelo local), **nenhum dado sai da
máquina** — o texto do documento nunca trafega para um serviço de terceiros.
Essa é uma das razões práticas para essa escolha ter sido viável como padrão
sem preocupação adicional de compliance. Ainda assim, se a aplicação for
configurada para usar um provedor de IA em nuvem (Anthropic ou qualquer outro),
antes de enviar documentos institucionais reais uma instituição deveria
considerar:

- **Política de retenção de dados do provedor**: por padrão, a API da Anthropic
  não usa dados de clientes de API para treinar modelos, mas ainda assim os
  dados trafegam para infraestrutura de terceiros — vale revisar os termos de
  retenção vigentes e, quando disponível, contratar zero data retention.
- **Base legal / LGPD**: dados de servidores públicos em atos oficiais têm amparo
  em transparência ativa, mas o envio a um processador terceiro (o provedor de
  IA) ainda configura tratamento de dados pessoais sujeito à LGPD — vale
  formalizar isso (contrato, DPA) antes de um uso institucional real.
- **Minimização**: nada impede, tecnicamente, restringir o envio a apenas os
  trechos relevantes do documento (o que a própria estratégia de segmentação já
  faz parcialmente por outro motivo).

Este projeto não implementa nenhum mecanismo técnico de anonimização — é uma
decisão consciente de manter o escopo dentro do que o desafio pede, mas o ponto
está registrado aqui e em `DECISOES.md` porque o desafio pede explicitamente essa
reflexão.

## 14. Limitações conhecidas

- O provedor padrão (Ollama + `qwen3:8b`, um modelo local de 8B parâmetros) é
  sensivelmente mais lento que uma API de nuvem (dezenas de segundos por
  documento em hardware de desenvolvimento) e segue instruções de forma menos
  precisa que modelos de fronteira — em especial na literalidade das evidências
  citadas. Isso é esperado e discutido em detalhe em `DECISOES.md`; é também a
  melhor demonstração prática de por que a validação programática de
  evidências é indispensável, e não apenas uma formalidade.
- PDFs escaneados como imagem (sem camada de texto) não são suportados — não há
  OCR nesta versão (ver `DECISOES.md`, "o que quebraria em produção").
- A extração de listas muito longas de pessoas (ex.: dezenas de nomes em uma
  única tabela, como no `ato_03` do conjunto de avaliação) pode ficar incompleta
  quando o documento é truncado pela estratégia de documentos longos.
- `orgao_emissor` e outros campos de texto livre não têm correção ortográfica —
  o valor é extraído literalmente como aparece no documento.
- Sem autenticação, autorização ou suporte a múltiplos usuários (fora de escopo,
  ver seção 7 do desafio).
- Processamento é síncrono (uma requisição HTTP = um processamento completo);
  não há fila/worker em background — adequado para uso de um usuário por vez,
  não para volume de produção (ver `DECISOES.md`).
