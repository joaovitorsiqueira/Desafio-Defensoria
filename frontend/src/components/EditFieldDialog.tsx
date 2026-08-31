import { useState } from "react";
import { ApiError, corrigirCampo } from "../services/api";
import type { AtoDetail, AtoRelacionado, PapelPessoa, PessoaCitada, RelacaoAto, Signatario, Vigencia } from "../types/ato";
import { NOMES_CAMPOS, ROTULOS_PAPEL, ROTULOS_RELACAO, ROTULOS_TIPO_ATO } from "../lib/format";
import { Button, Input, Select, Textarea } from "./ui";
import { Modal } from "./Modal";

const CAMPOS_LISTA_TEXTO = new Set(["fundamentacao_legal", "palavras_chave"]);
const CAMPOS_DATA = new Set(["data_assinatura", "data_publicacao"]);

// Campos de estrutura composta (lista de objetos ou objeto com vários
// subcampos) ganham um editor visual dedicado em vez de JSON cru — a pessoa
// que usa esta tela não é da área técnica e não deveria precisar escrever
// JSON à mão para corrigir um nome ou uma data (ver DECISOES.md).
type CampoEstruturado = "signatarios" | "pessoas_citadas" | "atos_relacionados" | "vigencia";

function ehCampoEstruturado(campo: string): campo is CampoEstruturado {
  return campo === "signatarios" || campo === "pessoas_citadas" || campo === "atos_relacionados" || campo === "vigencia";
}

function valorParaEdicaoSimples(campo: string, valor: unknown): string {
  if (CAMPOS_LISTA_TEXTO.has(campo)) return ((valor as string[]) ?? []).join("\n");
  if (valor === null || valor === undefined) return "";
  return String(valor);
}

function edicaoParaValorSimples(campo: string, texto: string): unknown {
  if (CAMPOS_LISTA_TEXTO.has(campo)) {
    return texto
      .split("\n")
      .map((linha) => linha.trim())
      .filter(Boolean);
  }
  if (campo === "ano") return texto.trim() === "" ? null : Number(texto.trim());
  return texto.trim() === "" ? null : texto;
}

// ---------- editor genérico de listas de objetos (signatários, pessoas citadas, atos relacionados) ----------

interface CampoConfig {
  chave: string;
  rotulo: string;
  tipo: "texto" | "select";
  opcoes?: { value: string; label: string }[];
}

function EditorListaObjetos<T>({
  itens,
  onChange,
  campos,
  criarVazio,
  rotuloItem,
}: {
  itens: T[];
  onChange: (itens: T[]) => void;
  campos: CampoConfig[];
  criarVazio: () => T;
  rotuloItem: string;
}) {
  function atualizarCampo(indice: number, chave: string, valor: string) {
    const novos = itens.slice();
    novos[indice] = { ...(novos[indice] as object), [chave]: valor } as T;
    onChange(novos);
  }

  function remover(indice: number) {
    onChange(itens.filter((_, i) => i !== indice));
  }

  return (
    <div className="space-y-3">
      {itens.length === 0 && (
        <p className="text-sm text-slate-500">Nenhum {rotuloItem} adicionado.</p>
      )}
      {itens.map((item, indice) => (
        <div key={indice} className="rounded-md border border-slate-200 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
              {rotuloItem} {indice + 1}
            </span>
            <button
              type="button"
              onClick={() => remover(indice)}
              className="text-xs font-medium text-red-600 underline underline-offset-2 hover:text-red-800"
            >
              remover
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {campos.map((c) => (
              <div key={c.chave} className={c.tipo === "select" ? "" : "col-span-2"}>
                <label className="mb-1 block text-xs text-slate-500">{c.rotulo}</label>
                {c.tipo === "select" ? (
                  <Select
                    value={String((item as Record<string, unknown>)[c.chave] ?? "")}
                    onChange={(e) => atualizarCampo(indice, c.chave, e.target.value)}
                  >
                    {c.opcoes!.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Input
                    value={String((item as Record<string, unknown>)[c.chave] ?? "")}
                    onChange={(e) => atualizarCampo(indice, c.chave, e.target.value)}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
      <Button type="button" variant="secondary" onClick={() => onChange([...itens, criarVazio()])}>
        + adicionar {rotuloItem}
      </Button>
    </div>
  );
}

const OPCOES_PAPEL = Object.entries(ROTULOS_PAPEL).map(([value, label]) => ({ value, label }));
const OPCOES_RELACAO = Object.entries(ROTULOS_RELACAO).map(([value, label]) => ({ value, label }));

// ---------- editor de vigência ----------

function EditorVigencia({ valor, onChange }: { valor: Vigencia; onChange: (v: Vigencia) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="mb-1 block text-xs text-slate-500">Início</label>
        <input
          type="date"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
          value={valor.inicio ?? ""}
          onChange={(e) => onChange({ ...valor, inicio: e.target.value || null })}
        />
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-500">Fim</label>
        <input
          type="date"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
          value={valor.fim ?? ""}
          onChange={(e) => onChange({ ...valor, fim: e.target.value || null })}
        />
      </div>
      <div className="col-span-2">
        <label className="mb-1 block text-xs text-slate-500">Retroativa?</label>
        <Select
          value={valor.retroativa === null ? "" : String(valor.retroativa)}
          onChange={(e) =>
            onChange({ ...valor, retroativa: e.target.value === "" ? null : e.target.value === "true" })
          }
        >
          <option value="">Não informado no documento</option>
          <option value="true">Sim</option>
          <option value="false">Não</option>
        </Select>
      </div>
    </div>
  );
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
  const [texto, setTexto] = useState("");
  const [estruturado, setEstruturado] = useState<unknown>(null);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [campoCarregado, setCampoCarregado] = useState<string | null>(null);

  // O diálogo permanece montado entre aberturas (só alterna `aberto`), então o
  // estado precisa ser recarregado toda vez que ele abre para um campo. Isso
  // era feito num useEffect, mas um efeito só roda DEPOIS da renderização: ao
  // trocar de "vigência" (objeto) para "atos relacionados" (lista) sem
  // fechar e reabrir o componente, a primeira renderização acontecia com o
  // campo novo mas o estado `estruturado` ainda do formato antigo — e
  // `itens.map(...)` num objeto que não é array quebrava a página inteira.
  // Ajustar o estado aqui, durante a própria renderização, evita que essa
  // renderização com formato incompatível chegue a acontecer.
  const chaveDesejada = aberto ? campo : null;
  if (campoCarregado !== chaveDesejada) {
    setCampoCarregado(chaveDesejada);
    if (chaveDesejada !== null) {
      setErro(null);
      if (ehCampoEstruturado(campo)) {
        setEstruturado(valorAtual);
      } else {
        setTexto(valorParaEdicaoSimples(campo, valorAtual));
      }
    }
  }

  if (!aberto) return null;

  const ehData = CAMPOS_DATA.has(campo);
  const ehLista = CAMPOS_LISTA_TEXTO.has(campo);
  const ehTipoAto = campo === "tipo_ato";
  const ehEstruturado = ehCampoEstruturado(campo);

  async function salvar() {
    setErro(null);
    const valor: unknown = ehEstruturado ? estruturado : edicaoParaValorSimples(campo, texto);
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
    <Modal aberto={aberto} onFechar={onFechar} titulo={`Corrigir: ${NOMES_CAMPOS[campo] ?? campo}`} largura="max-w-xl">
      <div className="space-y-3">
        <p className="text-xs text-slate-500">
          Este valor foi gerado pela IA. Ao salvar, o novo valor passa a ser exibido como corrigido por
          uma pessoa, e essa correção fica registrada no histórico do ato.
        </p>

        {campo === "signatarios" && (
          <EditorListaObjetos<Signatario>
            itens={(estruturado as Signatario[]) ?? []}
            onChange={setEstruturado}
            rotuloItem="signatário"
            criarVazio={() => ({ nome: "", cargo: "" })}
            campos={[
              { chave: "nome", rotulo: "Nome", tipo: "texto" },
              { chave: "cargo", rotulo: "Cargo", tipo: "texto" },
            ]}
          />
        )}

        {campo === "pessoas_citadas" && (
          <EditorListaObjetos<PessoaCitada>
            itens={(estruturado as PessoaCitada[]) ?? []}
            onChange={setEstruturado}
            rotuloItem="pessoa"
            criarVazio={() => ({ nome: "", identificador: null, cargo: null, papel: "OUTRO" as PapelPessoa })}
            campos={[
              { chave: "nome", rotulo: "Nome", tipo: "texto" },
              { chave: "identificador", rotulo: "Identificador (matrícula, se houver)", tipo: "texto" },
              { chave: "cargo", rotulo: "Cargo (se houver)", tipo: "texto" },
              { chave: "papel", rotulo: "Papel", tipo: "select", opcoes: OPCOES_PAPEL },
            ]}
          />
        )}

        {campo === "atos_relacionados" && (
          <EditorListaObjetos<AtoRelacionado>
            itens={(estruturado as AtoRelacionado[]) ?? []}
            onChange={setEstruturado}
            rotuloItem="ato relacionado"
            criarVazio={() => ({ referencia: "", relacao: "ALTERA" as RelacaoAto })}
            campos={[
              { chave: "referencia", rotulo: "Referência (ex.: Portaria 45/2025)", tipo: "texto" },
              { chave: "relacao", rotulo: "Relação", tipo: "select", opcoes: OPCOES_RELACAO },
            ]}
          />
        )}

        {campo === "vigencia" && (
          <EditorVigencia
            valor={(estruturado as Vigencia) ?? { inicio: null, fim: null, retroativa: null }}
            onChange={setEstruturado}
          />
        )}

        {!ehEstruturado &&
          (ehTipoAto ? (
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
              rows={ehLista ? 5 : 3}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder={ehLista ? "Um item por linha" : undefined}
            />
          ))}

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
