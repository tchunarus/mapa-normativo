/* Mapa Eleitoral: interface. Lê docs/data/eleicoes/ (gerado por coletor/eleicoes/publicar.py)
   e se registra no Mapa Normativo como módulo (rota #eleicoes, aba e seção de busca).
   Nenhuma regra jurídica é decidida aqui: classificações, explicações, fundamentos e
   dependências vêm prontos dos dados publicados. */
(() => {
"use strict";
const MN = window.MapaNormativo, F = window.MapaEleitoralFiltros;
if (!MN || !F) return;
const { esc, FMT, FMTH, getJSON, ls } = MN.util;
const BASE = "eleicoes/";
const C = { dados: {}, carregando: {}, erro: {} };

// ------------------------------------------------------------ dados (carga sob demanda, com cache)
function dado(arquivo) {
  if (C.dados[arquivo]) return C.dados[arquivo];
  if (!C.carregando[arquivo] && !C.erro[arquivo]) {
    C.carregando[arquivo] = getJSON(BASE + arquivo)
      .then(d => { C.dados[arquivo] = d; })
      .catch(e => { C.erro[arquivo] = e.message || String(e); })
      .finally(() => { delete C.carregando[arquivo]; if (F.parseRota(location.hash) || location.hash === "#busca") MN.render(true); });
  }
  return null;
}
const carregando = (msg) => `<p class="loading">${esc(msg || "Carregando o Mapa Eleitoral…")}</p>`;
function falha(arquivo) {
  return C.erro[arquivo] ? `<div class="empty">Não foi possível carregar os dados (${esc(C.erro[arquivo])}). <a class="ref" href="#eleicoes">Voltar ao Mapa Eleitoral</a></div>` : null;
}

// ------------------------------------------------------------ utilitários de exibição
const IDX = () => C.dados["index.json"];
const rot = (grupo, v) => ((IDX().rotulos || {})[grupo] || {})[v] || v || "";
const cargoDe = id => (IDX().cargos || {})[id] || {};
const eleicaoPorRota = r => (IDX().eleicoes || []).find(e => e.rota === r);
const eleicaoPorId = id => (IDX().eleicoes || []).find(e => e.id === id);
const cargoEleicao = (el, rota) => (el.cargos || []).find(c => c.rota === rota);
const hrefCargo = (el, ce) => F.montarRota({ v: "cargo", eleicao: el.rota, cargo: ce.rota });
const hrefCand = id => F.montarRota({ v: "candidato", id });
const hrefProp = id => F.montarRota({ v: "proposta", id });
const plural = (n, s, p) => `${n.toLocaleString("pt-BR")} ${n === 1 ? s : p}`;
function situacaoBadge(s, oficial) {
  const ativa = F.SITUACOES_ATIVAS.indexOf(s) >= 0 && s !== "INDEFERIDO_COM_RECURSO";
  const cls = s === "DEFERIDO" ? "ok" : ativa ? "gold" : "warn";
  return `<span class="badge ${cls}" title="Situação oficial no TSE: ${esc(oficial || rot("situacao", s))}">${esc(oficial || rot("situacao", s))}</span>`;
}
function regraLink(r) {
  if (!r) return "";
  if (r.fora_da_base) return `<a class="ref el-fora" href="${esc(r.url)}" target="_blank" rel="noopener" title="${esc(r.observacao || "Texto ainda não incorporado ao Mapa Normativo")}">${esc(r.rotulo)}*</a>`;
  return `<a class="ref" href="#d.${esc(r.dispositivo)}" title="Abrir o artigo no Mapa Normativo">${esc(r.rotulo)}</a>`;
}
function fonteLink(f, curta) {
  if (!f) return "";
  const tipo = `<span class="badge">${esc(rot("tipo_fonte", f.tipo))}</span>`;
  const fx = f.fixture ? ` <span class="badge warn">fictícia</span>` : "";
  return `${tipo}${fx} <a class="ref" href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.titulo)}</a>` +
    (curta ? "" : `<span class="small muted"> · ${esc(f.publicador)} · acesso em ${esc(FMTH(f.acessado_em))}${f.sha256 ? ` · <span class="mono" title="SHA-256 da resposta original">${esc(f.sha256.slice(0, 12))}</span>` : ""}</span>`);
}
function afirmacaoBloco(a) {
  return `<div class="el-afirm${a.divergencia ? " div" : ""}"><p>${esc(a.texto)}${a.divergencia ? ` <span class="badge warn">fontes divergentes</span>` : ""}</p>
    <ul class="el-fontes">${a.fontes.map(x => `<li><span class="badge ${x.relacao === "SUPPORTS" ? "" : "warn"}">${esc(rot("relacao", x.relacao))}</span> ${fonteLink(x.fonte)}${x.localizador ? `<span class="small muted"> · ${esc(x.localizador)}</span>` : ""}${x.trecho ? `<blockquote class="el-trecho">${esc(x.trecho)}</blockquote>` : ""}</li>`).join("")}</ul></div>`;
}
const fixtureAviso = () => `<div class="el-fixture" role="note"><span class="lab">DEVELOPMENT_FIXTURE</span><p>Dados fictícios de demonstração. Candidaturas, propostas e fontes desta página foram inventadas para testar a análise de competência e não correspondem a pessoas ou documentos reais.</p></div>`;
const crumbs = (itens) => `<p class="crumbs"><a href="#inicio">Mapa Normativo</a><a href="#eleicoes">Mapa Eleitoral</a>${itens.map(([t, h]) => h ? `<a href="${esc(h)}">${esc(t)}</a>` : `<span>${esc(t)}</span>`).join("")}</p>`;

// ------------------------------------------------------------ componentes
function OfficeCard(el, ce) {
  const c = cargoDe(ce.cargo_id);
  const comps = (c.competencias || []).filter(x => x.destaque).slice(0, 4);
  const vagas = ce.vagas ? `<div class="el-kv"><span>Vagas em disputa</span><b>${ce.vagas.n}</b> <span class="small muted" title="${esc(ce.vagas.afirmacao.texto)}">(${esc(ce.vagas.afirmacao.fontes.map(f => f.fonte.tipo === "LEGISLATION" ? "CF, " + (f.localizador || "") : f.fonte.publicador).join("; "))})</span></div>` : "";
  return `<article class="el-card">
    <div class="el-card-top"><span class="badge gold">${esc(rot("esfera", c.esfera))}</span><span class="badge">Poder ${esc(rot("poder", c.poder))}</span><span class="badge">${esc(rot("sistema", c.sistema))}</span></div>
    <h3>${esc(c.nome)}</h3><p class="small muted" style="margin:2px 0 0">${esc(ce.ente_nome)} · mandato de ${c.mandato_anos} anos</p>
    <p class="el-funcao">${esc(c.funcao_resumo)}</p>
    ${comps.length ? `<p class="el-mini">Principais competências</p><ul class="el-comps">${comps.map(x => `<li>${esc(x.descricao)} <span class="small">${regraLink(x.regra)}</span></li>`).join("")}</ul>` : ""}
    <div class="el-card-foot">${vagas}<div class="el-kv"><span>Candidaturas</span><b>${ce.n_ativas.toLocaleString("pt-BR")}</b>${ce.n_candidaturas !== ce.n_ativas ? ` <span class="small muted">de ${ce.n_candidaturas.toLocaleString("pt-BR")} registradas</span>` : ""}</div>
      ${ce.observacao && !ce.vagas ? `<p class="small muted" style="margin:6px 0 0">${esc(ce.observacao)}</p>` : ""}
      ${comps.some(x => x.regra && x.regra.fora_da_base) ? `<p class="small muted" style="margin:0">* Constituição do Estado, ainda não incorporada ao Mapa Normativo.</p>` : ""}
      <a class="btn" href="${hrefCargo(el, ce)}">Ver candidatos</a></div>
  </article>`;
}
function CandidateRow(l, col) {
  return `<li><a class="row el-row" href="${hrefCand(l[col.id])}"><div><div class="rt">${esc(l[col.nome])}</div>
    <div class="rs"><span class="mono">${esc(l[col.numero])}</span> · ${esc(l[col.partido] || "sem partido informado")}${l[col.n_propostas] ? ` · ${plural(l[col.n_propostas], "proposta analisada", "propostas analisadas")}` : ""}${l[col.ausente] ? ` · <span class="badge warn">não consta mais da fonte</span>` : ""}</div></div>
    <span class="rm">${situacaoBadge(l[col.situacao], l[col.situacao_oficial])}</span></a></li>`;
}
function ProposalCard(p) {
  const tema = (p.temas || [])[0];
  const cls = p.classificacao && IDX().classificacoes[p.classificacao];
  return `<article class="el-prop"><p class="el-mini">${esc(tema ? tema.nome : "Sem tema")}</p>
    <h4><a href="${hrefProp(p.id)}">${esc(p.titulo)}</a></h4><p class="small">${esc(p.descricao)}</p>
    ${cls ? `<p class="small" style="margin:6px 0 0"><span class="el-tom ${cls.tom}"></span>${esc(cls.titulo)}: <b>${esc(cls.subtitulo)}</b></p>` : ""}
    <div class="srcline">${p.fonte ? `Fonte: ${fonteLink(p.fonte, true)}` : ""}${p.fonte ? `<a href="${esc(p.fonte.url)}" target="_blank" rel="noopener">Ver documento original</a>` : ""}<a href="${hrefProp(p.id)}">Abrir análise →</a></div></article>`;
}
function Veredito(an, cargo) {
  const t = an.rotulo;
  return `<div class="el-veredito ${t.tom}"><p class="lab">${esc(t.titulo)}</p><h3>${esc(t.subtitulo)}</h3><p>${esc(t.resumo)}</p>
    <dl class="el-fatos"><dt>Competência direta do ${esc(cargo.nome_curto)}?</dt><dd>${esc(rot("sim_nao", an.competencia_direta))}</dd>
    <dt>Pode iniciar o processo?</dt><dd>${esc(rot("sim_nao", an.pode_iniciar))}</dd>
    ${an.instrumento ? `<dt>Instrumento necessário</dt><dd>${esc(an.instrumento.nome)} (${esc(an.instrumento.nome_curto)})</dd>` : ""}</dl></div>`;
}
function Etapas(instr, cargo) {
  if (!instr || !instr.etapas || !instr.etapas.length) return "";
  const grupos = {}; instr.etapas.forEach(e => (grupos[e.ordem] = grupos[e.ordem] || []).push(e));
  return `<ol class="el-etapas">${Object.keys(grupos).sort((a, b) => a - b).map(k => {
    const es = grupos[k], ou = es.length > 1 && es[0].papel === "INITIATIVE";
    return `<li class="${es.every(e => e.condicional) ? "cond" : ""}"><p class="el-mini">${esc(rot("papel_etapa", es[0].papel))}${es.every(e => e.condicional) ? " · se for o caso" : ""}</p>
      ${es.map((e, i) => `${i && ou ? '<span class="small muted"> ou </span>' : i ? "<br>" : ""}<b>${esc(e.instituicao)}</b>${e.instituicao === cargo.instituicao ? ' <span class="badge gold">o próprio cargo</span>' : ""}<span class="small muted"> · ${esc(e.descricao)}${e.regra ? ` (${e.dispositivo ? `<a class="ref" href="#d.${esc(e.dispositivo)}">${esc(e.regra)}</a>` : esc(e.regra)})` : ""}</span>`).join("")}</li>`;
  }).join("")}</ol>`;
}
function Participantes(instr, cargo) {
  if (!instr) return "";
  const vistos = [];
  instr.etapas.filter(e => !e.condicional && !(e.papel === "INITIATIVE" && instr.etapas.filter(x => x.ordem === e.ordem).length > 1 && e.instituicao !== cargo.instituicao))
    .forEach(e => { if (vistos.indexOf(e.instituicao) < 0) vistos.push(e.instituicao); });
  return vistos.map(n => `<span class="chip${n === cargo.instituicao ? " el-eu" : ""}">${esc(n)}</span>`).join("");
}
function Fundamento(r) {
  return `<div class="rel"><div class="l">${regraLink(r)}<span class="chips"><span class="badge">${esc(rot("papel_fundamento", r.papel))}</span>${r.alterado_desde_analise ? '<span class="badge warn">texto alterado depois da análise</span>' : ""}</span></div>
    <div><p>${esc(r.resumo)}</p>${r.trecho && r.trecho.length ? `<blockquote class="el-trecho">${r.trecho.map(esc).join("<br>")}<span class="nt">Texto vigente, conforme a compilação oficial do Planalto${conferido(r)}</span></blockquote>` : ""}${r.fora_da_base ? `<p class="small muted">${esc(r.observacao || "")}</p>` : ""}</div></div>`;
}
// data da última conferência do diploma, lida do próprio Mapa Normativo (atualizada a cada execução)
function conferido(r) {
  const k = String(r.dispositivo || "").split(".")[0], d = (MN.util.S.dipMeta || {})[k];
  return d && d.verificado_em ? `, conferida em ${esc(FMTH(d.verificado_em))}` : "";
}
function statusRevisao(an) {
  const rev = an.status_revisao === "REVIEWED" || an.status_revisao === "CORRECTED";
  return `<span class="badge ${rev ? "ok" : "warn"}">${esc(rot("status_revisao", an.status_revisao))}</span>`;
}

// ------------------------------------------------------------ páginas
function pEleicao(rotaEleicao, filtros) {
  const idx = IDX();
  const el = eleicaoPorRota(rotaEleicao) || idx.eleicoes.find(e => e.tipo === "GENERAL");
  if (!el) return `<div class="empty">Eleição não encontrada.</div>`;
  const principal = el.tipo === "GENERAL";
  const municipal = idx.eleicoes.find(e => e.tipo === "MUNICIPAL");
  const demo = idx.eleicoes.find(e => e.tipo === "DEMONSTRATION");
  const datas = (el.afirmacoes || []).map(a => `<li>${esc(a.texto)} <span class="small muted">(${a.fontes.map(f => `<a class="ref" href="${esc(f.fonte.url)}" target="_blank" rel="noopener">${esc(f.fonte.publicador)}${f.localizador ? ", " + esc(f.localizador) : ""}</a>`).join("; ")})</span></li>`).join("");
  const sinc = (idx.sincronizacoes || []).map(s => `<dt>${esc(s.rotulo)}</dt><dd class="small">${esc(FMTH(s.concluido_em || s.iniciado_em))} · ${s.fetched} lidos, ${s.created} novos, ${s.updated} atualizados${s.errors ? `, <b>${s.errors} erro(s)</b>` : ""}</dd>`).join("");
  const cardsMun = municipal ? ["prefeito", "vereador"].map(cid => { const c = cargoDe(cid); return `<article class="el-card fora"><div class="el-card-top"><span class="badge warn">Não votamos nisso em 2026</span><span class="badge">Poder ${esc(rot("poder", c.poder))}</span></div>
      <h3>${esc(c.nome)}</h3><p class="el-funcao">${esc(c.funcao_resumo)}</p><p class="small muted">${(c.regras || []).slice(0, 2).map(regraLink).join(" · ")}</p></article>`; }).join("") : "";
  return `${el.fixture ? fixtureAviso() : ""}<div class="page-head">${crumbs(principal ? [] : [[el.nome, null]])}
      <h2>${esc(principal ? "Eleições " + el.ano : el.nome)}</h2>
      <p class="lede">${esc(el.descricao || "")} Para cada proposta, o mapa responde: o que o candidato propôs, se o cargo tem competência para realizar a medida e, se não puder fazê-lo sozinho, de quem depende.</p>
      ${datas ? `<ul class="el-datas">${datas}</ul>` : ""}
      ${principal ? `<form class="search el-busca" id="elBuscaForm" role="search"><input id="elBusca" type="text" autocomplete="off" aria-label="Pesquisar no Mapa Eleitoral" placeholder="Pesquisar candidato, partido, número, proposta ou tema" value="${esc(filtros.q || "")}"><button class="btn" type="submit">Pesquisar</button></form><div id="elBuscaRes">${buscaInline(filtros.q)}</div>` : ""}
    </div>
    <div class="grid2" style="margin-top:28px"><div>
    <section class="blk" style="margin-top:0"><div class="sec-head"><h3>Em quais cargos votamos?</h3><span class="sec-note">${esc(principal ? "Santa Catarina" : "")}</span></div>
      <div class="el-cards">${(el.cargos || []).map(ce => OfficeCard(el, ce)).join("")}</div></section>
    ${principal && municipal ? `<section class="blk el-municipal"><div class="sec-head"><h3>E os municípios?</h3><span class="sec-note">fora da eleição de 2026</span></div>
      <p class="small" style="max-width:74ch;margin:0 0 12px">Prefeitos e Vereadores não são escolhidos em 2026. ${(municipal.afirmacoes || []).map(a => esc(a.texto)).join(" ")}</p>
      <div class="el-cards">${cardsMun}</div>
      <p class="el-mini" style="margin-top:16px">Municípios acompanhados</p><div class="chips">${(idx.municipios || []).map(m => `<a class="chip" href="${F.montarRota({ v: "municipio", id: m.id })}">${esc(m.nome)}</a>`).join("")}</div></section>` : ""}
    </div><aside class="side">
      <div class="side-box"><h3>Explorar</h3><ul class="list">
        <li><a class="row" href="${F.montarRota({ v: "propostas" })}"><div class="rt" style="font-size:16px">Propostas por classificação</div><span class="rm">→</span></a></li>
        ${demo && principal ? `<li><a class="row" href="${F.montarRota({ v: "eleicao", eleicao: demo.rota })}"><div><div class="rt" style="font-size:16px">Demonstração da análise</div><div class="rs">propostas fictícias, marcadas como tal</div></div><span class="rm">→</span></a></li>` : ""}
        <li><a class="row" href="${F.montarRota({ v: "admin" })}"><div class="rt" style="font-size:16px">Painel de conferência</div><span class="rm">→</span></a></li></ul></div>
      <div class="side-box"><h3>Última sincronização</h3><dl class="kv">${sinc || '<dt class="muted">Nenhuma</dt><dd></dd>'}</dl></div>
      <div class="side-box"><h3>Fontes</h3><ul class="small" style="margin:0;padding-left:18px">${(el.fontes || []).map(f => `<li>${fonteLink(f, true)}</li>`).join("")}</ul>
        <p class="small muted" style="margin:10px 0 0">Candidaturas conforme os dados oficiais do TSE. O mapa não recomenda voto, não classifica candidatos e não faz previsões.</p></div>
    </aside></div>`;
}

function buscaInline(q) {
  if (!q) return "";
  const b = dado("busca.json"); if (!b) return falha("busca.json") || carregando("Carregando o índice…");
  const res = F.buscar(b.itens, q, 20, false);
  if (!res.length) return `<p class="empty">Nada encontrado para “${esc(q)}”.</p>`;
  return `<ul class="list" style="margin-top:8px">${res.map(itemBusca).join("")}</ul>`;
}
function itemBusca(i) {
  const [tipo, id, rotulo, sub] = i;
  const idx = IDX();
  let href = "#eleicoes";
  if (tipo === "candidato") href = hrefCand(id);
  else if (tipo === "proposta") href = hrefProp(id);
  else if (tipo === "tema") href = F.montarRota({ v: "propostas", filtros: { tema: id } });
  else if (tipo === "partido") href = F.montarRota({ v: "propostas", filtros: { q: rotulo.split(" · ")[0] } });
  else if (tipo === "cargo") { for (const el of idx.eleicoes) { const ce = el.cargos.find(c => c.id === id); if (ce) href = hrefCargo(el, ce); } }
  const nome = { candidato: "candidatura", proposta: "proposta", tema: "tema", partido: "partido", cargo: "cargo" }[tipo];
  return `<li><a class="row" href="${esc(href)}"><div><div class="rt" style="font-size:16px">${esc(rotulo)}</div><div class="rs">${esc(sub)}</div></div><span class="rm">${esc(nome)}</span></a></li>`;
}

function pCargo(r) {
  const idx = IDX();
  const el = eleicaoPorRota(r.eleicao); const ce = el && cargoEleicao(el, r.cargo);
  if (!ce) return `<div class="empty">Cargo não encontrado nesta eleição. <a class="ref" href="#eleicoes">Voltar</a></div>`;
  const dados = dado(ce.arquivo); if (!dados) return falha(ce.arquivo) || carregando("Carregando candidaturas…");
  const c = cargoDe(ce.cargo_id), col = {}; dados.colunas.forEach((n, i) => col[n] = i);
  const f = Object.assign({ situacao: "ativas" }, r.filtros);
  const lista = F.filtrarCandidaturas(dados.candidaturas, dados.colunas, f);
  const pag = F.paginar(lista, f.p);
  const partidos = F.opcoes(dados.candidaturas, dados.colunas, "partido");
  const situacoes = F.opcoes(dados.candidaturas, dados.colunas, "situacao");
  const link = p => F.montarRota({ v: "cargo", eleicao: r.eleicao, cargo: r.cargo, filtros: Object.assign({}, r.filtros, { p }) });
  const pager = pag.paginas > 1 ? `<nav class="el-pager" aria-label="Páginas">${pag.pagina > 1 ? `<a class="btn quiet" href="${link(pag.pagina - 1)}">← anterior</a>` : ""}<span class="small muted">página ${pag.pagina} de ${pag.paginas}</span>${pag.pagina < pag.paginas ? `<a class="btn quiet" href="${link(pag.pagina + 1)}">próxima →</a>` : ""}</nav>` : "";
  return `${el.fixture ? fixtureAviso() : ""}<div class="page-head">${crumbs([[el.nome, F.montarRota({ v: "eleicao", eleicao: el.rota })], [c.nome + " · " + ce.ente_nome, null]])}
    <h2>${esc(c.nome)}</h2><p class="lede">${esc(c.funcao_resumo)}</p>
    <div class="el-card-top" style="margin-top:12px"><span class="badge gold">${esc(rot("esfera", c.esfera))}</span><span class="badge">Poder ${esc(rot("poder", c.poder))}</span><span class="badge">${esc(rot("sistema", c.sistema))}</span><span class="badge">mandato de ${c.mandato_anos} anos</span>${ce.vagas ? `<span class="badge">${ce.vagas.n} vaga(s) em disputa</span>` : ""}</div></div>
  <section class="blk"><div class="sec-head"><h3>Candidaturas</h3><span class="sec-note">${pag.total ? `${pag.de} a ${pag.ate} de ${plural(pag.total, "resultado", "resultados")}` : "nenhum resultado"}</span></div>
    <form class="el-filtros" id="elFiltros" data-rota="${esc(JSON.stringify({ eleicao: r.eleicao, cargo: r.cargo }))}" onsubmit="return false">
      <label><span>Nome</span><input type="text" name="q" value="${esc(f.q || "")}" autocomplete="off" placeholder="Nome de urna ou completo"></label>
      <label><span>Partido</span><select name="partido"><option value="">Todos</option>${partidos.map(o => `<option value="${esc(o.valor)}" ${o.valor === f.partido ? "selected" : ""}>${esc(o.valor)} (${o.n})</option>`).join("")}</select></label>
      <label><span>Número</span><input type="text" name="numero" inputmode="numeric" value="${esc(f.numero || "")}" autocomplete="off" placeholder="Ex.: 25"></label>
      <label><span>Situação</span><select name="situacao"><option value="ativas" ${f.situacao === "ativas" ? "selected" : ""}>Candidaturas em disputa</option><option value="todas" ${f.situacao === "todas" ? "selected" : ""}>Todas</option>${situacoes.map(o => `<option value="${esc(o.valor)}" ${o.valor === f.situacao ? "selected" : ""}>${esc(rot("situacao", o.valor))} (${o.n})</option>`).join("")}</select></label>
      <label><span>Cargo</span><select name="cargo">${el.cargos.map(x => `<option value="${esc(x.rota)}" ${x.rota === r.cargo ? "selected" : ""}>${esc(cargoDe(x.cargo_id).nome)}</option>`).join("")}</select></label>
    </form>
    ${pag.itens.length ? `<ul class="list">${pag.itens.map(l => CandidateRow(l, col)).join("")}</ul>` : `<p class="empty">Nenhuma candidatura corresponde aos filtros.</p>`}
    ${pager}
    <p class="small muted" style="margin-top:14px">Lista ordenada por nome, com as candidaturas em disputa primeiro. Dados do TSE sincronizados em ${esc(FMTH(dados.gerado_em))}; a página não consulta o TSE a cada visita.</p></section>`;
}

function pCandidato(r) {
  const arq = `candidaturas/${r.id}.json`;
  const d = dado(arq); if (!d) return falha(arq) || carregando("Carregando candidatura…");
  const el = eleicaoPorId(d.candidatura.eleicao_id) || {}, c = cargoDe(d.cargo_id);
  const ce = (el.cargos || []).find(x => x.id === d.candidatura.cargo_eleicao_id);
  const cd = d.candidatura, p = d.pessoa;
  const abas = [["visao-geral", "Visão geral"], ["propostas", "Propostas"], ["competencia", "Competência"], ["historico", "Histórico"], ["fontes", "Fontes"]];
  const aba = abas.some(a => a[0] === r.aba) ? r.aba : "visao-geral";
  let corpo = "";
  if (aba === "visao-geral") {
    corpo = `<dl class="kv el-bio">${[["Nome completo", p.nome_completo], ["Ocupação", p.ocupacao], ["Grau de instrução", p.grau_instrucao], ["Naturalidade", p.naturalidade],
      ["Partido", d.partido.nome ? `${d.partido.sigla} · ${d.partido.nome}` : d.partido.sigla], ["Coligação ou federação", cd.coligacao], ["Composição", cd.composicao_coligacao],
      ["Candidatura à reeleição", cd.reeleicao === true ? "Sim" : cd.reeleicao === false ? "Não" : null], ["Situação na totalização", cd.totalizacao_oficial],
      ["Processo de registro", cd.tse_processo]].filter(x => x[1]).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
      ${(cd.vices || []).length ? `<p class="el-mini" style="margin-top:18px">${esc(c.id === "senador" ? "Suplentes" : "Vice")}</p><ul class="small" style="margin:4px 0 0;padding-left:18px">${cd.vices.map(v => `<li>${esc(v.nome_urna)} · ${esc(v.cargo || "")} · ${esc(v.partido || "")}</li>`).join("")}</ul>` : ""}
      ${!cd.detalhada ? `<p class="small muted" style="margin-top:14px">Ficha resumida: para este cargo, a sincronização atual traz os dados da lista oficial de candidaturas. Os dados detalhados estão na ficha do TSE indicada em Fontes.</p>` : ""}`;
  } else if (aba === "propostas") {
    corpo = d.propostas.length ? `<div class="el-props">${d.propostas.map(ProposalCard).join("")}</div>` :
      `<div class="empty"><p style="margin:0 0 8px">Nenhuma proposta desta candidatura foi processada e analisada até agora.</p>${d.proposta_governo ? `<p style="margin:0">Documento oficial: ${fonteLink(d.proposta_governo)}. <a class="ref" href="${esc(d.proposta_governo.url)}" target="_blank" rel="noopener">Ver documento original</a></p>` : `<p class="small" style="margin:0">${cd.detalhada ? "A ficha oficial desta candidatura não lista proposta de governo registrada." : "A sincronização atual deste cargo não inclui os documentos da candidatura; consulte a ficha do TSE indicada em Fontes."}</p>`}</div>`;
  } else if (aba === "competencia") {
    const cont = {}; d.propostas.forEach(x => { if (x.classificacao) cont[x.classificacao] = (cont[x.classificacao] || 0) + 1; });
    corpo = `<p style="max-width:74ch;margin:0 0 12px">${esc(c.funcao_resumo)}</p>
      <ul class="el-comps">${(c.competencias || []).map(x => `<li>${esc(x.descricao)} <span class="small">${regraLink(x.regra)}</span>${x.modo === "PARTICIPATES" ? ' <span class="badge">decisão coletiva</span>' : ""}</li>`).join("")}</ul>
      ${Object.keys(cont).length ? `<p class="el-mini" style="margin-top:18px">Propostas desta candidatura, por resultado da análise</p><ul class="list">${Object.entries(cont).map(([k, n]) => `<li><div class="row"><div class="rt" style="font-size:16px">${esc(IDX().classificacoes[k].subtitulo)}</div><span class="rm">${n}</span></div></li>`).join("")}</ul>` : ""}
      <p class="small muted" style="margin-top:12px">Fundamentos: ${(c.regras || []).map(regraLink).join(" · ")}</p>`;
  } else if (aba === "historico") {
    corpo = `<div class="empty">Em preparação. Esta aba reunirá candidaturas anteriores, mandatos exercidos e votações, sempre com fonte oficial.</div>`;
  } else {
    const fontes = [d.fonte, d.proposta_governo].filter(Boolean);
    d.propostas.forEach(x => { if (x.fonte && !fontes.some(f => f.id === x.fonte.id)) fontes.push(x.fonte); });
    corpo = `<ul class="el-fontes">${fontes.map(f => `<li>${fonteLink(f)}${f.descricao ? `<div class="small muted">${esc(f.descricao)}</div>` : ""}${f.snapshot ? `<div class="small muted mono">${esc(f.snapshot)}</div>` : ""}</li>`).join("")}</ul>
      ${(d.afirmacoes || []).map(afirmacaoBloco).join("")}`;
  }
  const foto = cd.foto_url ? `<img class="el-foto" src="${esc(cd.foto_url)}" alt="Foto oficial de ${esc(p.nome_urna)}" width="120" height="160" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : `<div class="el-foto vazia" aria-hidden="true">${esc((p.nome_urna || "?").slice(0, 1))}</div>`;
  return `${d.fixture ? fixtureAviso() : ""}<div class="page-head">${crumbs([[el.nome || "", F.montarRota({ v: "eleicao", eleicao: el.rota })], [c.nome, ce ? hrefCargo(el, ce) : null], [p.nome_urna, null]])}
    <div class="el-cand-head">${foto}<div><h2>${esc(p.nome_urna)}</h2>
      <p class="lede" style="margin-top:6px">${esc(c.nome)} · ${esc(d.ente_nome)}</p>
      <div class="el-card-top" style="margin-top:10px"><span class="badge gold">${esc(d.partido.sigla || "")}</span><span class="badge mono">${esc(cd.numero)}</span>${situacaoBadge(cd.situacao, cd.situacao_oficial)}${cd.ausente_desde ? `<span class="badge warn">não consta mais da fonte desde ${esc(FMT(cd.ausente_desde))}</span>` : ""}</div>
      ${d.fonte ? `<p class="small muted" style="margin:10px 0 0">Fonte: <a class="ref" href="${esc(d.fonte.url)}" target="_blank" rel="noopener">${esc(d.fonte.titulo)}</a> · acesso em ${esc(FMTH(d.fonte.acessado_em))}</p>` : ""}</div></div></div>
  <nav class="tabs-scroll el-abas" aria-label="Seções da candidatura"><div class="tabs">${abas.map(([id, t]) => `<a class="tab" href="${F.montarRota({ v: "candidato", id: r.id, aba: id })}" ${id === aba ? 'aria-current="page"' : ""}>${t}${id === "propostas" && d.propostas.length ? `<span class="n">${d.propostas.length}</span>` : ""}</a>`).join("")}</div></nav>
  <section class="blk" style="margin-top:20px">${corpo}</section>`;
}

function pProposta(r) {
  const arq = `propostas/${r.id}.json`;
  const d = dado(arq); if (!d) return falha(arq) || carregando("Carregando proposta…");
  const c = cargoDe(d.cargo_id), cand = d.candidatura, an = d.analise;
  const el = eleicaoPorId(cand.eleicao_id) || {};
  const principal = (d.afirmacoes || []).find(a => a.tipo === "PROPOSAL");
  const fonte = principal && principal.fontes.find(f => f.relacao === "SUPPORTS");
  const outras = (d.afirmacoes || []).filter(a => a !== principal);
  const deps = an ? an.dependencias.filter(x => !x.condicional) : [], cond = an ? an.dependencias.filter(x => x.condicional) : [];
  const alt = deps.filter(x => x.alternativa), obrig = deps.filter(x => !x.alternativa);
  return `${d.fixture ? fixtureAviso() : ""}<div class="page-head">${crumbs([[el.nome || "", F.montarRota({ v: "eleicao", eleicao: el.rota })], [cand.nome, hrefCand(cand.id)], ["Proposta", null]])}
    <p class="el-mini">${(d.temas || []).map(t => esc(t.nome)).join(" · ") || "Sem tema"}</p>
    <h2>${esc(d.titulo)}</h2><p class="lede">${esc(d.descricao)}</p>
    <p class="small muted" style="margin:10px 0 0">Proposta de <a class="ref" href="${hrefCand(cand.id)}">${esc(cand.nome)}</a>, candidatura a ${esc(c.nome)}${d.materia ? ` · matéria: ${esc(d.materia.nome)} (${esc(rot("nivel", d.materia.nivel))})` : ""} · ${esc(rot("natureza_medida", d.natureza_medida))}</p></div>
  <div class="grid2"><div>
    <section class="blk" style="margin-top:22px"><div class="sec-head"><h3>Fonte original</h3></div>
      ${fonte ? `<p style="margin:0">${fonteLink(fonte.fonte)}${fonte.localizador ? `<span class="small muted"> · ${esc(fonte.localizador)}</span>` : ""}</p><div class="actions"><a class="btn quiet" href="${esc(fonte.fonte.url)}" target="_blank" rel="noopener">Ver documento original</a></div>` : ""}</section>
    ${an ? `<section class="blk"><div class="sec-head"><h3>O cargo pode fazer isso?</h3>${statusRevisao(an)}</div>${Veredito(an, c)}</section>
    <section class="blk"><div class="sec-head"><h3>Por quê?</h3></div><p style="max-width:78ch;margin:0">${esc(an.explicacao)}</p>
      ${(an.observacoes || []).length ? `<ul class="small el-obs">${an.observacoes.map(o => `<li>${esc(o)}</li>`).join("")}</ul>` : ""}
      ${an.aviso_texto_alterado ? `<div class="alert" style="margin-top:12px"><span class="lab">Fundamento alterado</span><p>O texto de ${esc(an.aviso_texto_alterado.join(", "))} mudou depois desta análise. A conclusão precisa ser conferida.</p></div>` : ""}</section>
    ${an.instrumento ? `<section class="blk"><div class="sec-head"><h3>O que seria necessário?</h3></div>
      <p style="margin:0"><b>${esc(an.instrumento.nome)}</b> <span class="badge">${esc(an.instrumento.nome_curto)}</span></p><p class="small" style="max-width:74ch">${esc(an.instrumento.descricao)}${an.instrumento.quorum ? ` Quórum: ${esc(an.instrumento.quorum)}` : ""}</p>
      <p class="el-mini">Participam</p><div class="chips">${Participantes(an.instrumento, c)}</div>
      <p class="el-mini" style="margin-top:14px">Etapas</p>${Etapas(an.instrumento, c)}
      ${an.alternativas.length ? `<p class="el-mini" style="margin-top:14px">Outro caminho</p>${an.alternativas.map(a => `<div class="el-alt"><b>${esc(a.nome)}</b> <span class="badge">${esc(a.nome_curto)}</span><p class="small">${esc(a.nota || a.descricao)}</p>${Etapas(a, c)}</div>`).join("")}` : ""}</section>` : ""}
    <section class="blk"><div class="sec-head"><h3>De quem depende?</h3></div>
      ${obrig.length || alt.length ? `<ul class="list">${obrig.map(x => `<li class="el-dep"><b>${esc(x.instituicao)}</b>${x.cargo_integra ? ' <span class="badge gold">o cargo integra, decisão coletiva</span>' : ""}<p class="small">${esc(x.explicacao.replace(/\.$/, ""))}${x.regra ? ` (${regraLink(x.regra)})` : ""}.</p></li>`).join("")}
        ${alt.length ? `<li class="el-dep"><b>Iniciativa de um destes:</b> ${alt.map(x => esc(x.instituicao)).join(", ")}<p class="small">${esc(alt[0].explicacao)}</p></li>` : ""}</ul>` : `<p class="empty">A medida não depende de aprovação de outro órgão.</p>`}
      ${cond.length ? `<p class="el-mini" style="margin-top:10px">Se for o caso</p><ul class="small" style="margin:4px 0 0;padding-left:18px">${cond.map(x => `<li>${esc(x.instituicao)}: ${esc(x.explicacao)}</li>`).join("")}</ul>` : ""}</section>
    <section class="blk"><div class="sec-head"><h3>Fundamento jurídico</h3><span class="sec-note">clique para abrir o artigo no Mapa Normativo</span></div>${an.fundamentos.map(Fundamento).join("")}</section>` :
      `<section class="blk"><p class="empty">Análise de competência ainda não gerada para esta proposta.</p></section>`}
    <section class="blk"><div class="sec-head"><h3>Fontes utilizadas</h3></div>${(d.afirmacoes || []).map(afirmacaoBloco).join("")}</section>
  </div><aside class="side">
    ${an ? `<div class="side-box"><h3>Sobre esta análise</h3><dl class="kv"><dt>Situação</dt><dd>${statusRevisao(an)}</dd><dt>Confiança</dt><dd>${esc(rot("confianca", an.confianca))}</dd><dt>Método</dt><dd class="small">${esc(an.analisador)} · ${esc(an.versao_analisador)}</dd><dt>Atualizada em</dt><dd class="small">${esc(FMTH(an.atualizado_em))}</dd></dl>
      <p class="small muted" style="margin:10px 0 0">Classificação gerada por regras a partir das competências e dos instrumentos cadastrados, com fundamento conferido contra a redação vigente. Não constitui parecer jurídico.</p></div>` : ""}
    ${d.grupo && d.grupo.propostas.length ? `<div class="side-box"><h3>Propostas semelhantes</h3><p class="small muted" style="margin:0 0 6px">${esc(d.grupo.titulo)}</p><ul class="list">${d.grupo.propostas.map(q => `<li><a class="row" href="${hrefProp(q.id)}"><div><div class="rt" style="font-size:15.5px">${esc(q.titulo)}</div><div class="rs">${esc(q.candidatura.nome)} · ${esc(cargoDe(q.candidatura.cargo_id).nome)}</div></div></a></li>`).join("")}</ul></div>` : ""}
    ${outras.length ? `<div class="side-box"><h3>Outras afirmações</h3>${outras.map(afirmacaoBloco).join("")}</div>` : ""}
  </aside></div>`;
}

function pMunicipio(r) {
  const idx = IDX(); const m = (idx.municipios || []).find(x => x.id === r.id);
  if (!m) return `<div class="empty">Município não acompanhado. <a class="ref" href="#eleicoes">Voltar</a></div>`;
  const el = eleicaoPorId(m.eleicao_id) || {};
  const floripa = m.ente === "SC/Florianópolis";
  return `<div class="page-head">${crumbs([[m.nome, null]])}<h2>${esc(m.nome)}</h2>
    <p class="lede">O Município elege Prefeito, Vice-Prefeito e Vereadores. Esses cargos não fazem parte das Eleições Gerais de 2026. ${(el.afirmacoes || []).map(a => esc(a.texto)).join(" ")}</p></div>
  <section class="blk"><div class="sec-head"><h3>Cargos municipais</h3><span class="badge warn">Não votamos nisso em 2026</span></div>
    <div class="el-cards">${m.cargos.map(cid => { const c = cargoDe(cid); return `<article class="el-card fora"><h3>${esc(c.nome)}</h3><p class="el-funcao">${esc(c.funcao_resumo)}</p>
      <ul class="el-comps">${(c.competencias || []).map(x => `<li>${esc(x.descricao)} <span class="small">${regraLink(x.regra)}</span></li>`).join("")}</ul><p class="small muted">${(c.regras || []).map(regraLink).join(" · ")}</p></article>`; }).join("")}</div></section>
  <section class="blk"><div class="sec-head"><h3>Legislação municipal no Mapa Normativo</h3></div>
    ${floripa ? `<p class="small" style="margin:0">O Código Tributário do Município já está na base: <a class="ref" href="#dip.floripa_ctm">Código Tributário de Florianópolis</a>.</p>` :
      `<p class="small" style="margin:0">O Código Tributário de São José ainda não entrou na base: a Câmara Municipal só disponibiliza o texto original de 2005, sem as alterações posteriores, e publicar esse texto como vigente seria incorreto.</p>`}
    <p class="small muted" style="margin:10px 0 0">Esta página será ampliada com candidaturas e propostas quando houver eleição municipal.</p></section>`;
}

function pPropostas(r) {
  const idx = IDX(); const d = dado("propostas.json"); if (!d) return falha("propostas.json") || carregando();
  const f = r.filtros || {};
  const col = {}; d.colunas.forEach((n, i) => col[n] = i);
  const lista = F.filtrarPropostas(d, f);
  const pag = F.paginar(lista, f.p);
  const sel = (nome, rotulo, opcoes) => `<label><span>${rotulo}</span><select name="${nome}"><option value="">Todas</option>${opcoes.map(([v, t]) => `<option value="${esc(v)}" ${f[nome] === v ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
  const link = p => F.montarRota({ v: "propostas", filtros: Object.assign({}, f, { p }) });
  return `<div class="page-head">${crumbs([["Propostas", null]])}<h2>Propostas analisadas</h2>
    <p class="lede">Filtre por resultado da análise, instrumento necessário, tema ou nível da matéria: por exemplo, propostas que exigem PEC ou propostas que tratam de assunto municipal.</p></div>
  <section class="blk"><form class="el-filtros" id="elFiltrosProp" onsubmit="return false">
    <label><span>Texto</span><input type="text" name="q" value="${esc(f.q || "")}" autocomplete="off" placeholder="Título ou candidatura"></label>
    ${sel("classificacao", "Resultado", Object.entries(idx.classificacoes).map(([k, v]) => [k, v.subtitulo]))}
    ${sel("instrumento", "Instrumento", idx.instrumentos.map(i => [i.id, i.nome]))}
    ${sel("tema", "Tema", idx.temas.map(t => [t.id, t.nome]))}
    ${sel("nivel", "Nível da matéria", Object.entries(idx.rotulos.nivel))}
    ${sel("eleicao", "Eleição", idx.eleicoes.map(e => [e.id, e.nome]))}
  </form>
  <div class="sec-head" style="margin-top:14px"><h3>${plural(pag.total, "proposta", "propostas")}</h3>${lista.some(p => p[col.fixture]) ? '<span class="badge warn">inclui dados fictícios de demonstração</span>' : ""}</div>
  ${pag.itens.length ? `<ul class="list">${pag.itens.map(p => { const cl = idx.classificacoes[p[col.classificacao]]; return `<li><a class="row" href="${hrefProp(p[col.id])}"><div><div class="rt">${esc(p[col.titulo])}</div><div class="rs">${esc(p[col.candidato])} · ${esc(cargoDe(p[col.cargo_id]).nome)}${p[col.fixture] ? " · fictícia" : ""}</div></div><span class="rm">${cl ? `<span class="el-tom ${cl.tom}"></span>${esc(cl.subtitulo)}` : ""}</span></a></li>`; }).join("")}</ul>` :
    `<p class="empty">Nenhuma proposta corresponde aos filtros. As propostas reais das candidaturas de 2026 ainda não foram processadas; a demonstração usa dados fictícios.</p>`}
  ${pag.paginas > 1 ? `<nav class="el-pager">${pag.pagina > 1 ? `<a class="btn quiet" href="${link(pag.pagina - 1)}">← anterior</a>` : ""}<span class="small muted">página ${pag.pagina} de ${pag.paginas}</span>${pag.pagina < pag.paginas ? `<a class="btn quiet" href="${link(pag.pagina + 1)}">próxima →</a>` : ""}</nav>` : ""}</section>`;
}

function pAdmin() {
  const d = dado("admin.json"); if (!d) return falha("admin.json") || carregando("Carregando o painel…");
  const lista = (titulo, itens, fmt, vazio) => `<section class="blk"><div class="sec-head"><h3>${esc(titulo)}</h3><span class="sec-note">${itens.length}</span></div>${itens.length ? `<ul class="small el-admin">${itens.map(x => `<li>${fmt(x)}</li>`).join("")}</ul>` : `<p class="empty">${esc(vazio || "Nada a conferir.")}</p>`}</section>`;
  const ingest = d.ingestoes.map(l => `<tr><td>${esc(l.rotulo)}<div class="small muted">${esc(l.fonte)} · ${esc(l.transporte)}</div></td><td class="mono small">${esc(FMTH(l.concluido_em || l.iniciado_em))}</td><td class="mono">${l.fetched ?? ""}</td><td class="mono">${l.created ?? ""}</td><td class="mono">${l.updated ?? ""}</td><td class="mono">${l.unchanged ?? ""}</td><td class="mono">${l.missing ?? ""}</td><td class="mono">${l.errors ? `<b>${l.errors}</b>` : 0}</td></tr>
    ${(l.erros || []).length ? `<tr><td colspan="8" class="small" style="color:var(--warn)">${l.erros.slice(0, 5).map(esc).join("<br>")}</td></tr>` : ""}`).join("");
  return `<div class="page-head">${crumbs([["Painel de conferência", null]])}<h2>Painel de conferência</h2>
    <p class="lede">Estado das sincronizações, da integridade dos dados e das análises que aguardam revisão. Gerado em ${esc(FMTH(d.gerado_em))}.</p></div>
  <section class="blk"><div class="sec-head"><h3>Sincronizações</h3></div><div class="tbl-wrap"><table><thead><tr><th>Fonte</th><th>Quando</th><th>Lidos</th><th>Novos</th><th>Atualizados</th><th>Inalterados</th><th>Ausentes</th><th>Erros</th></tr></thead><tbody>${ingest}</tbody></table></div></section>
  ${lista("Erros de integridade", d.erros_integridade.concat(d.erros_fundamentos), esc, "Nenhum erro: todas as chaves, enumerações e fundamentos conferem.")}
  ${lista("Análises pendentes de revisão", d.analises_pendentes, a => `<a class="ref" href="${hrefProp(a.proposta_id)}">${esc(a.proposta_id)}</a> · ${esc(a.classificacao)} · ${esc(a.status)}${a.fixture ? " · fictícia" : ""}`)}
  ${lista("Fundamentos alterados depois da análise", d.fundamentos_alterados, x => `${esc(x.analise_id)}: ${esc(x.regra)}`)}
  ${lista("Afirmações sem fonte (não publicadas)", d.afirmacoes_sem_fonte, a => `${esc(a.id)}: ${esc(a.texto)}${a.fixture ? " · fictícia" : ""}`)}
  ${lista("Propostas não publicadas", d.propostas_nao_publicadas, esc)}
  ${lista("Fontes divergentes", d.divergencias, a => `${esc(a.id)}: ${esc(a.texto)}`)}
  ${lista("Duplicidades", d.duplicidades, esc)}
  ${lista("Outros avisos", d.avisos_integridade.filter(a => d.duplicidades.indexOf(a) < 0), esc)}
  ${lista("Fundamentos fora da base normativa", d.regras_fora_da_base, esc)}
  ${lista("Mudanças recentes nos dados do TSE", d.mudancas_recentes.filter(m => m.tipo !== "criado").slice(0, 40), m => `${esc(FMTH(m.em))} · ${esc(m.tipo)} · ${esc(m.tabela)}.${esc(m.id)}${m.campos ? " · " + esc(m.campos.join(", ")) : ""}`, "Nenhuma alteração registrada além da carga inicial.")}
  <section class="blk"><div class="sec-head"><h3>Registros por tabela</h3></div><dl class="kv">${Object.entries(d.contagens).filter(x => x[1]).map(([k, v]) => `<dt class="mono small">${esc(k)}</dt><dd class="mono small">${v}</dd>`).join("")}</dl></section>`;
}

// ------------------------------------------------------------ registro no Mapa Normativo
function render(h) {
  const r = F.parseRota("#" + h);
  if (!r) return "";
  const idx = dado("index.json"); if (!idx) return falha("index.json") || carregando();
  switch (r.v) {
    case "inicio": return pEleicao(null, r.filtros);
    case "eleicao": return pEleicao(r.eleicao, r.filtros);
    case "cargo": return pCargo(r);
    case "candidato": return pCandidato(r);
    case "proposta": return pProposta(r);
    case "municipio": return pMunicipio(r);
    case "propostas": return pPropostas(r);
    case "admin": return pAdmin();
    default: return `<div class="empty">Página não encontrada. <a class="ref" href="#eleicoes">Voltar ao Mapa Eleitoral</a></div>`;
  }
}

let foco = null, espera;
function aplicarFiltros(form, rotaBase) {
  const f = {}; new FormData(form).forEach((v, k) => { if (v !== "" && k !== "cargo" && !(k === "situacao" && v === "ativas")) f[k] = String(v); });
  const r = F.parseRota(location.hash);
  const cargo = form.elements.cargo ? form.elements.cargo.value : null;
  const nova = rotaBase === "propostas" ? F.montarRota({ v: "propostas", filtros: f }) : F.montarRota({ v: "cargo", eleicao: r.eleicao, cargo: cargo || r.cargo, filtros: cargo && cargo !== r.cargo ? {} : f });
  if (nova === location.hash) return;
  history.replaceState(null, "", nova);
  MN.render(true);
}
function depois() {
  const bf = document.getElementById("elBuscaForm");
  if (bf) {
    const inp = document.getElementById("elBusca");
    const atualiza = () => { const r = F.parseRota(location.hash) || { v: "inicio" }; const nova = F.montarRota({ v: r.v === "eleicao" ? "eleicao" : "inicio", eleicao: r.eleicao, filtros: inp.value.trim() ? { q: inp.value.trim() } : {} });
      history.replaceState(null, "", nova); document.getElementById("elBuscaRes").innerHTML = buscaInline(inp.value.trim()); };
    bf.addEventListener("submit", e => { e.preventDefault(); atualiza(); });
    inp.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(atualiza, 250); });
  }
  ["elFiltros", "elFiltrosProp"].forEach(id => {
    const form = document.getElementById(id); if (!form) return;
    const base = id === "elFiltrosProp" ? "propostas" : "cargo";
    form.querySelectorAll("select").forEach(s => s.addEventListener("change", () => { foco = null; aplicarFiltros(form, base); }));
    form.querySelectorAll("input").forEach(i => i.addEventListener("input", () => { clearTimeout(espera); foco = i.name; espera = setTimeout(() => aplicarFiltros(form, base), 250); }));
    if (foco && form.elements[foco]) { const i = form.elements[foco]; i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
  });
  document.querySelectorAll("img.el-foto").forEach(img => img.addEventListener("error", () => { img.replaceWith(Object.assign(document.createElement("div"), { className: "el-foto vazia", textContent: (img.alt.replace("Foto oficial de ", "") || "?").slice(0, 1) })); }));
}

// seção na pesquisa geral do Mapa Normativo
function busca(q) {
  if (!q) return "";
  if (!C.dados["index.json"]) dado("index.json");
  const b = dado("busca.json"); if (!b || !C.dados["index.json"]) return "";
  const res = F.buscar(b.itens, q, 6, false);
  if (!res.length) return "";
  return `<section class="blk"><div class="sec-head"><h3>Mapa Eleitoral</h3><a class="sec-note ref" href="${F.montarRota({ v: "inicio", filtros: { q } })}">ver todos</a></div><ul class="list">${res.map(itemBusca).join("")}</ul></section>`;
}

MN.registrar({ id: "eleicoes", aba: ["eleicoes", "Eleições"], corresponde: h => /^eleicoes(\/|\?|$)/.test(h), render, depois, busca });
})();
