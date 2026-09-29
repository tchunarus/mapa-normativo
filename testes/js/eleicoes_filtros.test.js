// Testes das funções puras do Mapa Eleitoral: node --test testes/js/
const test = require("node:test");
const assert = require("node:assert/strict");
const F = require("../../web/eleicoes_filtros.js");

test("rotas: leitura e montagem são inversas", () => {
  const casos = [
    { v: "inicio", filtros: {} },
    { v: "eleicao", eleicao: "2026", filtros: {} },
    { v: "cargo", eleicao: "2026", cargo: "presidente", filtros: {} },
    { v: "cargo", eleicao: "2026", cargo: "sc/deputado-estadual", filtros: { q: "joão", partido: "PL", p: "3" } },
    { v: "candidato", id: "tse-240002553718", aba: "propostas", filtros: {} },
    { v: "proposta", id: "fx-ana-ir", filtros: {} },
    { v: "municipio", id: "florianopolis", filtros: {} },
    { v: "propostas", filtros: { instrumento: "pec", tema: "tributacao" } },
    { v: "admin", filtros: {} },
  ];
  for (const r of casos) {
    const h = F.montarRota(r);
    const lido = F.parseRota(h);
    assert.equal(lido.v, r.v, h);
    for (const k of ["eleicao", "cargo", "id"]) if (r[k]) assert.equal(lido[k], r[k], h);
    assert.deepEqual(lido.filtros, r.filtros, h);
  }
  assert.equal(F.montarRota({ v: "cargo", eleicao: "2026", cargo: "sc/senador", filtros: { p: 1 } }), "#eleicoes/2026/sc/senador");
  assert.equal(F.parseRota("#eleicoes/candidato/tse-1").aba, "visao-geral");
  assert.equal(F.parseRota("#d.cf.84"), null);
  assert.equal(F.parseRota("#eleicoesx"), null);
});

const colunas = ["id", "nome", "numero", "partido", "situacao", "situacao_oficial", "n_propostas", "busca", "ausente"];
const linhas = [
  ["a", "João da Silva", 22123, "PL", "DEFERIDO", "Deferido", 0, "joao da silva joao pedro da silva 22123 pl", 0],
  ["b", "Maria Souza", 13000, "PT", "RENUNCIA", "Renúncia", 0, "maria souza 13000 pt", 0],
  ["c", "José Lima", 22555, "PL", "INDEFERIDO", "Indeferido", 0, "jose lima 22555 pl", 0],
  ["d", "Ana Joana", 55111, "PSD", "AGUARDANDO_JULGAMENTO", "Pendente de julgamento", 1, "ana joana 55111 psd", 0],
];

test("filtros de candidaturas", () => {
  assert.deepEqual(F.filtrarCandidaturas(linhas, colunas, {}).map(l => l[0]), ["a", "d"]);  // padrão: só as em disputa
  assert.deepEqual(F.filtrarCandidaturas(linhas, colunas, { situacao: "todas" }).length, 4);
  assert.deepEqual(F.filtrarCandidaturas(linhas, colunas, { situacao: "RENUNCIA" }).map(l => l[0]), ["b"]);
  assert.deepEqual(F.filtrarCandidaturas(linhas, colunas, { q: "JOÃO", situacao: "todas" }).map(l => l[0]), ["a"]);  // sem acento
  assert.deepEqual(F.filtrarCandidaturas(linhas, colunas, { q: "silva pedro" }).map(l => l[0]), ["a"]);  // todos os termos
  assert.deepEqual(F.filtrarCandidaturas(linhas, colunas, { partido: "pl", situacao: "todas" }).map(l => l[0]), ["a", "c"]);
  assert.deepEqual(F.filtrarCandidaturas(linhas, colunas, { numero: "22", situacao: "todas" }).map(l => l[0]), ["a", "c"]);  // prefixo
  assert.deepEqual(F.filtrarCandidaturas(linhas, colunas, { numero: "55-111" }).map(l => l[0]), ["d"]);
  assert.deepEqual(F.opcoes(linhas, colunas, "partido").map(o => [o.valor, o.n]), [["PL", 2], ["PSD", 1], ["PT", 1]]);
});

test("paginação", () => {
  const lista = Array.from({ length: 95 }, (_, i) => i);
  let p = F.paginar(lista, 1, 40);
  assert.deepEqual([p.pagina, p.paginas, p.total, p.de, p.ate, p.itens.length], [1, 3, 95, 1, 40, 40]);
  p = F.paginar(lista, 3, 40);
  assert.deepEqual([p.de, p.ate, p.itens.length], [81, 95, 15]);
  assert.equal(F.paginar(lista, 99, 40).pagina, 3);
  assert.equal(F.paginar(lista, "x", 40).pagina, 1);
  assert.deepEqual([F.paginar([], 1).total, F.paginar([], 1).paginas, F.paginar([], 1).de], [0, 1, 0]);
});

test("busca: termos, pesos e exclusão de dados fictícios", () => {
  const itens = [
    ["candidato", "1", "Jorginho Mello", "Governador · 22 · PL", "jorginho mello 22 pl", 0],
    ["candidato", "2", "Candidata Exemplo Ana", "Presidente", "candidata exemplo ana 91", 1],
    ["cargo", "3", "Governador do Estado (Santa Catarina)", "Eleições 2026", "governador do estado santa catarina", 0],
    ["tema", "t", "Tributação", "Impostos", "tributacao impostos", 0],
  ];
  assert.deepEqual(F.buscar(itens, "jorginho").map(i => i[1]), ["1"]);
  assert.deepEqual(F.buscar(itens, "exemplo"), []);
  assert.deepEqual(F.buscar(itens, "exemplo", 10, true).map(i => i[1]), ["2"]);
  assert.deepEqual(F.buscar(itens, "Tributação").map(i => i[1]), ["t"]);
  assert.deepEqual(F.buscar(itens, "governador").map(i => i[0]), ["cargo"]);  // cargo pesa mais
  assert.deepEqual(F.buscar(itens, "a"), []);  // termo curto demais
});

test("filtro de propostas por classificação, instrumento e tema", () => {
  const idx = { colunas: ["id", "titulo", "candidatura_id", "candidato", "cargo_id", "eleicao_id", "classificacao", "instrumento_id", "temas", "nivel", "status_revisao", "fixture"],
    propostas: [
      ["p1", "Acabar com a reeleição", "c1", "Ana", "presidente", "demo", "CONSTITUTIONAL_AMENDMENT_REQUIRED", "pec", ["instituicoes-politicas"], "FEDERAL", "AUTO_GENERATED", 1],
      ["p2", "Reduzir o IPTU", "c1", "Ana", "presidente", "demo", "MUNICIPAL_DEPENDENCY", "lei-municipal", ["tributacao", "municipios"], "MUNICIPAL", "AUTO_GENERATED", 1],
    ] };
  assert.deepEqual(F.filtrarPropostas(idx, { instrumento: "pec" }).map(p => p[0]), ["p1"]);
  assert.deepEqual(F.filtrarPropostas(idx, { tema: "municipios" }).map(p => p[0]), ["p2"]);
  assert.deepEqual(F.filtrarPropostas(idx, { nivel: "MUNICIPAL" }).map(p => p[0]), ["p2"]);
  assert.deepEqual(F.filtrarPropostas(idx, { q: "reeleicao" }).map(p => p[0]), ["p1"]);
  assert.deepEqual(F.filtrarPropostas(idx, {}).length, 2);
});
