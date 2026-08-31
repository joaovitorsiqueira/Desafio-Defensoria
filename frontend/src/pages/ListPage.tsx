import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listarAtos } from "../services/api";
import type { AtoListItem } from "../types/ato";
import { formatarData, ROTULOS_TIPO_ATO } from "../lib/format";
import { Badge, Button, Card, CardContent, Input, Select, Spinner } from "../components/ui";

const PAGINA_TAMANHO = 20;

function BadgeConfianca({ valor }: { valor: number | null }) {
  if (valor === null) return <Badge tone="neutral">—</Badge>;
  if (valor >= 0.75) return <Badge tone="success">{Math.round(valor * 100)}%</Badge>;
  if (valor >= 0.4) return <Badge tone="warning">{Math.round(valor * 100)}%</Badge>;
  return <Badge tone="danger">{Math.round(valor * 100)}%</Badge>;
}

export function ListPage() {
  const [itens, setItens] = useState<AtoListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [tipoAto, setTipoAto] = useState("");
  const [orgaoEmissor, setOrgaoEmissor] = useState("");
  const [busca, setBusca] = useState("");

  useEffect(() => {
    let cancelado = false;
    setCarregando(true);
    setErro(null);
    listarAtos({ tipo_ato: tipoAto || undefined, orgao_emissor: orgaoEmissor || undefined, busca: busca || undefined, limit: PAGINA_TAMANHO, offset })
      .then((resposta) => {
        if (cancelado) return;
        setItens(resposta.items);
        setTotal(resposta.total);
      })
      .catch((e) => {
        if (cancelado) return;
        setErro(e instanceof ApiError ? e.message : "Não foi possível carregar a lista de atos.");
      })
      .finally(() => {
        if (!cancelado) setCarregando(false);
      });
    return () => {
      cancelado = true;
    };
  }, [tipoAto, orgaoEmissor, busca, offset]);

  const nenhumFiltroAtivo = !tipoAto && !orgaoEmissor && !busca;

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-slate-900">Atos processados</h1>
      <p className="mb-6 text-sm text-slate-600">Consulte, filtre e audite os atos já extraídos.</p>

      <Card className="mb-4">
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Tipo do ato</label>
            <Select
              value={tipoAto}
              onChange={(e) => {
                setOffset(0);
                setTipoAto(e.target.value);
              }}
            >
              <option value="">Todos</option>
              {Object.entries(ROTULOS_TIPO_ATO).map(([valor, rotulo]) => (
                <option key={valor} value={valor}>
                  {rotulo}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Órgão emissor</label>
            <Input
              placeholder="Filtrar por órgão..."
              value={orgaoEmissor}
              onChange={(e) => {
                setOffset(0);
                setOrgaoEmissor(e.target.value);
              }}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Busca textual</label>
            <Input
              placeholder="Assunto, número, arquivo..."
              value={busca}
              onChange={(e) => {
                setOffset(0);
                setBusca(e.target.value);
              }}
            />
          </div>
        </CardContent>
      </Card>

      {erro && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {carregando ? (
        <div className="flex items-center gap-2 py-10 text-sm text-slate-600">
          <Spinner /> Carregando atos...
        </div>
      ) : itens.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-slate-500">
            {nenhumFiltroAtivo
              ? "Nenhum ato processado ainda. Envie um PDF ou cole um texto na tela de envio para começar."
              : "Nenhum ato encontrado com os filtros atuais."}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-3">Tipo</th>
                  <th className="px-3 py-3">Número/Ano</th>
                  <th className="px-3 py-3">Órgão emissor</th>
                  <th className="px-3 py-3">Assunto</th>
                  <th className="px-3 py-3">Assinatura</th>
                  <th className="px-3 py-3">Confiança</th>
                  <th className="whitespace-nowrap px-3 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {itens.map((ato) => (
                  <tr key={ato.id} className="hover:bg-slate-50">
                    <td className="px-3 py-3">
                      {ato.tipo_ato ? (
                        <Badge tone="info">{ROTULOS_TIPO_ATO[ato.tipo_ato]}</Badge>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-slate-700">
                      {ato.numero ?? "—"}
                      {ato.ano ? `/${ato.ano}` : ""}
                    </td>
                    <td className="max-w-[160px] truncate px-3 py-3 text-slate-700">
                      {ato.orgao_emissor ?? "—"}
                    </td>
                    <td className="max-w-[200px] truncate px-3 py-3 text-slate-700">{ato.assunto ?? "—"}</td>
                    <td className="px-3 py-3 text-slate-700">{formatarData(ato.data_assinatura) || "—"}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-1.5">
                        <BadgeConfianca valor={ato.confianca_geral} />
                        {ato.campos_suspeitos.length > 0 && (
                          <Badge tone="warning" title={`${ato.campos_suspeitos.length} campo(s) suspeito(s)`}>
                            ⚠ {ato.campos_suspeitos.length}
                          </Badge>
                        )}
                        {ato.tem_correcao_humana && <Badge tone="info">Corrigido</Badge>}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <Link to={`/atos/${ato.id}`}>
                        <Button variant="secondary">Ver detalhe</Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-sm text-slate-600">
            <span>
              Mostrando {offset + 1}–{Math.min(offset + PAGINA_TAMANHO, total)} de {total}
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGINA_TAMANHO))}
              >
                Anterior
              </Button>
              <Button
                variant="secondary"
                disabled={offset + PAGINA_TAMANHO >= total}
                onClick={() => setOffset(offset + PAGINA_TAMANHO)}
              >
                Próxima
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
