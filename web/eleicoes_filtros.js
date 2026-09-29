/* Mapa Eleitoral: funções puras de rota, filtro, paginação e busca.
   Sem acesso ao DOM, para poderem ser testadas com Node (testes/js/). Na página, ficam em
   window.MapaEleitoralFiltros; no Node, em module.exports. */
(function (raiz) {
  "use strict";
  const norm = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const POR_PAGINA = 40;
  const SITUACOES_ATIVAS = ["DEFERIDO", "DEFERIDO_COM_RECURSO", "AGUARDANDO_JULGAMENTO", "INDEFERIDO_COM_RECURSO"];

  function lerQuery(qs) {
    const out = {};
    String(qs || "").split("&").filter(Boolean).forEach(par => {
      const i = par.indexOf("=");
      const k = decodeURIComponent(i < 0 ? par : par.slice(0, i));
      const v = i < 0 ? "" : decodeURIComponent(par.slice(i + 1).replace(/\+/g, " "));
      if (k) out[k] = v;
    });
    return out;
  }
  function montarQuery(f) {
    const pares = Object.keys(f || {}).filter(k => f[k] !== undefined && f[k] !== null && f[k] !== "" && !(k === "p" && +f[k] === 1))
      .sort().map(k => encodeURIComponent(k) + "=" + encodeURIComponent(f[k]));
    return pares.length ? "?" + pares.join("&") : "";
  }

  /* "#eleicoes/2026/sc/governador?partido=PL&p=2" -> {v:"cargo", eleicao:"2026", cargo:"sc/governador", filtros:{...}} */
  function parseRota(hash) {
    let h = String(hash || "").replace(/^#/, "");
    try { h = decodeURI(h); } catch (e) { /* mantém como veio */ }
    const iq = h.indexOf("?");
    const filtros = iq >= 0 ? lerQuery(h.slice(iq + 1)) : {};
    const partes = (iq >= 0 ? h.slice(0, iq) : h).split("/").filter(Boolean);
    if (partes[0] !== "eleicoes") return null;
    const r = partes.slice(1);
    if (!r.length) return { v: "inicio", filtros };
    if (r[0] === "candidato" && r[1]) return { v: "candidato", id: r[1], aba: r[2] || "visao-geral", filtros };
    if (r[0] === "proposta" && r[1]) return { v: "proposta", id: r[1], filtros };
    if (r[0] === "municipios" && r[1]) return { v: "municipio", id: r[1], filtros };
    if (r[0] === "propostas") return { v: "propostas", filtros };
    if (r[0] === "admin") return { v: "admin", filtros };
    if (r.length === 1) return { v: "eleicao", eleicao: r[0], filtros };
    return { v: "cargo", eleicao: r[0], cargo: r.slice(1).join("/"), filtros };
  }
  function montarRota(r) {
    const q = montarQuery(r.filtros);
    switch (r.v) {
      case "inicio": return "#eleicoes" + q;
      case "candidato": return "#eleicoes/candidato/" + r.id + (r.aba && r.aba !== "visao-geral" ? "/" + r.aba : "") + q;
      case "proposta": return "#eleicoes/proposta/" + r.id + q;
      case "municipio": return "#eleicoes/municipios/" + r.id + q;
      case "propostas": return "#eleicoes/propostas" + q;
      case "admin": return "#eleicoes/admin" + q;
      case "eleicao": return "#eleicoes/" + r.eleicao + q;
      case "cargo": return "#eleicoes/" + r.eleicao + "/" + r.cargo + q;
      default: return "#eleicoes";
    }
  }

  /* linhas no formato compacto de cargos/<id>.json; colunas nomeiam as posições */
  function filtrarCandidaturas(linhas, colunas, f) {
    const c = {}; (colunas || []).forEach((n, i) => c[n] = i);
    const q = norm(f && f.q), partido = norm(f && f.partido), numero = String((f && f.numero) || "").replace(/\D/g, "");
    const sit = (f && f.situacao) || "ativas";
    return (linhas || []).filter(l => {
      if (q && !q.split(/\s+/).every(t => l[c.busca].includes(t))) return false;
      if (partido && norm(l[c.partido]) !== partido) return false;
      if (numero && !String(l[c.numero]).startsWith(numero)) return false;
      if (sit === "ativas" && SITUACOES_ATIVAS.indexOf(l[c.situacao]) < 0) return false;
      if (sit !== "ativas" && sit !== "todas" && l[c.situacao] !== sit) return false;
      return true;
    });
  }
  function paginar(lista, pagina, por) {
    por = por || POR_PAGINA;
    const total = (lista || []).length, paginas = Math.max(1, Math.ceil(total / por));
    const p = Math.min(Math.max(1, parseInt(pagina, 10) || 1), paginas);
    return { itens: (lista || []).slice((p - 1) * por, p * por), pagina: p, paginas, total, de: total ? (p - 1) * por + 1 : 0, ate: Math.min(total, p * por) };
  }
  function opcoes(linhas, colunas, campo) {
    const i = (colunas || []).indexOf(campo), cont = {};
    (linhas || []).forEach(l => { const v = l[i]; if (v !== "" && v !== null && v !== undefined) cont[v] = (cont[v] || 0) + 1; });
    return Object.keys(cont).sort((a, b) => a.localeCompare(b, "pt-BR")).map(v => ({ valor: v, n: cont[v] }));
  }

  /* índice propostas.json: filtros por classificação, instrumento, tema, cargo, nível e eleição */
  function filtrarPropostas(idx, f) {
    const c = {}; (idx.colunas || []).forEach((n, i) => c[n] = i);
    const q = norm(f && f.q);
    return (idx.propostas || []).filter(p => {
      if (f.classificacao && p[c.classificacao] !== f.classificacao) return false;
      if (f.instrumento && p[c.instrumento_id] !== f.instrumento) return false;
      if (f.tema && (p[c.temas] || []).indexOf(f.tema) < 0) return false;
      if (f.cargo && p[c.cargo_id] !== f.cargo) return false;
      if (f.nivel && p[c.nivel] !== f.nivel) return false;
      if (f.eleicao && p[c.eleicao_id] !== f.eleicao) return false;
      if (q && !norm(p[c.titulo] + " " + p[c.candidato]).includes(q)) return false;
      return true;
    });
  }

  /* busca.json: itens [tipo, id, rotulo, sub, busca, fixture]; todos os termos precisam aparecer */
  function buscar(itens, consulta, limite, comFixtures) {
    const termos = norm(consulta).split(/[^a-z0-9]+/).filter(t => t.length > 1);
    if (!termos.length) return [];
    const peso = { cargo: 4, tema: 3, partido: 3, candidato: 2, proposta: 1 };
    return (itens || []).filter(i => (comFixtures || !i[5]) && termos.every(t => i[4].includes(t)))
      .map(i => ({ i, s: (peso[i[0]] || 0) + (norm(i[2]).startsWith(termos[0]) ? 2 : 0) }))
      .sort((a, b) => b.s - a.s || a.i[2].localeCompare(b.i[2], "pt-BR")).slice(0, limite || 12).map(x => x.i);
  }

  const api = { norm, lerQuery, montarQuery, parseRota, montarRota, filtrarCandidaturas, paginar, opcoes, filtrarPropostas, buscar, POR_PAGINA, SITUACOES_ATIVAS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else raiz.MapaEleitoralFiltros = api;
})(typeof window !== "undefined" ? window : this);
