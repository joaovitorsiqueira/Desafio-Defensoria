# Avaliação da extração

Conjunto pequeno (5 atos) usado para medir, de forma objetiva e repetível, a
qualidade da extração — não para provar que o sistema "funciona bem", mas para
ter um número concreto para discutir (seção 26 do desafio).

## Estrutura

- `dataset/pdfs/`: cópias dos 5 atos fornecidos junto com o desafio (`ato_01.pdf`
  a `ato_05.pdf`), usados como material de desenvolvimento — não como base para
  qualquer heurística específica de extração.
- `dataset/ground_truth.json`: gabarito preenchido manualmente, lendo cada PDF,
  para os campos considerados mais objetivamente verificáveis do contrato:
  `tipo_ato`, `numero`, `ano`, `orgao_emissor`, `data_assinatura`,
  `data_publicacao`.
- `evaluate.py`: roda o mesmo pipeline de extração da aplicação (texto → IA →
  validação) contra cada PDF e compara com o gabarito.
- `results_latest.md` / `results_latest.json`: resultado da última execução,
  registrado no repositório. Última execução: **96% de acurácia média** entre
  os 6 campos avaliados, em 4 dos 5 documentos (o quinto, `ato_04.pdf`, não
  possui camada de texto extraível — ver "Limitações" abaixo).

## Como rodar

```bash
cd backend && python -m venv .venv && .venv/Scripts/activate  # ou source .venv/bin/activate no Linux/Mac
pip install -r requirements.txt
cd ..
export ANTHROPIC_API_KEY=sua-chave   # ou defina no .env na raiz do projeto
python evaluation/evaluate.py
```

## Por que só 6 campos são avaliados automaticamente

`assunto`, `resumo`, `palavras_chave`, `signatarios`, `pessoas_citadas`,
`fundamentacao_legal`, `atos_relacionados` e `vigencia` são campos de texto
livre ou estruturas aninhadas cujo "gabarito correto" não é uma string única —
duas extrações razoavelmente diferentes na redação podem estar igualmente
corretas (ex.: um resumo pode ser parafraseado de várias formas válidas). Medir
esses campos exigiria um critério de similaridade semântica (ex.: um segundo
modelo como juiz), o que adicionaria complexidade e uma nova fonte de
incerteza à própria avaliação. Optou-se por manter a métrica simples e
compreensível, focada nos campos onde "certo" e "errado" são inequívocos, e
por avaliar os campos de texto livre qualitativamente durante a apresentação.

## Regras de comparação

- `tipo_ato`: igualdade exata (é um enum).
- `numero`: comparação após remover zeros à esquerda e caracteres não
  numéricos (tolera "001" vs "1").
- `ano`, `data_assinatura`, `data_publicacao`: igualdade exata (ou ambos
  nulos).
- `orgao_emissor`: comparação por substring normalizada (case-insensitive),
  em qualquer direção — nomes de órgãos costumam ser escritos por extenso ou
  abreviados de formas diferentes, tanto pelo modelo quanto por quem escreveu
  o gabarito.

## Limitações conhecidas desta avaliação

- Amostra pequena (5 documentos): a acurácia calculada tem alta variância e
  não deve ser lida como uma métrica estatisticamente robusta — serve para
  acompanhar tendência ao longo de mudanças no prompt/modelo, não como
  benchmark absoluto.
- O gabarito foi preenchido por leitura manual de cada PDF por quem
  desenvolveu o sistema, o que pode carregar o mesmo viés de interpretação do
  desenvolvedor (ex.: qual data conta como "assinatura" quando há uma data no
  corpo do texto e outra no carimbo de assinatura eletrônica — ver `ato_03`,
  onde essas duas datas divergem por um dia).
- `orgao_emissor` no `ato_04` foi deliberadamente marcado como `null` no
  gabarito: o documento é uma instrução conjunta entre três diretorias, sem
  uma única autoridade emissora declarada em um único trecho — um bom teste de
  se o modelo se abstém corretamente em vez de escolher arbitrariamente uma
  das três. Na prática, esse caso específico não chega a ser exercitado pela
  avaliação automática: `ato_04.pdf` é um PDF sem camada de texto extraível
  (confirmado com `pypdf` — a extração retorna 0 caracteres na única página),
  então o pipeline já para antes, no estágio de extração de texto, com o erro
  amigável correspondente. O teste de abstenção correta em `orgao_emissor`
  continua válido para quem quiser reprocessar esse documento manualmente
  (colando o texto) ou testar um ato semelhante com camada de texto.
- Não mede latência/custo como critério de qualidade, apenas registra os
  valores observados.
