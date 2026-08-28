import { useState } from "react";
import { ApiError, corrigirCampo } from "../services/api";
import type { AtoDetail } from "../types/ato";
import { NOMES_CAMPOS, ROTULOS_TIPO_ATO } from "../lib/format";
import { Button, Select, Textarea } from "./ui";
import { Modal } from "./Modal";

const CAMPOS_LISTA_TEXTO = new Set(["fundamentacao_legal", "palavras_chave"]);
const CAMPOS_JSON = new Set(["signatarios", "pessoas_citadas", "atos_relacionados", "vigencia"]);
const CAMPOS_DATA = new Set(["data_assinatura", "data_publicacao"]);

function valorParaEdicao(campo: string, valor: unknown): string {
  if (CAMPOS_LISTA_TEXTO.has(campo)) return ((valor as string[]) ?? []).join("\n");
  if (CAMPOS_JSON.has(campo)) return JSON.stringify(valor, null, 2);
  if (valor === null || valor === undefined) return "";
  return String(valor);
}

function edicaoParaValor(campo: string, texto: string): unknown {
  if (CAMPOS_LISTA_TEXTO.has(campo)) {
    return texto
      .split("\n")
      .map((linha) => linha.trim())
      .filter(Boolean);
  }
  if (CAMPOS_JSON.has(campo)) {
    return JSON.parse(texto);
  }
  if (campo === "ano") return texto.trim() === "" ? null : Number(texto.trim());
  return texto.trim() === "" ? null : texto;
}

export function EditFieldDialog({
  aberto,
  onFechar,
  atoId,
  campo,
  valorAtual,
  onSalvo,
}: {
  aberto: boolean;
  onFechar: () => void;
  atoId: string;
  campo: string;
  valorAtual: unknown;
  onSalvo: (ato: AtoDetail) => void;
}) {
  const [texto, setTexto] = useState(() => valorParaEdicao(campo, valorAtual));
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (!aberto) return null;

  const ehJson = CAMPOS_JSON.has(campo);
  const ehLista = CAMPOS_LISTA_TEXTO.has(campo);
  const ehData = CAMPOS_DATA.has(campo);
  const ehTipoAto = campo === "tipo_ato";

  async function salvar() {
    setErro(null);
    let valor: unknown;
    try {
      valor = edicaoParaValor(campo, texto);
    } catch {
      setErro("O valor informado não é um JSON válido. Verifique a formatação.");
      return;
    }
    setSalvando(true);
    try {
      const atualizado = await corrigirCampo(atoId, campo, valor);
      onSalvo(atualizado);
      onFechar();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível salvar a correção.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal aberto={aberto} onFechar={onFechar} titulo={`Corrigir: ${NOMES_CAMPOS[campo] ?? campo}`}>
      <div className="space-y-3">
        <p className="text-xs text-slate-500">
          Este valor foi gerado pela IA. Ao salvar, o novo valor passa a ser exibido como corrigido por
          uma pessoa, e essa correção fica registrada no histórico do ato.
        </p>

        {ehTipoAto ? (
          <Select value={texto} onChange={(e) => setTexto(e.target.value)}>
            {Object.entries(ROTULOS_TIPO_ATO).map(([valor, rotulo]) => (
              <option key={valor} value={valor}>
                {rotulo}
              </option>
            ))}
          </Select>
        ) : ehData ? (
          <input
            type="date"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
          />
        ) : (
          <Textarea
            rows={ehJson ? 10 : ehLista ? 5 : 3}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder={
              ehLista
                ? "Um item por linha"
                : ehJson
                  ? "Edite a estrutura em JSON"
                  : undefined
            }
            className={ehJson ? "font-mono text-xs" : undefined}
          />
        )}

        {erro && <p className="text-sm text-red-600">{erro}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onFechar} disabled={salvando}>
            Cancelar
          </Button>
          <Button onClick={salvar} disabled={salvando}>
            {salvando ? "Salvando..." : "Salvar correção"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
