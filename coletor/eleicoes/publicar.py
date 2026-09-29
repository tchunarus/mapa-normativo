"""Publica os dados do Mapa Eleitoral em docs/data/eleicoes/, prontos para a página.

    python3 coletor/eleicoes/publicar.py [--sem-fixtures]

A página não faz cálculo jurídico nem chama o TSE: só lê estes arquivos.

- index.json: eleições, cargos em disputa, funções e competências dos cargos,
  rótulos das classificações e últimas sincronizações (carregado ao abrir o Mapa Eleitoral);
- cargos/<cargo_eleicao>.json: lista compacta das candidaturas de um cargo, já
  ordenada e com a chave de busca normalizada (filtro e paginação na página);
- candidaturas/<id>.json: ficha da candidatura, carregada só ao abrir o candidato;
- propostas/<id>.json: proposta com análise, fundamentos, dependências e fontes;
- propostas.json: índice de propostas com facetas (classificação, instrumento, temas);
- busca.json: índice para a pesquisa geral (candidatos, cargos, partidos, propostas, temas);
- admin.json: painel de conferência (ingestões, erros, pendências, duplicidades).

Regras de publicação: proposta ou afirmação sem fonte não é publicada; fundamento é
conferido contra a redação vigente do Mapa Normativo no momento da publicação; dado
fictício (DEVELOPMENT_FIXTURE) só aparece na eleição de demonstração e leva a marca.
"""
import argparse, json, os, shutil, sys, unicodedata
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))
import repositorio, normativo  # noqa: E402
from fontes import ENTES  # noqa: E402

OUT = os.path.join(repositorio.RAIZ, 'docs', 'data', 'eleicoes')
FIX = repositorio.FIXTURE

CLASSIFICACOES = {
    'DIRECT_POWER': ('Competência do cargo', 'Pode fazer diretamente',
                     'O ocupante do cargo dispõe de instrumento próprio para adotar a medida, sem depender da aprovação de outro órgão.', 'ok'),
    'LEGISLATION_REQUIRED': ('Competência do cargo', 'Depende de aprovação legislativa',
                             'O ocupante do cargo possui meios institucionais para promover a medida, mas sua implementação não ocorre unilateralmente.', 'mid'),
    'CONSTITUTIONAL_AMENDMENT_REQUIRED': ('Exige mudança na Constituição', 'Depende de emenda constitucional',
                                          'A medida só é possível com a alteração da Constituição Federal, aprovada por maioria qualificada nas duas Casas do Congresso.', 'mid'),
    'SHARED_COMPETENCE': ('Competência compartilhada', 'Atuação conjunta entre entes',
                          'A matéria é dividida entre União, Estados e Municípios; o cargo atua na parte que cabe ao seu ente.', 'mid'),
    'FEDERAL_DEPENDENCY': ('Fora da esfera do cargo', 'Depende da União',
                           'A decisão cabe a órgãos federais; o cargo não tem meios para implementar a medida por conta própria.', 'warn'),
    'STATE_DEPENDENCY': ('Fora da esfera do cargo', 'Depende do Estado',
                         'A decisão cabe a órgãos estaduais; o cargo não tem meios para implementar a medida por conta própria.', 'warn'),
    'MUNICIPAL_DEPENDENCY': ('Fora da esfera do cargo', 'Depende do Município',
                             'A decisão cabe à Prefeitura e à Câmara Municipal; o cargo não tem meios para implementar a medida por conta própria.', 'warn'),
    'OTHER_BRANCH_DEPENDENCY': ('Competência de outro Poder', 'Depende de outro Poder',
                                'A execução cabe a outro Poder do mesmo ente; o cargo pode contribuir, mas não realiza a medida sozinho.', 'warn'),
    'OUTSIDE_OFFICE_COMPETENCE': ('Fora da competência do cargo', 'Não é atribuição do cargo',
                                  'A medida, na forma proposta, é ato de outro órgão, do qual o cargo não participa.', 'warn'),
    'INSUFFICIENT_INFORMATION': ('Análise inconclusiva', 'Informação insuficiente',
                                 'A proposta não traz elementos suficientes para avaliar a competência do cargo.', 'mute'),
}
ROTULOS = {
    'esfera': {'FEDERAL': 'Federal', 'STATE': 'Estadual', 'MUNICIPAL': 'Municipal'},
    'poder': {'EXECUTIVE': 'Executivo', 'LEGISLATIVE': 'Legislativo', 'JUDICIARY': 'Judiciário'},
    'sistema': {'MAJORITARIAN': 'Majoritário', 'PROPORTIONAL': 'Proporcional'},
    'status_revisao': {'AUTO_GENERATED': 'Análise automatizada, ainda não revisada', 'PENDING_REVIEW': 'Análise pendente de revisão',
                       'REVIEWED': 'Análise revisada', 'CORRECTED': 'Análise revisada e corrigida'},
    'confianca': {'HIGH': 'alta', 'MEDIUM': 'média', 'LOW': 'baixa'},
    'sim_nao': {'YES': 'Sim', 'NO': 'Não', 'PARTIAL': 'Em parte', 'DEPENDS': 'Depende de apoio coletivo', 'NOT_APPLICABLE': 'Não se aplica'},
    'tipo_fonte': {'TSE': 'TSE', 'LEGISLATION': 'Legislação', 'COURT_DECISION': 'Decisão judicial', 'LEGISLATIVE_RECORD': 'Registro legislativo',
                   'GOVERNMENT_DOCUMENT': 'Documento de governo', 'CANDIDATE_DOCUMENT': 'Documento da candidatura',
                   'CANDIDATE_STATEMENT': 'Declaração da candidatura', 'INTERVIEW': 'Entrevista', 'NEWS': 'Notícia',
                   'FACT_CHECK': 'Checagem', 'POLL': 'Pesquisa', 'ACADEMIC': 'Acadêmico', 'OTHER': 'Outro'},
    'relacao': {'SUPPORTS': 'confirma', 'CONTRADICTS': 'diverge', 'CORRECTS': 'corrige', 'MENTIONS': 'menciona'},
    'situacao': {'DEFERIDO': 'Deferido', 'DEFERIDO_COM_RECURSO': 'Deferido com recurso', 'INDEFERIDO': 'Indeferido',
                 'INDEFERIDO_COM_RECURSO': 'Indeferido com recurso', 'AGUARDANDO_JULGAMENTO': 'Aguardando julgamento',
                 'CANCELADO': 'Cancelado', 'CASSADO': 'Cassado', 'RENUNCIA': 'Renúncia', 'FALECIDO': 'Falecido',
                 'NAO_CONHECIDO': 'Pedido não conhecido', 'OUTRO': 'Outra situação'},
    'papel_etapa': {'INITIATIVE': 'Iniciativa', 'DELIBERATION': 'Votação', 'SANCTION_VETO': 'Sanção ou veto', 'PROMULGATION': 'Promulgação',
                    'EXECUTION': 'Execução', 'REGULATION': 'Edição do ato', 'BUDGET_AMENDMENT': 'Emenda ao orçamento', 'VETO_REVIEW': 'Análise do veto'},
    'papel_fundamento': {'COMPETENCE': 'Competência', 'INSTRUMENT': 'Instrumento', 'INITIATIVE': 'Atribuição do cargo',
                         'PROCEDURE': 'Procedimento', 'LIMIT': 'Limite'},
    'natureza_medida': {'CONSTITUTIONAL_CHANGE': 'Mudança na Constituição', 'COMPLEMENTARY_LAW_CHANGE': 'Mudança em lei complementar',
                        'LEGAL_CHANGE': 'Mudança em lei', 'EXECUTIVE_REGULATION': 'Regulamento do Executivo',
                        'ADMINISTRATIVE_ACTION': 'Ação de gestão', 'PUBLIC_WORK_OR_SERVICE': 'Obra ou serviço público',
                        'BUDGET_ALLOCATION': 'Destinação de recursos', 'OVERSIGHT': 'Fiscalização', 'UNSPECIFIED': 'Não especificada'},
    'nivel': {'FEDERAL': 'Federal', 'STATE': 'Estadual', 'MUNICIPAL': 'Municipal', 'SHARED': 'Compartilhada'},
}
SITUACAO_ATIVA = {'DEFERIDO', 'DEFERIDO_COM_RECURSO', 'AGUARDANDO_JULGAMENTO', 'INDEFERIDO_COM_RECURSO'}


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s or '')) if unicodedata.category(c) != 'Mn').lower()


DESTINO = {'pasta': OUT}


def salvar(rel, obj):
    cam = os.path.join(DESTINO['pasta'], rel)
    os.makedirs(os.path.dirname(cam), exist_ok=True)
    with open(cam, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))


def nome_ente(e):
    return 'Brasil' if e == 'BR' else (ENTES.get(e) or {}).get('nome', e)


class Publicador:
    def __init__(self, banco, info_regras, agora):
        self.b, self.info, self.agora = banco, info_regras, agora
        self.t = {n: banco.por_id(n) for n in repositorio.TABELAS}
        self.idx = {}
        for nome in ('afirmacao_fontes', 'proposta_temas', 'analise_regras', 'analise_alternativas', 'dependencias',
                     'cargo_competencias', 'instrumento_etapas', 'candidaturas', 'propostas', 'afirmacoes', 'analises'):
            self.idx[nome] = {}
        chaves = {'afirmacao_fontes': 'afirmacao_id', 'proposta_temas': 'proposta_id', 'analise_regras': 'analise_id',
                  'analise_alternativas': 'analise_id', 'dependencias': 'analise_id', 'cargo_competencias': 'cargo_id',
                  'instrumento_etapas': 'instrumento_id', 'candidaturas': 'cargo_eleicao_id', 'propostas': 'candidatura_id',
                  'analises': 'proposta_id'}
        for nome, k in chaves.items():
            for r in banco.tabelas[nome]:
                self.idx[nome].setdefault(r.get(k), []).append(r)
        self.afirm_por_proposta, self.afirm_por_cand = {}, {}
        for a in banco.tabelas['afirmacoes']:
            if a.get('proposta_id'):
                self.afirm_por_proposta.setdefault(a['proposta_id'], []).append(a)
            elif a.get('candidatura_id'):
                self.afirm_por_cand.setdefault(a['candidatura_id'], []).append(a)
        self.nao_publicadas = []

    # ------------------------------------------------------------ peças
    def fonte(self, fid):
        f = self.t['fontes'].get(fid)
        if not f:
            return None
        out = {k: f.get(k) for k in ('id', 'titulo', 'publicador', 'url', 'tipo', 'data_publicacao', 'data_documento', 'acessado_em',
                                     'autor', 'descricao', 'url_arquivada', 'sha256', 'snapshot') if f.get(k)}
        if f.get('origem_dado') == FIX:
            out['fixture'] = True
        return out

    def afirmacao(self, a):
        fs = []
        for cs in self.idx['afirmacao_fontes'].get(a['id'], []):
            f = self.fonte(cs['fonte_id'])
            if f:
                fs.append({'fonte': f, 'relacao': cs['relacao'], 'localizador': cs.get('localizador'), 'trecho': cs.get('trecho')})
        if not fs:
            return None
        out = {k: a.get(k) for k in ('id', 'texto', 'tipo', 'data_evento', 'confianca', 'status_revisao', 'valor') if a.get(k) is not None}
        out['fontes'] = fs
        out['divergencia'] = any(x['relacao'] in ('CONTRADICTS', 'CORRECTS') for x in fs)
        return out

    def regra(self, rid):
        r = self.t['regras'][rid]
        i = self.info.get(rid) or {}
        out = {'id': rid, 'rotulo': r['rotulo'], 'resumo': r['resumo']}
        if r.get('fora_da_base'):
            out.update({'fora_da_base': True, 'norma': r.get('norma'), 'url': r.get('url'), 'observacao': r.get('observacao')})
        else:
            out.update({'dispositivo': r['dispositivo'], 'localizador': r.get('localizador'), 'diploma': i.get('diploma'),
                        'url_oficial': i.get('url_oficial'), 'trecho': i.get('trecho_vigente'),
                        'hash': i.get('hash')})
        return out

    def cargo(self, cid):
        c = self.t['cargos'][cid]
        comps = []
        for cc in sorted(self.idx['cargo_competencias'].get(cid, []), key=lambda x: x.get('ordem', 0)):
            comp = self.t['competencias'][cc['competencia_id']]
            comps.append({'descricao': comp['descricao'], 'modo': cc['modo'], 'destaque': bool(cc.get('destaque')),
                          'natureza': comp['natureza'], 'regra': self.regra(comp['regra_id'])})
        inst = self.t['instituicoes'][c['instituicao_id']]
        return {k: c.get(k) for k in ('id', 'nome', 'nome_curto', 'esfera', 'poder', 'sistema', 'mandato_anos', 'funcao_resumo', 'slug')} | {
            'instituicao': inst['nome'], 'regras': [self.regra(r) for r in c.get('regra_ids') or []], 'competencias': comps}

    def candidatura_resumo(self, c):
        p = self.t['candidatos'][c['candidato_id']]
        part = self.t['partidos'].get(c.get('partido_id')) or {}
        return {'id': c['id'], 'nome': p['nome_urna'], 'numero': c['numero'], 'partido': part.get('sigla'), 'cargo_id': c['cargo_id'],
                'cargo_eleicao_id': c.get('cargo_eleicao_id'), 'eleicao_id': c['eleicao_id'], 'ente': c['ente'],
                'fixture': c.get('origem_dado') == FIX or None}

    def publicavel(self, p):
        return any(self.afirmacao(a) for a in self.afirm_por_proposta.get(p['id'], []) if a['tipo'] == 'PROPOSAL')

    def analise(self, p):
        a = next(iter(self.idx['analises'].get(p['id'], [])), None)
        if not a:
            return None
        out = {k: a.get(k) for k in ('id', 'classificacao', 'competencia_direta', 'pode_iniciar', 'explicacao', 'resumo_fundamento',
                                     'confianca', 'status_revisao', 'analisador', 'versao_analisador', 'observacoes', 'atualizado_em', 'original')
               if a.get(k) is not None}
        rot = CLASSIFICACOES[a['classificacao']]
        out['rotulo'] = {'titulo': rot[0], 'subtitulo': rot[1], 'resumo': rot[2], 'tom': rot[3]}
        fund, alterados = [], []
        for ar in self.idx['analise_regras'].get(a['id'], []):
            r = self.regra(ar['regra_id'])
            r['papel'] = ar['papel']
            if ar.get('hash_dispositivo') and r.get('hash') and ar['hash_dispositivo'] != r['hash']:
                r['alterado_desde_analise'] = True; alterados.append(r['rotulo'])
            fund.append(r)
        ordem = {'COMPETENCE': 0, 'INSTRUMENT': 1, 'INITIATIVE': 2, 'PROCEDURE': 3, 'LIMIT': 4}
        out['fundamentos'] = sorted(fund, key=lambda r: ordem.get(r['papel'], 9))
        if alterados:
            out['aviso_texto_alterado'] = alterados
        if a.get('instrumento_id'):
            out['instrumento'] = self.instrumento(a['instrumento_id'], p)
        out['alternativas'] = [self.instrumento(x['instrumento_id'], p) | {'nota': x.get('nota')}
                               for x in self.idx['analise_alternativas'].get(a['id'], [])]
        deps = []
        for d in sorted(self.idx['dependencias'].get(a['id'], []), key=lambda d: d['ordem']):
            inst = self.t['instituicoes'][d['instituicao_id']]
            deps.append({'instituicao': inst['nome'], 'instituicao_id': inst['id'], 'tipo': d['tipo'], 'explicacao': d['explicacao'],
                         'etapa': d.get('etapa_ordem'), 'alternativa': bool(d.get('alternativa')), 'condicional': bool(d.get('condicional')),
                         'cargo_integra': bool(d.get('cargo_integra')), 'regra': self.regra(d['regra_id']) if d.get('regra_id') else None})
        out['dependencias'] = deps
        return out

    def instrumento(self, iid, p=None):
        i = self.t['instrumentos'][iid]
        etapas = [{'ordem': e['ordem'], 'papel': e['papel'], 'instituicao': self.t['instituicoes'][e['instituicao_id']]['nome'],
                   'instituicao_id': e['instituicao_id'], 'descricao': e['descricao'], 'condicional': bool(e.get('condicional')),
                   'regra': self.t['regras'][e['regra_id']]['rotulo'] if e.get('regra_id') else None,
                   'dispositivo': self.t['regras'][e['regra_id']].get('dispositivo') if e.get('regra_id') else None}
                  for e in self.idx['instrumento_etapas'].get(iid, [])]
        return {k: i.get(k) for k in ('id', 'nome', 'nome_curto', 'descricao', 'quorum', 'exige_sancao') if i.get(k) is not None} | {
            'regra': self.regra(i['regra_id']) if i.get('regra_id') else None, 'etapas': etapas}

    def temas_de(self, pid):
        out = []
        for pt in sorted(self.idx['proposta_temas'].get(pid, []), key=lambda x: not x.get('principal')):
            t = self.t['temas'][pt['tema_id']]
            out.append({'id': t['id'], 'nome': t['nome']})
        return out

    # ------------------------------------------------------------ arquivos
    def publicar(self, com_fixtures=True):
        cargos_pub = {cid: self.cargo(cid) for cid in self.t['cargos']}
        eleicoes, busca, idx_prop = [], [], []
        partidos_vistos = {}
        for el in sorted(self.b.tabelas['eleicoes'], key=lambda e: (e['tipo'] == 'DEMONSTRATION', e['ano'])):
            fixture = el.get('origem_dado') == FIX
            if fixture and not com_fixtures:
                continue
            ces = []
            for ce in sorted(self.b.onde('cargos_eleicao', eleicao_id=el['id']), key=lambda x: x.get('ordem', 0)):
                cands = self.idx['candidaturas'].get(ce['id'], [])
                linhas, n_prop = [], 0
                for c in cands:
                    r = self.candidatura_resumo(c)
                    props = [p for p in self.idx['propostas'].get(c['id'], []) if self.publicavel(p)]
                    n_prop += len(props)
                    part = self.t['partidos'].get(c.get('partido_id')) or {}
                    linhas.append([c['id'], r['nome'], c['numero'], part.get('sigla') or '', c['situacao'], c.get('situacao_oficial') or '',
                                   len(props), norm(' '.join([r['nome'], self.t['candidatos'][c['candidato_id']].get('nome_completo') or '',
                                                              str(c['numero']), part.get('sigla') or '', part.get('nome') or ''])),
                                   1 if c.get('ausente_desde') else 0])
                    busca.append(['candidato', c['id'], r['nome'], f"{self.t['cargos'][c['cargo_id']]['nome_curto']} · {c['numero']} · {part.get('sigla') or ''}",
                                  norm(' '.join([r['nome'], str(c['numero']), part.get('sigla') or ''])), 1 if fixture else 0])
                    if part.get('id'):
                        partidos_vistos.setdefault(part['id'], [part, 0])[1] += 1
                linhas.sort(key=lambda x: (x[4] not in SITUACAO_ATIVA, norm(x[1])))
                vagas = None
                af = self.t['afirmacoes'].get(ce.get('vagas_afirmacao_id') or '')
                if af:
                    pub = self.afirmacao(af)
                    if pub:
                        vagas = {'n': af['valor']['vagas'], 'afirmacao': pub}
                arquivo = f'cargos/{ce["id"]}.json'
                salvar(arquivo, {'id': ce['id'], 'eleicao_id': el['id'], 'rota': ce['rota'], 'cargo_id': ce['cargo_id'], 'ente': ce['ente'],
                                 'ente_nome': nome_ente(ce['ente']), 'fixture': fixture or None, 'gerado_em': self.agora,
                                 'colunas': ['id', 'nome', 'numero', 'partido', 'situacao', 'situacao_oficial', 'n_propostas', 'busca', 'ausente'],
                                 'candidaturas': linhas})
                ces.append({'id': ce['id'], 'rota': ce['rota'], 'cargo_id': ce['cargo_id'], 'ente': ce['ente'], 'ente_nome': nome_ente(ce['ente']),
                            'n_candidaturas': len(cands), 'n_ativas': sum(1 for l in linhas if l[4] in SITUACAO_ATIVA),
                            'n_propostas': n_prop, 'vagas': vagas, 'observacao': ce.get('observacao'), 'arquivo': arquivo})
                busca.append(['cargo', ce['id'], f"{self.t['cargos'][ce['cargo_id']]['nome']} ({nome_ente(ce['ente'])})", el['nome'],
                              norm(self.t['cargos'][ce['cargo_id']]['nome'] + ' ' + nome_ente(ce['ente'])), 1 if fixture else 0])
            afirm = [x for x in (self.afirmacao(self.t['afirmacoes'][a]) for a in el.get('afirmacao_ids') or [] if a in self.t['afirmacoes']) if x]
            eleicoes.append({k: el.get(k) for k in ('id', 'nome', 'ano', 'tipo', 'rota', 'data_primeiro_turno', 'data_segundo_turno', 'descricao')} | {
                'fixture': fixture or None, 'afirmacoes': afirm, 'fontes': [x for x in (self.fonte(f) for f in el.get('fonte_ids') or []) if x],
                'cargos': ces})
        for pid, (part, n) in sorted(partidos_vistos.items()):
            busca.append(['partido', pid, part['sigla'] + (f" · {part['nome']}" if part.get('nome') else ''), f'{n} candidatura(s)',
                          norm(part['sigla'] + ' ' + (part.get('nome') or '')), 1 if part.get('origem_dado') == FIX else 0])
        for t in self.b.tabelas['temas']:
            busca.append(['tema', t['id'], t['nome'], t.get('descricao') or '', norm(t['nome'] + ' ' + (t.get('descricao') or '')), 0])

        # candidaturas e propostas
        for c in self.b.tabelas['candidaturas']:
            if c.get('origem_dado') == FIX and not com_fixtures:
                continue
            self.publicar_candidatura(c, cargos_pub, idx_prop, busca)
        salvar('propostas.json', {'gerado_em': self.agora, 'colunas': ['id', 'titulo', 'candidatura_id', 'candidato', 'cargo_id', 'eleicao_id',
                                                                         'classificacao', 'instrumento_id', 'temas', 'nivel', 'status_revisao', 'fixture'],
                                  'propostas': idx_prop})
        salvar('busca.json', {'gerado_em': self.agora, 'colunas': ['tipo', 'id', 'rotulo', 'sub', 'busca', 'fixture'], 'itens': busca})
        ingest = sorted(self.b.tabelas['ingestoes'], key=lambda x: x['iniciado_em'])
        ultimas = {}
        for l in ingest:
            ultimas[l['rotulo']] = {k: l.get(k) for k in ('rotulo', 'fonte', 'iniciado_em', 'concluido_em', 'transporte', 'fetched', 'created',
                                                          'updated', 'unchanged', 'missing', 'errors')}
        indice = {'versao': 1, 'gerado_em': self.agora, 'eleicoes': eleicoes, 'cargos': cargos_pub,
                  'classificacoes': {k: {'titulo': v[0], 'subtitulo': v[1], 'resumo': v[2], 'tom': v[3]} for k, v in CLASSIFICACOES.items()},
                  'rotulos': ROTULOS, 'temas': [{k: t.get(k) for k in ('id', 'nome', 'descricao', 'pai_id')} for t in
                                                sorted(self.b.tabelas['temas'], key=lambda t: t.get('ordem', 0))],
                  'instrumentos': [{k: i.get(k) for k in ('id', 'nome', 'nome_curto')} for i in sorted(self.b.tabelas['instrumentos'], key=lambda i: i.get('ordem', 0))],
                  'municipios': self.municipios(), 'sincronizacoes': list(ultimas.values()),
                  'contagens': {'candidaturas': sum(1 for c in self.b.tabelas['candidaturas'] if c.get('origem_dado') != FIX),
                                'propostas_publicadas': sum(1 for p in idx_prop if not p[11]),
                                'propostas_demonstracao': sum(1 for p in idx_prop if p[11]),
                                'fontes': sum(1 for f in self.b.tabelas['fontes'] if f.get('origem_dado') != FIX)}}
        salvar('index.json', indice)
        return indice

    def publicar_candidatura(self, c, cargos_pub, idx_prop, busca):
        pessoa = self.t['candidatos'][c['candidato_id']]
        part = self.t['partidos'].get(c.get('partido_id')) or {}
        fixture = c.get('origem_dado') == FIX
        props = []
        for p in sorted(self.idx['propostas'].get(c['id'], []), key=lambda x: x['id']):
            if not self.publicavel(p):
                self.nao_publicadas.append(p['id']); continue
            an = self.analise(p)
            temas = self.temas_de(p['id'])
            afirm = [x for x in (self.afirmacao(a) for a in self.afirm_por_proposta.get(p['id'], [])) if x]
            m = self.t['materias'].get(p.get('materia_id')) or {}
            grupo = self.t['grupos_proposta'].get(p.get('grupo_id') or '')
            semelhantes = []
            if grupo:
                for q in self.b.tabelas['propostas']:
                    if q.get('grupo_id') == grupo['id'] and q['id'] != p['id'] and self.publicavel(q):
                        qc = self.t['candidaturas'][q['candidatura_id']]
                        semelhantes.append({'id': q['id'], 'titulo': q['titulo'], 'candidatura': self.candidatura_resumo(qc)})
            pub = {'id': p['id'], 'titulo': p['titulo'], 'descricao': p['descricao'], 'natureza_medida': p['natureza_medida'],
                   'materia': {'id': m.get('id'), 'nome': m.get('nome'), 'nivel': m.get('nivel')} if m else None,
                   'temas': temas, 'afirmacoes': afirm, 'analise': an, 'status_extracao': p['status_revisao'],
                   'grupo': {'id': grupo['id'], 'titulo': grupo['titulo'], 'propostas': semelhantes} if grupo else None,
                   'candidatura': self.candidatura_resumo(c), 'cargo_id': c['cargo_id'], 'fixture': fixture or None,
                   'gerado_em': self.agora}
            salvar(f'propostas/{p["id"]}.json', pub)
            fonte_principal = next((f['fonte'] for a in afirm for f in a['fontes'] if f['relacao'] == 'SUPPORTS'), None)
            props.append({'id': p['id'], 'titulo': p['titulo'], 'descricao': p['descricao'], 'temas': temas, 'fonte': fonte_principal,
                          'classificacao': an and an['classificacao'], 'status_revisao': an and an['status_revisao']})
            idx_prop.append([p['id'], p['titulo'], c['id'], pessoa['nome_urna'], c['cargo_id'], c['eleicao_id'], an and an['classificacao'],
                             an and (an.get('instrumento') or {}).get('id'), [t['id'] for t in temas], m.get('nivel'),
                             an and an['status_revisao'], 1 if fixture else 0])
            busca.append(['proposta', p['id'], p['titulo'], pessoa['nome_urna'], norm(p['titulo'] + ' ' + p['descricao'] + ' ' +
                          ' '.join(t['nome'] for t in temas)), 1 if fixture else 0])
        afirm_c = [x for x in (self.afirmacao(a) for a in self.afirm_por_cand.get(c['id'], [])) if x]
        pub = {'id': c['id'], 'fixture': fixture or None, 'gerado_em': self.agora,
               'pessoa': {k: pessoa.get(k) for k in ('nome_urna', 'nome_urna_oficial', 'nome_completo', 'ocupacao', 'grau_instrucao', 'naturalidade') if pessoa.get(k)},
               'candidatura': {k: c.get(k) for k in ('numero', 'situacao', 'situacao_oficial', 'totalizacao_oficial', 'coligacao', 'composicao_coligacao',
                                                     'reeleicao', 'apta', 'foto_url', 'tse_processo', 'vices', 'ente', 'eleicao_id', 'cargo_eleicao_id',
                                                     'detalhada', 'ausente_desde', 'atualizado_em') if c.get(k) not in (None, '')},
               'ente_nome': nome_ente(c['ente']), 'partido': {k: part.get(k) for k in ('sigla', 'nome', 'numero') if part.get(k)},
               'cargo_id': c['cargo_id'], 'fonte': self.fonte(c['fonte_id']),
               'proposta_governo': self.fonte(c.get('proposta_governo_fonte_id')) if c.get('proposta_governo_fonte_id') else None,
               'propostas': props, 'afirmacoes': afirm_c}
        salvar(f'candidaturas/{c["id"]}.json', pub)

    def municipios(self):
        out = []
        for chave in ('SC/Florianópolis', 'SC/São José'):
            e = ENTES.get(chave)
            if not e:
                continue
            slug = norm(e['nome']).replace(' ', '-')
            out.append({'id': slug, 'ente': chave, 'nome': e['nome'], 'uf': e.get('uf'),
                        'cargos': [ce['cargo_id'] for ce in self.b.tabelas['cargos_eleicao'] if ce['ente'] == chave],
                        'eleicao_id': next((ce['eleicao_id'] for ce in self.b.tabelas['cargos_eleicao'] if ce['ente'] == chave), None)})
        return out

    def admin(self, erros, avisos, erros_regras):
        b = self.b
        pend = [{'id': a['id'], 'proposta_id': a['proposta_id'], 'classificacao': a['classificacao'], 'status': a['status_revisao'],
                 'fixture': a.get('origem_dado') == FIX or None, 'observacoes': a.get('observacoes')}
                for a in b.tabelas['analises'] if a['status_revisao'] in ('AUTO_GENERATED', 'PENDING_REVIEW')]
        sem_fonte = [{'id': a['id'], 'texto': a['texto'], 'fixture': a.get('origem_dado') == FIX or None}
                     for a in b.tabelas['afirmacoes'] if not self.idx['afirmacao_fontes'].get(a['id'])]
        divergencias = [{'id': a['id'], 'texto': a['texto']} for a in b.tabelas['afirmacoes']
                        if any(cs['relacao'] in ('CONTRADICTS', 'CORRECTS') for cs in self.idx['afirmacao_fontes'].get(a['id'], []))]
        fundamentos_alterados = []
        for ar in b.tabelas['analise_regras']:
            i = self.info.get(ar['regra_id']) or {}
            if ar.get('hash_dispositivo') and i.get('hash') and ar['hash_dispositivo'] != i['hash']:
                fundamentos_alterados.append({'analise_id': ar['analise_id'], 'regra': self.t['regras'][ar['regra_id']]['rotulo']})
        ingest = sorted(b.tabelas['ingestoes'], key=lambda x: x['iniciado_em'], reverse=True)
        fontes_por_tipo = {}
        for f in b.tabelas['fontes']:
            fontes_por_tipo[f['tipo']] = fontes_por_tipo.get(f['tipo'], 0) + 1
        salvar('admin.json', {
            'gerado_em': self.agora,
            'contagens': {n: len(v) for n, v in b.tabelas.items()},
            'ingestoes': [{k: l.get(k) for k in ('id', 'rotulo', 'fonte', 'iniciado_em', 'concluido_em', 'transporte', 'fetched', 'created',
                                                 'updated', 'unchanged', 'missing', 'errors', 'erros', 'avisos', 'por_escopo')} for l in ingest[:30]],
            'erros_integridade': erros, 'avisos_integridade': avisos, 'erros_fundamentos': erros_regras,
            'analises_pendentes': pend, 'afirmacoes_sem_fonte': sem_fonte, 'divergencias': divergencias,
            'propostas_nao_publicadas': sorted(set(self.nao_publicadas)), 'fundamentos_alterados': fundamentos_alterados,
            'duplicidades': [a for a in avisos if 'repetido' in a or 'duplicidade' in a],
            'fontes_por_tipo': fontes_por_tipo,
            'regras_fora_da_base': [r['rotulo'] for r in b.tabelas['regras'] if r.get('fora_da_base')],
            'mudancas_recentes': (json.load(open(os.path.join(repositorio.RAIZ, 'estado', 'eleicoes', 'mudancas.json')))
                                  if os.path.exists(os.path.join(repositorio.RAIZ, 'estado', 'eleicoes', 'mudancas.json')) else [])[-60:][::-1],
        })


def construir(agora=None, com_fixtures=True, raiz=repositorio.RAIZ):
    banco = repositorio.carregar(raiz)
    # A data de geração é a do último processamento registrado, não a desta execução:
    # sem mudança nos dados, a publicação sai idêntica e não gera commit.
    agora = agora or max((l.get('concluido_em') or l['iniciado_em'] for l in banco.tabelas['ingestoes']),
                         default=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    erros, avisos = banco.validar()
    erros_regras, info = normativo.conferir_todas(banco.tabelas['regras'])
    if erros or erros_regras:
        # não publica dados inconsistentes; mantém a versão anterior e devolve o motivo
        return {'publicado': False, 'erros': (erros + erros_regras)[:50]}
    # gera numa pasta temporária e troca de uma vez: uma falha no meio não deixa a
    # publicação pela metade nem apaga a versão anterior
    tmp = OUT + '.novo'
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    DESTINO['pasta'] = tmp
    try:
        pub = Publicador(banco, info, agora)
        indice = pub.publicar(com_fixtures)
        pub.admin(erros, avisos, erros_regras)
    finally:
        DESTINO['pasta'] = OUT
    # troca arquivo por arquivo (não a pasta inteira): renomear diretórios dentro de uma
    # pasta sincronizada pelo sistema (Área de Trabalho no iCloud) gera cópias "nome 2"
    novos = set()
    for base, _, arqs in os.walk(tmp):
        for n in arqs:
            rel = os.path.relpath(os.path.join(base, n), tmp)
            novos.add(rel)
            dest = os.path.join(OUT, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if not (os.path.exists(dest) and open(dest, 'rb').read() == open(os.path.join(base, n), 'rb').read()):
                os.replace(os.path.join(base, n), dest)
    for base, _, arqs in os.walk(OUT):
        for n in arqs:
            if os.path.relpath(os.path.join(base, n), OUT) not in novos:
                os.remove(os.path.join(base, n))
    shutil.rmtree(tmp)
    return {'publicado': True, 'eleicoes': len(indice['eleicoes']), 'candidaturas': indice['contagens']['candidaturas'],
            'propostas_publicadas': indice['contagens']['propostas_publicadas'], 'nao_publicadas': sorted(set(pub.nao_publicadas)),
            'avisos': avisos[:20]}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sem-fixtures', action='store_true', help='não publica a eleição de demonstração')
    a = ap.parse_args()
    r = construir(com_fixtures=not a.sem_fixtures)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(0 if r['publicado'] else 1)
