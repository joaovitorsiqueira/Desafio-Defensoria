import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, enviarPdf, enviarTexto } from "../services/api";
import { Button, Card, CardContent, CardHeader, Spinner, Textarea } from "../components/ui";

const TAMANHO_MAXIMO_MB = 15;
const TAMANHO_MAXIMO_BYTES = TAMANHO_MAXIMO_MB * 1024 * 1024;

type Modo = "pdf" | "texto";

export function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [modo, setModo] = useState<Modo>("pdf");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [texto, setTexto] = useState("");
  const [arrastando, setArrastando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  function validarArquivo(f: File): string | null {
    const nomeMinusculo = f.name.toLowerCase();
    if (f.type !== "application/pdf" && !nomeMinusculo.endsWith(".pdf")) {
      return "Selecione um arquivo no formato PDF.";
    }
    if (f.size > TAMANHO_MAXIMO_BYTES) {
      return `O arquivo excede o tamanho máximo permitido (${TAMANHO_MAXIMO_MB} MB).`;
    }
    return null;
  }

  function selecionarArquivo(f: File) {
    const problema = validarArquivo(f);
    if (problema) {
      setErro(problema);
      setArquivo(null);
      return;
    }
    setErro(null);
    setArquivo(f);
  }

  function aoSoltarArquivo(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setArrastando(false);
    const f = e.dataTransfer.files?.[0];
    if (f) selecionarArquivo(f);
  }

  async function processar() {
    setErro(null);
    setEnviando(true);
    try {
      const ato =
        modo === "pdf"
          ? arquivo
            ? await enviarPdf(arquivo)
            : null
          : await enviarTexto(texto);

      if (!ato) {
        setErro("Selecione um arquivo PDF antes de continuar.");
        return;
      }
      navigate(`/atos/${ato.id}`);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível processar o ato. Tente novamente.");
    } finally {
      setEnviando(false);
    }
  }

  const podeEnviar = modo === "pdf" ? arquivo !== null : texto.trim().length >= 30;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold text-slate-900">Enviar ato para extração</h1>
      <p className="mb-6 text-sm text-slate-600">
        Envie o PDF do ato publicado ou cole o texto diretamente. A extração é feita por um modelo
        de linguagem e leva alguns segundos.
      </p>

      <Card>
        <CardHeader className="flex items-center gap-2">
          <button
            onClick={() => setModo("pdf")}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${modo === "pdf" ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}
          >
            Upload de PDF
          </button>
          <button
            onClick={() => setModo("texto")}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${modo === "texto" ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}
          >
            Colar texto
          </button>
        </CardHeader>
        <CardContent>
          {modo === "pdf" ? (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setArrastando(true);
              }}
              onDragLeave={() => setArrastando(false)}
              onDrop={aoSoltarArquivo}
              onClick={() => inputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-12 text-center transition-colors ${
                arrastando ? "border-brand-600 bg-brand-50" : "border-slate-300 hover:border-slate-400"
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) selecionarArquivo(f);
                }}
              />
              {arquivo ? (
                <>
                  <p className="text-sm font-medium text-slate-900">{arquivo.name}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {(arquivo.size / (1024 * 1024)).toFixed(2)} MB — clique para trocar o arquivo
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-slate-700">
                    Arraste um PDF aqui ou clique para selecionar
                  </p>
                  <p className="mt-1 text-xs text-slate-500">Tamanho máximo: {TAMANHO_MAXIMO_MB} MB</p>
                </>
              )}
            </div>
          ) : (
            <Textarea
              rows={12}
              placeholder="Cole aqui o texto integral do ato publicado..."
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
            />
          )}

          {erro && (
            <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {erro}
            </div>
          )}

          <div className="mt-5 flex items-center justify-end gap-3">
            {enviando && (
              <span className="flex items-center gap-2 text-sm text-slate-600">
                <Spinner /> Processando documento — isso pode levar alguns segundos...
              </span>
            )}
            <Button onClick={processar} disabled={!podeEnviar || enviando}>
              {enviando ? "Processando..." : "Extrair informações"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
