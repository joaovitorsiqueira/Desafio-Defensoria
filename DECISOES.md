# Decisões técnicas

Registro das escolhas conscientes feitas nos pontos que o desafio deixou em
aberto, por quê, e o que isso custa. Ver também os comentários de topo de cada
módulo no código, que explicam a decisão local correspondente.

## Back-end: Python + FastAPI + Pydantic + SQLAlchemy + SQLite

Escolha sugerida pelo próprio desafio, mantida sem alteração: Pydantic dá
validação de schema e enums "de graça" e é o mesmo formalismo usado para pedir
saída estruturada ao modelo (menos um lugar para as duas definições
divergirem); SQLite elimina qualquer dependência de infraestrutura externa para
rodar o projeto localmente, coerente com o escopo de prova de conceito.

## Modelo e provedor de IA: Ollama local, `qwen3:8b` (padrão) — Anthropic Claude como alternativa implementada

O desafio deixa a escolha do modelo livre, incluindo explicitamente "modelo
local via Ollama" como opção sem prejuízo na avaliação. O provedor padrão deste
projeto é **Ollama rodando `qwen3:8b` localmente**. Motivo prático: por já haver
Ollama instalado com esse modelo baixado no ambiente de desenvolvimento, essa é
a configuração que efetivamente foi testada de ponta a ponta contra os cinco
atos fornecidos.

A abstração `AIProvider` (`app/services/ai/provider.py`) foi desenhada desde o
início para tornar essa escolha reversível: `app/services/ai/anthropic_provider.py`
é uma segunda implementação completa e funcional (structured output nativo via
`client.messages.parse`, mesmo contrato de retorno, mesma lógica de retry),
selecionável apenas trocando `AI_PROVIDER=anthropic` e `AI_MODEL` no `.env` —
nenhuma linha de `extraction_service.py`, da API ou do front-end muda. Isso
existe para que a troca de provedor seja uma decisão de configuração, não uma
reescrita, caso o ambiente de avaliação prefira (ou só tenha disponível) uma
API de nuvem.

**Trade-offs observados de usar um modelo local de 8B parâmetros**, registrados
com transparência porque afetam diretamente a "qualidade da extração" avaliada:

- *Latência*: uma chamada em hardware de desenvolvimento (CPU/GPU local, sem
  otimização de produção) leva dezenas de segundos por documento — bem mais
  lento que uma API de nuvem. O front-end trata isso com um estado de
  carregamento explícito, mas em produção real isso reforçaria ainda mais a
  necessidade de processamento assíncrono (ver seção "o que quebraria em
  produção").
- *Aderência a instruções mais frágil*: em testes reais contra os PDFs de
  desenvolvimento, o modelo por vezes produziu uma evidência que não é uma
  cópia literal do texto (ex.: parafraseando o bloco de assinatura, ou citando
  a data já no formato normalizado `YYYY-MM-DD` em vez do texto por extenso),
  mesmo quando o **valor** extraído estava correto. Isso não é uma falha do
  sistema — é exatamente o cenário que a validação programática de evidências
  existe para capturar: o campo é corretamente marcado como "não confirmado" em
  vez de aceito às cegas, mesmo quando por acaso o valor estava certo. Um
  modelo maior (Opus, ou o próprio `qwen2.5:14b-instruct` também disponível no
  ambiente) tende a citar evidências mais fielmente, mas o ponto central do
  desafio — nunca confiar apenas na palavra do modelo — vale exatamente igual
  para qualquer tamanho de modelo, e o pipeline se comporta corretamente com um
  modelo mais fraco.
- *Custo*: modelos locais não têm custo por token (ver `pricing.py` — modelos
  com prefixo local são tratados como custo zero, refletindo apenas a ausência
  de cobrança por chamada de API, não o custo real de hardware/energia, que
  este projeto não tenta estimar).
- *Timeout em documentos grandes*: durante testes reais (fora do script de
  avaliação), o processamento do despacho de 72 páginas falhou com "tempo
  limite excedido" nas duas tentativas, mesmo com um teto de 300s por
  tentativa. Reproduzindo o mesmo upload localmente, a extração desse mesmo
  documento levou 258s — perto o suficiente do teto anterior para estourar
  por qualquer variação de carga da máquina (ex.: o Ollama precisar recarregar
  o modelo na memória entre tentativas). Duas correções foram aplicadas: o
  teto de timeout subiu para 600s (`AI_REQUEST_TIMEOUT_SECONDS`), e a chamada
  ao Ollama passou a enviar `keep_alive="30m"` para manter o modelo carregado
  em memória entre tentativas de retry, evitando pagar o custo de carregar
  ~5GB de pesos mais de uma vez em sequência. A mensagem de erro final também
  foi melhorada para citar a causa real da última tentativa (timeout, erro de
  conexão, ou resposta fora do schema) em vez de uma frase genérica — isso foi
  o que permitiu diagnosticar o problema real em vez de adivinhar.
- Apesar desses trade-offs, o resultado real da última execução de
  `evaluation/evaluate.py` (ver `evaluation/results_latest.md`) foi **96% de
  acurácia média** nos 6 campos avaliados, sobre os 4 dos 5 documentos de
  desenvolvimento que possuíam texto extraível (o quinto, `ato_04.pdf`, é um
  PDF sem camada de texto — ver seção de OCR abaixo). O único campo com
  divergência (`orgao_emissor` em um documento) foi o modelo extrair a sigla
  do órgão ("CNDEAIC") em vez do nome por extenso usado no gabarito — uma
  divergência de forma, não de conteúdo.
- *Contexto*: `qwen3:8b` no Ollama expõe uma janela nativa de até ~40k tokens,
  mas o valor efetivo por requisição no Ollama costuma ser bem menor por
  padrão — por isso o provedor pede explicitamente `num_ctx` (configurável via
  `OLLAMA_NUM_CTX`, padrão 16384) em vez de confiar no padrão do servidor.

**O que quebra se o provedor mudar de versão**: no caso do Ollama, uma
atualização que altere o formato do parâmetro `format` (saída estruturada) ou
os nomes de campos de uso (`prompt_eval_count`/`eval_count`) quebraria a leitura
de tokens/observabilidade; no caso da Anthropic, uma mudança de major version do
SDK oficial poderia alterar a assinatura de `client.messages.parse` (já
aconteceu na transição para a 1.x). Em ambos os casos, o dano fica contido
dentro do respectivo arquivo de provedor — nada mais na aplicação depende de
detalhes de nenhum dos dois SDKs.

## Structured output: `client.messages.parse(output_format=AtoExtraido)`

Preferi o helper de conveniência do SDK (`.parse()`, que deriva o JSON Schema
diretamente do modelo Pydantic e valida a resposta antes de devolvê-la) a montar
manualmente um `output_config={"format": {"type": "json_schema", "schema": ...}}`
e fazer `json.loads` + `model_validate` à mão. É a opção que a própria
documentação do SDK recomenda para este caso, evita reimplementar a derivação
de JSON Schema a partir de Pydantic (incluindo detalhes como
`additionalProperties: false` e resolução de `$ref` em modelos aninhados), e
ainda assim a resposta passa por uma segunda validação Pydantic explícita no
meu código antes de seguir para evidências — a "saída estruturada + validação
por schema" pedida pelo desafio é satisfeita em duas camadas independentes
(API do provedor + minha própria validação), não uma só.

## Temperatura e controle de alucinação

No provedor Ollama (padrão deste projeto), `temperature=0` é enviado
explicitamente em toda chamada, para minimizar variância entre execuções do
mesmo documento. No provedor Anthropic, isso não é possível: os modelos atuais
da família Claude (incluindo `claude-sonnet-5`) usam *thinking* adaptativo por
padrão e não aceitam mais o parâmetro `temperature` quando o thinking está
ativo — a API retorna erro se ele for enviado. Essa é uma mudança real e
recente da API da Anthropic, não uma limitação deste projeto.

Em ambos os casos, o ponto central é o mesmo, e vale a pena registrar
explicitamente porque o desafio pede para não superestimar o que temperatura
baixa realmente faz: mesmo quando disponível e ajustada a zero, ela reduz a
variância da amostragem token a token — não impede o modelo de "inventar" com
convicção, nem substitui verificação. As defesas reais contra alucinação neste
projeto são estruturais e independem do provedor: instrução de abstenção
explícita no prompt, saída estruturada com enums fechados, e acima de tudo a
validação programática de evidências (abaixo) — que é o que efetivamente
capturou casos reais de "valor certo, evidência inventada" durante os testes
com o modelo local (ver seção anterior).

## Estratégia de evidências (a parte mais importante do desafio)

Para cada campo crítico, a IA deve devolver um trecho literal do documento que
sustente aquele valor. A aplicação verifica programaticamente
(`app/services/validation/evidence.py`) se esse trecho existe de fato no texto
extraído do PDF, usando:

1. Normalização controlada (colapsa espaços/quebras de linha, sem alterar
   conteúdo).
2. Comparação literal (substring) do trecho normalizado.
3. Uma única tolerância adicional: se a comparação exata falhar, tenta de novo
   ignorando maiúsculas/minúsculas (cobre cabeçalhos em caixa alta que o modelo
   às vezes normaliza). Não há fuzzy matching, distância de edição, nem
   embeddings — decisão deliberada para manter a verificação simples,
   determinística e fácil de defender ("por que essa evidência foi aceita?"
   tem sempre uma resposta mecânica).

**Quando a evidência não bate**: o campo é marcado como **suspeito**
(`campos_suspeitos`), mas o valor **não é apagado nem convertido para `null`**
automaticamente. Considerei as duas opções (nulificar vs. marcar como
suspeito) e escolhi marcar como suspeito porque:

- Nulificar automaticamente esconde do revisor humano uma informação que pode
  estar correta (a evidência pode ter falhado por um recorte infeliz do
  truncamento de documentos longos, não porque o valor é falso).
- O desafio pede explicitamente comportamento conservador que "não apresente
  como informação confirmada" — isso é alcançado marcando o campo, sem exigir
  apagar o dado.
- A interface nunca trata um campo suspeito como equivalente a um campo
  confiável: ele aparece com um selo visual de "não confirmado" em vez de ser
  exibido normalmente, e a decisão final (manter, corrigir ou remover) fica com
  a pessoa que revisa, que é quem tem contexto para julgar.

## Confiança (`meta.confianca_geral`)

O valor que a IA retorna é uma autoavaliação subjetiva do próprio modelo — não
uma probabilidade estatística calibrada, e o desafio pede explicitamente para
não fingir que é. Por isso o valor persistido e exibido **não é o número bruto
devolvido pela IA**: é recalculado de forma determinística em
`app/services/validation/confidence.py` como

```
confianca = 0.5 × (fração de campos críticos preenchidos)
          + 0.5 × (fração desses campos com evidência validada)
```

Simples e auditável, não uma fórmula "sofisticada para parecer avançada". O
valor original da IA é preservado em `resultado_ia_original` para quem quiser
comparar os dois.

## Estratégia para documentos longos

Um PDF de um único ato ainda pode ter dezenas de páginas (anexos, tabelas
extensas — ver `ato_03` do conjunto de avaliação, com 72 páginas de tabelas de
designação). Em vez de enviar tudo cegamente, o texto é truncado (cabeçalho +
trecho final, cortando sempre em uma quebra de linha) quando excede
`SEGMENTATION_MAX_CHARS` (24.000 caracteres por padrão).

**Por que essa estratégia e não outra**: atos administrativos brasileiros
seguem uma estrutura previsível — cabeçalho/ementa/"considerandos" no início,
corpo no meio, assinatura/data/local no fim — e a maioria dos campos do
contrato concentra-se nas pontas. É uma heurística sobre a **forma** do
documento (aplica-se a qualquer ato de qualquer órgão), não sobre o
**conteúdo** de nenhum dos cinco exemplos fornecidos. Alternativas consideradas
e descartadas por desproporcionais ao escopo do desafio:

- *Chunking + múltiplas chamadas ao modelo, com merge dos resultados*: mais
  robusto para documentos muito grandes, mas introduz problemas novos (como
  reconciliar dois valores diferentes de `orgao_emissor` vindos de chunks
  diferentes) que não valem a complexidade adicional para uma PoC.
- *Busca por palavra-chave dos tipos de ato para delimitar o início*: pareceu
  inicialmente mais "inteligente", mas na prática é uma heurística mais frágil
  (depende de regex sobre um vocabulário fechado) do que simplesmente confiar
  que o início e o fim do arquivo são as partes mais informativas.

**Limitação assumida**: se um campo crítico só existir no meio do documento
(uma tabela enorme de nomes, por exemplo), ele pode ser perdido. Isso é
registrado nos metadados de auditoria (`truncado: true`) e é um trade-off
explícito, não um bug escondido.

## Qualidade da extração de texto de PDF: dois bugs reais, encontrados e corrigidos em produção

Testes com PDFs reais fora do conjunto de avaliação (fornecidos pelo próprio
usuário durante o desenvolvimento) revelaram duas falhas genuínas na extração
de texto via `pypdf`, ambas em `services/pdf/extractor.py`. As duas são
características de **como certas ferramentas geram o PDF**, não de nenhum
documento específico — por isso as correções são normalizações genéricas
aplicadas a todo texto extraído, nunca uma regra amarrada a um arquivo.

**1. Ligadura "ti" mal codificada.** Um PDF exportado pelo sistema SEI trazia
43 ocorrências de um caractere Unicode (`Ɵ`) usado no lugar da ligadura
"ti" — "ConsƟtuição" em vez de "Constituição", "insƟtuiu" em vez de
"instituiu". Isso corrompia termos centrais do texto e quebrava a validação de
evidências (o modelo tende a "corrigir" a grafia ao citar, e a comparação
literal contra o texto — ainda corrompido — falhava por engano, mesmo quando o
valor extraído estava certo). Corrigido substituindo o caractere pela
sequência "ti" e aplicando normalização Unicode NFKC (que também resolve
ligaduras legítimas como "ﬁ"/"ﬂ" que alguns extratores preservam como um
único glifo).

**2. Texto quebrado caractere-a-caractere.** Em outro PDF, uma página inteira
(justamente a que continha os artigos finais e as assinaturas) foi extraída
com uma letra por linha — `"P\nr\ni\nm\ne\ni\nr\na"` em vez de `"Primeira"`.
Isso tem dois efeitos: infla artificialmente o tamanho do documento (nesse
caso, de ~19 mil para ~36 mil caracteres, o suficiente para disparar
truncamento desnecessário) e torna o trecho ilegível tanto para a busca de
evidências quanto para o próprio modelo — o que se manifestou como uma
extração quase inteiramente vazia (apenas `tipo_ato` preenchido, 186 tokens de
saída). A correção detecta sequências de pelo menos 6 linhas consecutivas de 1
caractere e as reconstrói concatenando-as de volta — um limiar escolhido para
não confundir uma lista numerada real (curta) com o padrão quebrado (longo).
Depois da correção, o mesmo documento caiu para ~19 mil caracteres (sem
truncar) e a extração passou a bater com a leitura manual do documento em
praticamente todos os campos (tipo, número, ano, órgão, data, os três
signatários, sete itens de fundamentação legal).

**Por que isso importa para a apresentação**: os dois casos são exemplos
concretos de "aplicação que quebra diante de um documento fora do padrão"
sendo encontrada e corrigida durante o desenvolvimento — exatamente o tipo de
situação que a seção 10 do desafio lista como algo que pesa contra. Ambos
foram descobertos processando documentos reais que o usuário forneceu
depois da entrega inicial, não nos cinco PDFs de desenvolvimento — o que
também reforça que a solução generaliza, e não foi ajustada nos exemplos
fornecidos.

**Limitação que continua de pé**: essas duas correções tratam padrões já
observados. Um PDF com uma terceira variante de corrupção de texto (outra
fonte, outra ferramenta de geração) ainda poderia escapar — não há como
antecipar todas as formas possíveis de um PDF gerar texto malformado sem
rodar OCR como camada de verificação cruzada, o que está fora do escopo desta
entrega (ver "Próximos passos").

## Recuperação de erros

Ambas as implementações de `AIProvider` (`anthropic_provider.py` e
`ollama_provider.py`) tentam no máximo `AI_MAX_ATTEMPTS` vezes (padrão 2). Na
tentativa seguinte a uma falha, uma instrução corretiva é anexada à mensagem,
adaptada ao tipo de falha (erro de schema/JSON inválido, timeout/conexão,
resposta incompleta, recusa do modelo). Esgotadas as tentativas, o erro é
encapsulado em `AIExtractionError` e a API responde com HTTP 502 e uma mensagem
amigável — nunca um stack trace. O limite explícito de tentativas evita loop
infinito.

## Estrutura do schema de evidências

O contrato de saída mostra `meta.evidencias` com apenas dois campos de
exemplo (`signatarios`, `data_assinatura`). Para que a saída estruturada
nativa funcione (ela exige um schema JSON fechado, não um dicionário livre de
chaves arbitrárias), defini `Evidencias` como um objeto com um campo opcional
por informação crítica listada na seção 8 do desafio: `numero`, `ano`,
`orgao_emissor`, `data_assinatura`, `data_publicacao`, `signatarios`,
`pessoas_citadas`, `fundamentacao_legal`, `atos_relacionados`, `vigencia`. Os
nomes dos campos do contrato original não foram alterados — apenas
formalizado, dentro de `meta.evidencias`, o conjunto de chaves que o exemplo já
sugeria implicitamente.

## Campos opcionais além do que o exemplo do contrato mostra

O exemplo da seção 4 do desafio não anota `numero`, `ano`, `orgao_emissor`,
`assunto` e `resumo` com `| null`, mas a regra fundamental do domínio (seção 1:
"campos não encontrados devem ser `null` ou `[]`... nunca preenchidos por
suposição") é uma regra global, não limitada aos campos que o exemplo marcou.
Um ato fora do padrão dos cinco exemplos fornecidos pode, por exemplo, não
declarar seu número explicitamente. Tornar esses campos opcionais no schema
Pydantic (`AtoExtraido`) é a forma de garantir, em nível de schema, que o
modelo nunca é forçado a inventar um valor só para satisfazer um campo
obrigatório — a alternativa (campo obrigatório) entraria em conflito direto com
a regra fundamental do domínio.

## Correção humana: granularidade por campo de topo

A correção substitui o valor inteiro de um campo de topo do contrato (ex.:
corrigir `signatarios` substitui a lista inteira, não um único item dela). Optei
por essa granularidade — em vez de permitir editar um único elemento dentro de
uma lista ou um subcampo de `vigencia` isoladamente — porque simplifica tanto o
back-end (uma única operação de validação/persistência por correção, sempre
revalidando o `AtoExtraido` inteiro) quanto o front-end (um único componente de
edição por campo, sem um editor de sub-formulário para cada tipo de lista
aninhada), sem perder a capacidade de corrigir qualquer informação do ato. Para
campos de lista de objetos (`signatarios`, `pessoas_citadas`,
`atos_relacionados`) e `vigencia`, a edição no front-end é feita em um campo de
texto JSON — uma simplificação deliberada da interface para não gastar tempo
desproporcional construindo formulários dedicados para cada estrutura aninhada,
mantendo o foco do tempo disponível na parte de IA/validação, que é onde o
desafio concentra o maior peso de avaliação.

## Front-end: componentes próprios em vez de instalar shadcn/ui

O desafio sugere shadcn/ui como preferência, mas não como obrigação
("bibliotecas de componentes prontos são bem-vindas"). Construí um conjunto
pequeno de componentes (`Button`, `Card`, `Badge`, `Input`, `Textarea`, `Select`,
`Modal`) diretamente com Tailwind CSS, no mesmo espírito visual e de API do
shadcn/ui (primitivas simples, sem CSS customizado espalhado pelos componentes
de página), sem instalar as dependências Radix/CVA associadas ao gerador
oficial. Isso evitou o tempo de setup do CLI do shadcn (que instala e
configura múltiplos pacotes por componente) sem abrir mão do resultado visual
pedido: interface simples, profissional e funcional, sem CSS escrito do zero
componente a componente.

## O que ficou fora do escopo (por instrução explícita do desafio)

Autenticação/autorização/multiusuário, deploy em nuvem, robô de coleta
automatizada do diário oficial, fine-tuning, cobertura ampla de testes,
identidade visual, animações, responsividade mobile, acessibilidade avançada e
tema escuro. Nenhum desses itens foi implementado, mesmo que parcialmente.

## O que quebraria em produção (fora do escopo desta entrega, mas vale discutir)

- **Processamento síncrono**: hoje uma requisição HTTP fica aberta durante toda
  a chamada ao modelo (alguns segundos). Sob volume real, isso precisa virar
  processamento assíncrono com fila (ex.: Celery/RQ + Redis, ou tasks do
  próprio FastAPI com um worker separado), com a API respondendo
  imediatamente com um ID e o front-end fazendo polling/websocket do status.
- **SQLite**: adequado para uso de uma pessoa por vez; sob concorrência real
  (múltiplos processos escrevendo), seria necessário migrar para Postgres —
  a camada de acesso já usa SQLAlchemy, então a migração é principalmente
  trocar a `DATABASE_URL` e revisar tipos específicos de SQLite (ex.: `JSON`
  como texto).
- **Observabilidade**: hoje os metadados de tokens/custo/latência ficam só no
  banco, por ato. Em produção isso deveria alimentar um sistema de métricas
  central (Prometheus/Grafana, ou equivalente) para detectar degradação de
  custo ou latência ao longo do tempo, não só por documento.
- **Limites do provedor**: rate limits e possíveis mudanças de modelo/preço da
  Anthropic não são tratados além do retry simples implementado — em produção
  valeria um circuit breaker e alertas de custo.
- **OCR**: PDFs escaneados como imagem não são suportados. Adicionar OCR (ex.:
  Tesseract, ou um modelo de visão) é o próximo passo natural para cobrir
  diários oficiais mais antigos ou mal digitalizados.
- **Versionamento de modelo e de prompt**: o prompt já é versionado em arquivo
  (`prompts/extraction_v1.txt`), mas não há ainda um mecanismo de reprocessar
  atos antigos com uma nova versão de prompt/modelo e comparar resultados —
  importante para avaliar regressões antes de promover uma mudança em
  produção.
- **Segurança de upload**: hoje valida-se tipo e tamanho do arquivo, mas não há
  sandboxing além do que o `pypdf` já oferece; um scanner de malware antes do
  processamento seria razoável em um ambiente institucional real.

## Próximos passos com mais tempo

1. OCR para PDFs escaneados.
2. Reprocessamento em lote com comparação entre versões de prompt/modelo
   (base para uma avaliação contínua, não só pontual via `evaluate.py`).
3. Editor estruturado (não JSON cru) para `signatarios`, `pessoas_citadas`,
   `atos_relacionados` e `vigencia` na correção humana.
4. Processamento assíncrono com fila, para não bloquear a requisição HTTP
   durante a chamada ao modelo.
5. Ampliar o dataset de avaliação além de 5 atos, incluindo exemplos de
   unidades e formatos diferentes dos fornecidos.
