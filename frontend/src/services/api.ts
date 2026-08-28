// Toda comunicação com o backend passa por este módulo. Nenhum componente da UI
// faz fetch/axios diretamente nem conhece a forma da API — eles só chamam estas
// funções e recebem tipos já prontos (ver types/ato.ts). Isso mantém a regra de
// negócio (e qualquer detalhe de chamada ao backend/IA) fora dos componentes React.

import type { AtoDetail, AtoListResponse } from "../types/ato";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function tratarResposta<T>(resposta: Response): Promise<T> {
  if (!resposta.ok) {
    let mensagem = "Ocorreu um erro ao comunicar com o servidor.";
    try {
      const corpo = await resposta.json();
      if (typeof corpo?.detail === "string") {
        mensagem = corpo.detail;
      }
    } catch {
      // resposta sem corpo JSON (ex.: erro de rede) — mantém mensagem genérica
    }
    throw new ApiError(mensagem, resposta.status);
  }
  return resposta.json() as Promise<T>;
}

export interface FiltrosListagem {
  tipo_ato?: string;
  orgao_emissor?: string;
  data_inicio?: string;
  data_fim?: string;
  busca?: string;
  limit?: number;
  offset?: number;
}

export async function listarAtos(filtros: FiltrosListagem): Promise<AtoListResponse> {
  const params = new URLSearchParams();
  Object.entries(filtros).forEach(([chave, valor]) => {
    if (valor !== undefined && valor !== "") params.set(chave, String(valor));
  });
  const resposta = await fetch(`${API_BASE_URL}/api/atos?${params.toString()}`);
  return tratarResposta<AtoListResponse>(resposta);
}

export async function obterAto(id: string): Promise<AtoDetail> {
  const resposta = await fetch(`${API_BASE_URL}/api/atos/${id}`);
  return tratarResposta<AtoDetail>(resposta);
}

export async function enviarPdf(arquivo: File): Promise<AtoDetail> {
  const formData = new FormData();
  formData.append("arquivo", arquivo);
  const resposta = await fetch(`${API_BASE_URL}/api/atos/upload`, {
    method: "POST",
    body: formData,
  });
  return tratarResposta<AtoDetail>(resposta);
}

export async function enviarTexto(texto: string): Promise<AtoDetail> {
  const resposta = await fetch(`${API_BASE_URL}/api/atos/texto`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });
  return tratarResposta<AtoDetail>(resposta);
}

export async function corrigirCampo(id: string, campo: string, valor: unknown): Promise<AtoDetail> {
  const resposta = await fetch(`${API_BASE_URL}/api/atos/${id}/campos`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ campo, valor }),
  });
  return tratarResposta<AtoDetail>(resposta);
}

export function urlDocumentoOriginal(id: string): string {
  return `${API_BASE_URL}/api/atos/${id}/documento`;
}
