// Estes tipos espelham exatamente app/schemas/extraction_contract.py e
// app/schemas/api.py no backend. Mantidos aqui, e não recriados dentro dos
// componentes, para que toda a UI compartilhe a mesma definição do contrato.

export type TipoAto =
  | "PORTARIA"
  | "RESOLUCAO"
  | "DESPACHO"
  | "EDITAL"
  | "INSTRUCAO_NORMATIVA"
  | "OUTRO";

export type PapelPessoa =
  | "NOMEADO"
  | "EXONERADO"
  | "DESIGNADO"
  | "DISPENSADO"
  | "CEDIDO"
  | "BENEFICIARIO"
  | "OUTRO";

export type RelacaoAto = "REVOGA" | "ALTERA" | "RETIFICA" | "COMPLEMENTA";

export interface Signatario {
  nome: string;
  cargo: string;
}

export interface PessoaCitada {
  nome: string;
  identificador: string | null;
  cargo: string | null;
  papel: PapelPessoa;
}

export interface AtoRelacionado {
  referencia: string;
  relacao: RelacaoAto;
}

export interface Vigencia {
  inicio: string | null;
  fim: string | null;
  retroativa: boolean | null;
}

export interface Evidencias {
  numero: string | null;
  ano: string | null;
  orgao_emissor: string | null;
  data_assinatura: string | null;
  data_publicacao: string | null;
  signatarios: string | null;
  pessoas_citadas: string | null;
  fundamentacao_legal: string | null;
  atos_relacionados: string | null;
  vigencia: string | null;
}

export interface Meta {
  campos_nao_encontrados: string[];
  confianca_geral: number;
  evidencias: Evidencias;
}

export interface AtoExtraido {
  tipo_ato: TipoAto;
  numero: string | null;
  ano: number | null;
  orgao_emissor: string | null;
  data_assinatura: string | null;
  data_publicacao: string | null;
  assunto: string | null;
  resumo: string | null;
  signatarios: Signatario[];
  pessoas_citadas: PessoaCitada[];
  fundamentacao_legal: string[];
  atos_relacionados: AtoRelacionado[];
  vigencia: Vigencia;
  palavras_chave: string[];
  meta: Meta;
}

export interface EvidenceCheck {
  campo: string;
  evidencia: string;
  encontrada: boolean;
  match_type: "exata" | "case_insensitive" | "nao_encontrada" | "sem_evidencia";
}

export interface Auditoria {
  prompt_versao: string | null;
  modelo_ia: string | null;
  tokens_entrada: number | null;
  tokens_saida: number | null;
  latencia_ms: number | null;
  custo_estimado_usd: number | null;
  tentativas_ia: number | null;
  truncado: boolean;
}

export interface AtoListItem {
  id: string;
  criado_em: string;
  status: string;
  tipo_ato: TipoAto | null;
  numero: string | null;
  ano: number | null;
  orgao_emissor: string | null;
  data_assinatura: string | null;
  data_publicacao: string | null;
  assunto: string | null;
  confianca_geral: number | null;
  campos_suspeitos: string[];
  tem_correcao_humana: boolean;
}

export interface AtoListResponse {
  items: AtoListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AtoDetail {
  id: string;
  criado_em: string;
  atualizado_em: string;
  status: string;
  mensagem_erro: string | null;

  origem: "pdf" | "texto";
  nome_arquivo_original: string | null;
  tem_arquivo_original: boolean;
  texto_extraido: string;

  resultado: AtoExtraido;
  resultado_ia_original: AtoExtraido;
  campos_suspeitos: string[];
  evidencias_validadas: EvidenceCheck[];
  fontes_dos_campos: Record<string, "ia" | "humano">;

  auditoria: Auditoria;
}

// Campos de topo do contrato que podem ser corrigidos via PATCH /api/atos/{id}/campos
export const CAMPOS_CORRIGIVEIS = [
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
] as const;

export type CampoCorrigivel = (typeof CAMPOS_CORRIGIVEIS)[number];
