import { useEffect, useRef } from "react";
import type { EvidenceCheck } from "../types/ato";
import { Badge } from "./ui";
import { Modal } from "./Modal";

// Destaca a evidência dentro do texto original extraído (seção 17 do desafio —
// tratado como diferencial). O texto armazenado já passou pela mesma normalização
// de espaços usada na validação de evidências, então uma busca case-insensitive
// simples encontra o trecho correspondente na grande maioria dos casos.
function dividirComDestaque(texto: string, evidencia: string): { antes: string; trecho: string; depois: string } | null {
  if (!evidencia.trim()) return null;
  const indice = texto.toLowerCase().indexOf(evidencia.trim().toLowerCase());
  if (indice === -1) return null;
  return {
    antes: texto.slice(0, indice),
    trecho: texto.slice(indice, indice + evidencia.trim().length),
    depois: texto.slice(indice + evidencia.trim().length),
  };
}

export function EvidenceModal({
  aberto,
  onFechar,
  campoLabel,
  check,
  textoOriginal,
}: {
  aberto: boolean;
  onFechar: () => void;
  campoLabel: string;
  check: EvidenceCheck | undefined;
  textoOriginal: string;
}) {
  const marcaRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (aberto && marcaRef.current) {
      marcaRef.current.scrollIntoView({ block: "center" });
    }
  }, [aberto]);

  const partes = check ? dividirComDestaque(textoOriginal, check.evidencia) : null;

  return (
    <Modal aberto={aberto} onFechar={onFechar} titulo={`Evidência — ${campoLabel}`} largura="max-w-2xl">
      {!check ? (
        <p className="text-sm text-slate-500">A IA não forneceu evidência para este campo.</p>
      ) : (
        <div className="space-y-4">
          <div>
            {check.encontrada ? (
              <Badge tone="success">Evidência localizada no documento original</Badge>
            ) : (
              <Badge tone="danger">Evidência não localizada no documento — campo não confirmado</Badge>
            )}
          </div>
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
              Trecho citado pela IA
            </p>
            <blockquote className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm italic text-slate-700">
              “{check.evidencia}”
            </blockquote>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
              Localização no documento original
            </p>
            {partes ? (
              <pre className="whitespace-pre-wrap rounded-md border border-slate-200 bg-white px-3 py-2 text-xs leading-relaxed text-slate-700">
                {partes.antes}
                <mark ref={marcaRef} className="rounded bg-amber-200 px-0.5">
                  {partes.trecho}
                </mark>
                {partes.depois}
              </pre>
            ) : (
              <p className="text-sm text-slate-500">
                Não foi possível localizar visualmente o trecho no texto (ele pode estar fora do
                recorte enviado ao modelo, mesmo constando no documento completo).
              </p>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}
