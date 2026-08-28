import type { PapelPessoa, RelacaoAto, TipoAto } from "../types/ato";

export const ROTULOS_TIPO_ATO: Record<TipoAto, string> = {
  PORTARIA: "Portaria",
  RESOLUCAO: "Resolução",
  DESPACHO: "Despacho",
  EDITAL: "Edital",
  INSTRUCAO_NORMATIVA: "Instrução Normativa",
  OUTRO: "Outro",
};

export const ROTULOS_PAPEL: Record<PapelPessoa, string> = {
  NOMEADO: "Nomeado(a)",
  EXONERADO: "Exonerado(a)",
  DESIGNADO: "Designado(a)",
  DISPENSADO: "Dispensado(a)",
  CEDIDO: "Cedido(a)",
  BENEFICIARIO: "Beneficiário(a)",
  OUTRO: "Outro",
};

export const ROTULOS_RELACAO: Record<RelacaoAto, string> = {
  REVOGA: "Revoga",
  ALTERA: "Altera",
  RETIFICA: "Retifica",
  COMPLEMENTA: "Complementa",
};

export const NOMES_CAMPOS: Record<string, string> = {
  tipo_ato: "Tipo do ato",
  numero: "Número",
  ano: "Ano",
  orgao_emissor: "Órgão emissor",
  data_assinatura: "Data de assinatura",
  data_publicacao: "Data de publicação",
  assunto: "Assunto",
  resumo: "Resumo",
  signatarios: "Signatários",
  pessoas_citadas: "Pessoas citadas",
  fundamentacao_legal: "Fundamentação legal",
  atos_relacionados: "Atos relacionados",
  vigencia: "Vigência",
  palavras_chave: "Palavras-chave",
};

export function formatarData(iso: string | null): string {
  if (!iso) return "";
  const [ano, mes, dia] = iso.split("-");
  if (!ano || !mes || !dia) return iso;
  return `${dia}/${mes}/${ano}`;
}

export function formatarDataHora(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR");
}

export function formatarMoeda(valor: number | null): string {
  if (valor === null) return "não disponível";
  if (valor === 0) return "US$ 0,00 (modelo local, sem custo por token)";
  if (valor < 0.01) return `US$ ${valor.toFixed(6)}`;
  return `US$ ${valor.toFixed(4)}`;
}
