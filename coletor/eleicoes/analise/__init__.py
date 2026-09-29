"""Camada de análise de competência das propostas.

Arquitetura: ingestão -> processamento -> análise -> validação -> persistência ->
publicação. A página nunca chama um modelo de linguagem: lê o resultado estruturado
gravado em estado/eleicoes/analises.json (e tabelas associadas), com status de revisão.

Contrato (equivalente ao `ProposalAnalyzer.analyze(proposal, office)` da especificação):

    class AnalisadorProposta:
        nome: str
        versao: str
        def analisar(self, proposta, cargo, ctx) -> Resultado

`ctx` é um Contexto com o banco carregado e os índices. `Resultado` reúne a análise e
as linhas das tabelas filhas (fundamentos, dependências, alternativas). Toda
implementação:

- só pode citar regras existentes na tabela `regras` (conferidas contra o Mapa Normativo);
- devolve status AUTO_GENERATED; revisão humana é registrada à parte (tabela revisoes);
- informa `hash_entrada`, para que a análise seja refeita quando os dados mudarem.

Implementações: AnalisadorPorRegras (regras.py, determinístico e auditável),
AnalisadorLLM (llm.py, previsto e não implementado) e AnalisadorRevisado (revisao.py,
que aplica as revisões gravadas sobre o resultado de outro analisador).
"""
import hashlib, json


class Resultado:
    def __init__(self, analise, fundamentos=(), dependencias=(), alternativas=()):
        self.analise = analise
        self.fundamentos = list(fundamentos)
        self.dependencias = list(dependencias)
        self.alternativas = list(alternativas)


class AnalisadorProposta:
    nome = 'abstrato'
    versao = '0'

    def analisar(self, proposta, cargo, ctx):
        raise NotImplementedError


class Contexto:
    """Índices do banco usados pelos analisadores."""

    def __init__(self, banco, info_regras=None):
        self.banco = banco
        self.t = {n: banco.por_id(n) for n in ('cargos', 'materias', 'competencias', 'instrumentos', 'instituicoes',
                                                  'regras', 'candidaturas', 'propostas')}
        self.etapas = {}
        for e in banco.tabelas['instrumento_etapas']:
            self.etapas.setdefault(e['instrumento_id'], []).append(e)
        for v in self.etapas.values():
            v.sort(key=lambda e: e['ordem'])  # estável: mantém a ordem do arquivo dentro de cada etapa
        self.comp_por_materia = {}
        for c in banco.tabelas['competencias']:
            if c.get('materia_id'):
                self.comp_por_materia.setdefault(c['materia_id'], []).append(c)
        self.poderes = {}
        for cc in banco.tabelas['cargo_competencias']:
            self.poderes.setdefault(cc['cargo_id'], []).append((cc, self.t['competencias'][cc['competencia_id']]))
        self.info_regras = info_regras or {}

    def hash_entrada(self, proposta, cargo):
        """Tudo o que a análise lê: se qualquer parte mudar, a análise é refeita."""
        m = self.t['materias'].get(proposta.get('materia_id')) or {}
        comps = self.comp_por_materia.get(m.get('id'), [])
        instr = {c.get('instrumento_id') for c in comps} | {c.get('instrumento_id') for _, c in self.poderes.get(cargo['id'], [])}
        base = {
            'proposta': {k: proposta.get(k) for k in ('materia_id', 'natureza_medida', 'titulo', 'descricao')},
            'cargo': cargo, 'materia': m, 'competencias': comps,
            'poderes': [(cc, c) for cc, c in self.poderes.get(cargo['id'], [])],
            'instrumentos': [self.t['instrumentos'].get(i) for i in sorted(x for x in instr if x)],
            'etapas': [self.etapas.get(i, []) for i in sorted(x for x in instr if x)],
            'regras': {k: (v or {}).get('hash') for k, v in sorted(self.info_regras.items())},
        }
        limpo = json.loads(json.dumps(base, default=str, sort_keys=True))
        tira = lambda o: {k: tira(v) for k, v in o.items() if not k.startswith('_')} if isinstance(o, dict) else [tira(x) for x in o] if isinstance(o, list) else o
        return hashlib.sha256(json.dumps(tira(limpo), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
