import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { EditFieldDialog } from "../components/EditFieldDialog";
import { EvidenceModal } from "../components/EvidenceModal";
import { Modal } from "../components/Modal";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Spinner } from "../components/ui";
import {
  NOMES_CAMPOS,
  ROTULOS_PAPEL,
  ROTULOS_RELACAO,
  ROTULOS_TIPO_ATO,
  formatarData,
  formatarDataHora,
  formatarMoeda,
} from "../lib/format";
import { ApiError, obterAto, urlDocumentoOriginal } from "../services/api";
import type { AtoDetail as AtoDetailType } from "../types/ato";

function campoNaoConstaNoDocumento(ato: AtoDetailType, campo: string): boolean {
  return ato.resultado.meta.campos_nao_encontrados.some((c) => c === campo || c.startsWith(`${campo}.`));
}

function AusenciaBadge({ ato, campo }: { ato: AtoDetailType; campo: string }) {
  return campoNaoConstaNoDocumento(ato, campo) ? (
    <span className="text-sm italic text-slate-400">Não consta no documento</span>
  ) : (
    <span className="inline-flex items-center gap-1 text-sm italic text-amber-600">
      Não foi possível extrair
      <span title="A informação pode existir no documento, mas o modelo não conseguiu localizá-la com segurança.">
        ⓘ
      </span>
    </span>
  );
}

function FonteBadge({ ato, campo }: { ato: AtoDetailType; campo: string }) {
  if (ato.fontes_dos_campos[campo] === "humano") return <Badge tone="info">Corrigido por pessoa</Badge>;
  return null;
}

function SuspeitoBadge({ ato, campo }: { ato: AtoDetailType; campo: string }) {
  if (!ato.campos_suspeitos.includes(campo)) return null;
  return (
    <Badge tone="warning" title="A evidência fornecida pela IA não foi localizada no documento original.">
      Não confirmado
    </Badge>
  );
}

function BotaoEvidencia({
  ato,
  campo,
  onAbrir,
}: {
  ato: AtoDetailType;
  campo: string;
  onAbrir: () => void;
}) {
  const temEvidencia = ato.evidencias_validadas.some((e) => e.campo === campo);
  if (!temEvidencia) return null;
  return (
    <button onClick={onAbrir} className="text-xs font-medium text-brand-700 underline underline-offset-2 hover:text-brand-900">
      ver evidência
    </button>
  );
}

export function DetailPage() {
  const { id } = useParams<{ id: string }>();
  const [ato, setAto] = useState<AtoDetailType | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [campoEditando, setCampoEditando] = useState<string | null>(null);
  const [campoEvidencia, setCampoEvidencia] = useState<string | null>(null);
  const [textoOriginalAberto, setTextoOriginalAberto] = useState(false);

  useEffect(() => {
    if (!id) return;
    setCarregando(true);
    obterAto(id)
      .then(setAto)
      .catch((e) => setErro(e instanceof ApiError ? e.message : "Não foi possível carregar este ato."))
      .finally(() => setCarregando(false));
  }, [id]);

  if (carregando) {
    return (
      <div className="flex items-center gap-2 py-10 text-sm text-slate-600">
        <Spinner /> Carregando detalhe do ato...
      </div>
    );
  }
  if (erro || !ato) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {erro ?? "Ato não encontrado."}
      </div>
    );
  }

  // Alias local com tipo estreitado (não-nulo): funções aninhadas abaixo capturam
  // `ato` como closure sobre o estado do componente, e o TypeScript não propaga o
  // estreitamento feito pelo `if (!ato) return` acima para dentro dessas closures.
  const atoAtual: AtoDetailType = ato;
  const r = atoAtual.resultado;

  function CampoLinha({
    campo,
    valor,
  }: {
    campo: keyof typeof NOMES_CAMPOS;
    valor: string | null;
  }) {
    return (
      <div className="flex items-start justify-between gap-4 py-2.5">
        <div className="w-40 shrink-0 text-sm font-medium text-slate-500">{NOMES_CAMPOS[campo]}</div>
        <div className="flex-1">
          {valor ? (
            <span className="text-sm text-slate-900">{valor}</span>
          ) : (
            <AusenciaBadge ato={atoAtual} campo={campo} />
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <SuspeitoBadge ato={atoAtual} campo={campo} />
          <FonteBadge ato={atoAtual} campo={campo} />
          <BotaoEvidencia ato={atoAtual} campo={campo} onAbrir={() => setCampoEvidencia(campo)} />
          <button
            onClick={() => setCampoEditando(campo)}
            className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-800"
          >
            editar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <Badge tone="info">{ROTULOS_TIPO_ATO[r.tipo_ato]}</Badge>
            {ato.status === "erro" && <Badge tone="danger">Erro no processamento</Badge>}
          </div>
          <h1 className="text-xl font-semibold text-slate-900">
            {r.numero ? `Nº ${r.numero}` : "Sem número identificado"}
            {r.ano ? `/${r.ano}` : ""}
          </h1>
          <p className="text-sm text-slate-600">{r.orgao_emissor ?? "Órgão emissor não identificado"}</p>
        </div>
        {ato.tem_arquivo_original ? (
          <a href={urlDocumentoOriginal(ato.id)} target="_blank" rel="noreferrer">
            <Button variant="secondary">Ver documento original (PDF)</Button>
          </a>
        ) : (
          <Button variant="secondary" onClick={() => setTextoOriginalAberto(true)}>
            Ver texto original
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Identificação e datas</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-slate-100">
          <CampoLinha campo="tipo_ato" valor={ROTULOS_TIPO_ATO[r.tipo_ato]} />
          <CampoLinha campo="numero" valor={r.numero} />
          <CampoLinha campo="ano" valor={r.ano?.toString() ?? null} />
          <CampoLinha campo="orgao_emissor" valor={r.orgao_emissor} />
          <CampoLinha campo="data_assinatura" valor={formatarData(r.data_assinatura) || null} />
          <CampoLinha campo="data_publicacao" valor={formatarData(r.data_publicacao) || null} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Assunto e resumo</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-slate-100">
          <CampoLinha campo="assunto" valor={r.assunto} />
          <div className="flex items-start justify-between gap-4 py-2.5">
            <div className="w-40 shrink-0 text-sm font-medium text-slate-500">Resumo</div>
            <div className="flex-1 text-sm text-slate-900">
              {r.resumo ?? <AusenciaBadge ato={atoAtual} campo="resumo" />}
            </div>
            <button
              onClick={() => setCampoEditando("resumo")}
              className="shrink-0 text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-800"
            >
              editar
            </button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Signatários</CardTitle>
          <div className="flex items-center gap-2">
            <SuspeitoBadge ato={atoAtual} campo="signatarios" />
            <BotaoEvidencia ato={atoAtual} campo="signatarios" onAbrir={() => setCampoEvidencia("signatarios")} />
            <button
              onClick={() => setCampoEditando("signatarios")}
              className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-800"
            >
              editar
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {r.signatarios.length === 0 ? (
            <AusenciaBadge ato={atoAtual} campo="signatarios" />
          ) : (
            <ul className="space-y-1.5">
              {r.signatarios.map((s, i) => (
                <li key={i} className="text-sm text-slate-900">
                  <span className="font-medium">{s.nome}</span>
                  <span className="text-slate-500"> — {s.cargo}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Pessoas citadas</CardTitle>
          <div className="flex items-center gap-2">
            <SuspeitoBadge ato={atoAtual} campo="pessoas_citadas" />
            <BotaoEvidencia ato={atoAtual} campo="pessoas_citadas" onAbrir={() => setCampoEvidencia("pessoas_citadas")} />
            <button
              onClick={() => setCampoEditando("pessoas_citadas")}
              className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-800"
            >
              editar
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {r.pessoas_citadas.length === 0 ? (
            <AusenciaBadge ato={atoAtual} campo="pessoas_citadas" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="py-1.5 pr-3">Nome</th>
                    <th className="py-1.5 pr-3">Identificador</th>
                    <th className="py-1.5 pr-3">Cargo</th>
                    <th className="py-1.5 pr-3">Papel</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {r.pessoas_citadas.map((p, i) => (
                    <tr key={i}>
                      <td className="py-1.5 pr-3 font-medium text-slate-900">{p.nome}</td>
                      <td className="py-1.5 pr-3 text-slate-600">{p.identificador ?? "—"}</td>
                      <td className="py-1.5 pr-3 text-slate-600">{p.cargo ?? "—"}</td>
                      <td className="py-1.5 pr-3">
                        <Badge tone="neutral">{ROTULOS_PAPEL[p.papel]}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Fundamentação legal</CardTitle>
          <div className="flex items-center gap-2">
            <SuspeitoBadge ato={atoAtual} campo="fundamentacao_legal" />
            <BotaoEvidencia ato={atoAtual} campo="fundamentacao_legal" onAbrir={() => setCampoEvidencia("fundamentacao_legal")} />
            <button
              onClick={() => setCampoEditando("fundamentacao_legal")}
              className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-800"
            >
              editar
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {r.fundamentacao_legal.length === 0 ? (
            <AusenciaBadge ato={atoAtual} campo="fundamentacao_legal" />
          ) : (
            <ul className="list-inside list-disc space-y-1 text-sm text-slate-900">
              {r.fundamentacao_legal.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Atos relacionados</CardTitle>
          <div className="flex items-center gap-2">
            <SuspeitoBadge ato={atoAtual} campo="atos_relacionados" />
            <BotaoEvidencia ato={atoAtual} campo="atos_relacionados" onAbrir={() => setCampoEvidencia("atos_relacionados")} />
            <button
              onClick={() => setCampoEditando("atos_relacionados")}
              className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-800"
            >
              editar
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {r.atos_relacionados.length === 0 ? (
            <AusenciaBadge ato={atoAtual} campo="atos_relacionados" />
          ) : (
            <ul className="space-y-1.5 text-sm text-slate-900">
              {r.atos_relacionados.map((a, i) => (
                <li key={i}>
                  <Badge tone="neutral">{ROTULOS_RELACAO[a.relacao]}</Badge> <span className="ml-1">{a.referencia}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Vigência</CardTitle>
          <div className="flex items-center gap-2">
            <SuspeitoBadge ato={atoAtual} campo="vigencia" />
            <BotaoEvidencia ato={atoAtual} campo="vigencia" onAbrir={() => setCampoEvidencia("vigencia")} />
            <button
              onClick={() => setCampoEditando("vigencia")}
              className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-800"
            >
              editar
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {r.vigencia.inicio === null && r.vigencia.fim === null && r.vigencia.retroativa === null ? (
            <AusenciaBadge ato={atoAtual} campo="vigencia" />
          ) : (
            <dl className="grid grid-cols-3 gap-3 text-sm">
              <div>
                <dt className="text-xs font-medium text-slate-500">Início</dt>
                <dd className="text-slate-900">{formatarData(r.vigencia.inicio) || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-slate-500">Fim</dt>
                <dd className="text-slate-900">{formatarData(r.vigencia.fim) || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-slate-500">Retroativa</dt>
                <dd className="text-slate-900">
                  {r.vigencia.retroativa === null ? "—" : r.vigencia.retroativa ? "Sim" : "Não"}
                </dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Palavras-chave</CardTitle>
        </CardHeader>
        <CardContent>
          {r.palavras_chave.length === 0 ? (
            <AusenciaBadge ato={atoAtual} campo="palavras_chave" />
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {r.palavras_chave.map((p, i) => (
                <Badge key={i} tone="neutral">
                  {p}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Confiança e auditoria da extração</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs font-medium text-slate-500">Confiança geral</dt>
            <dd className="text-slate-900">{Math.round(r.meta.confianca_geral * 100)}%</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">Modelo</dt>
            <dd className="text-slate-900">{ato.auditoria.modelo_ia ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">Versão do prompt</dt>
            <dd className="text-slate-900">{ato.auditoria.prompt_versao ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">Tokens (entrada/saída)</dt>
            <dd className="text-slate-900">
              {ato.auditoria.tokens_entrada ?? "—"} / {ato.auditoria.tokens_saida ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">Latência</dt>
            <dd className="text-slate-900">
              {ato.auditoria.latencia_ms ? `${(ato.auditoria.latencia_ms / 1000).toFixed(1)}s` : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">Custo estimado</dt>
            <dd className="text-slate-900">{formatarMoeda(ato.auditoria.custo_estimado_usd)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">Tentativas até sucesso</dt>
            <dd className="text-slate-900">{ato.auditoria.tentativas_ia ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">Documento truncado?</dt>
            <dd className="text-slate-900">{ato.auditoria.truncado ? "Sim (documento longo)" : "Não"}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">Processado em</dt>
            <dd className="text-slate-900">{formatarDataHora(ato.criado_em)}</dd>
          </div>
        </CardContent>
      </Card>

      <EditFieldDialog
        aberto={campoEditando !== null}
        onFechar={() => setCampoEditando(null)}
        atoId={atoAtual.id}
        campo={campoEditando ?? ""}
        valorAtual={campoEditando ? (r as unknown as Record<string, unknown>)[campoEditando] : null}
        onSalvo={setAto}
      />
      <EvidenceModal
        aberto={campoEvidencia !== null}
        onFechar={() => setCampoEvidencia(null)}
        campoLabel={campoEvidencia ? (NOMES_CAMPOS[campoEvidencia] ?? campoEvidencia) : ""}
        check={ato.evidencias_validadas.find((e) => e.campo === campoEvidencia)}
        textoOriginal={ato.texto_extraido}
      />
      <Modal
        aberto={textoOriginalAberto}
        onFechar={() => setTextoOriginalAberto(false)}
        titulo="Texto original enviado"
        largura="max-w-2xl"
      >
        <p className="mb-3 text-xs text-slate-500">
          Este ato foi enviado como texto colado (sem arquivo PDF associado) — o trecho abaixo é
          exatamente o texto que foi processado.
        </p>
        <pre className="whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700">
          {atoAtual.texto_extraido}
        </pre>
      </Modal>
    </div>
  );
}
