"""Gera os arquivos publicados em docs/data a partir do cache oficial, do estado e do conteúdo analítico."""
import json, os, re, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import planalto
from fontes import DIPLOMAS

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE, OUT = os.path.join(RAIZ, '.cache'), os.path.join(RAIZ, 'docs', 'data')
J = lambda p: json.load(open(os.path.join(RAIZ, p)))


def ler(p, padrao):
    try:
        return J(p)
    except FileNotFoundError:
        return padrao


def salvar(nome, obj):
    caminho = os.path.join(OUT, nome)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'w') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))


def primeira(a):
    return re.sub(r'^Art\.\s*[\d\.\-A-Zº°o]+\s*[\.\-–]?\s*', '', (a['l'][0] if a['l'] else [''])[0])


CIT = re.compile(r'arts?\.\s*(\d{1,4}(?:\.\d{3})?(?:-[A-Z])?)[^;.]{0,40}?\b(do|da)\s+(CTN|CPC|CC|LEF|C[óo]digo Tribut[áa]rio Nacional|C[óo]digo de Processo Civil|C[óo]digo Civil|Lei n\.?º?\s*6\.830/80|Constitui[çc][ãa]o Federal|CF)', re.I)
SIG = {'ctn': 'ctn', 'código tributário nacional': 'ctn', 'codigo tributario nacional': 'ctn', 'cpc': 'cpc', 'código de processo civil': 'cpc',
       'codigo de processo civil': 'cpc', 'cc': 'cc', 'código civil': 'cc', 'codigo civil': 'cc', 'lef': 'lef', 'cf': 'cf', 'constituição federal': 'cf', 'constituicao federal': 'cf'}


def citacoes(texto, existentes):
    """Liga automaticamente precedentes novos aos dispositivos citados na questão ou na tese."""
    out = []
    for m in CIT.finditer(texto or ''):
        dip = SIG.get(m.group(3).lower(), 'lef' if '6.830' in m.group(3) else None)
        if not dip:
            continue
        num = m.group(1).replace('.', '')
        did = f'{dip}.{num}'
        if did in existentes and did not in out:
            out.append(did)
    return out


def construir(agora=None):
    agora = agora or datetime.now(timezone.utc).isoformat(timespec='seconds')
    avisos, diplomas, refs, busca, alterados = [], [], {}, [], []
    todos_ids = set()
    extraidos = {}
    for f in DIPLOMAS:
        cam = os.path.join(CACHE, f['cache'] + '.htm')
        pub = os.path.join(OUT, 'diplomas', f['id'] + '.json')
        if os.path.exists(cam):
            arts = planalto.extrair(cam, f)
        elif os.path.exists(pub):
            arts = json.load(open(pub))['artigos']
            avisos.append(f"Fonte indisponível nesta execução, mantida a última versão publicada: {f['id']}")
        else:
            avisos.append(f"Diploma sem fonte nem versão publicada: {f['id']}"); continue
        extraidos[f['id']] = arts
        for n in arts:
            todos_ids.add(f"{f['id']}.{n}")
    hashes = ler('estado/hashes.json', {})
    for f in DIPLOMAS:
        arts = extraidos.get(f['id'])
        if arts is None:
            continue
        ordem = sorted(arts, key=lambda x: (int(x.split('-')[0]), x))
        meta = {k: f[k] for k in ('id', 'sigla', 'nome', 'norma', 'area', 'url', 'urn', 'onda')}
        meta.update({'completo': not f.get('sel'), 'n': len(arts), 'verificado_em': hashes.get('_verificado', {}).get(f['id'], agora)})
        salvar(f"diplomas/{f['id']}.json", dict(meta, artigos=arts, ordem=ordem))
        diplomas.append(meta)
        ano = datetime.now().year
        for n in ordem:
            a = arts[n]; did = f"{f['id']}.{n}"
            busca.append([did, a['r'], primeira(a)[:180], 1 if a['rev'] else 0])
            if any(str(ano) in (l[1] or '') for l in a['l']):
                nota = next(l[1] for l in a['l'] if str(ano) in (l[1] or ''))
                alterados.append({'d': did, 'rotulo': f"{f['sigla']}, {a['r']}", 'norma': nota})
    institutos = J('conteudo/institutos.json')
    alertas = J('conteudo/alertas.json')
    comps = J('conteudo/comparacoes.json')
    rel = J('conteudo/relacoes.json')
    auto = ler('conteudo/relacoes_auto.json', [])
    rel['arestas'] = rel['arestas'] + [e for e in auto if e['de'] in todos_ids and e['para'] in todos_ids]
    prec = ler('estado/precedentes.json', {})
    # vínculos de institutos
    for p in prec.values():
        p['institutos'] = []
    for ins in institutos:
        for pid in ins.get('precedentes', []):
            if pid in prec:
                prec[pid]['institutos'].append(ins['id'])
            else:
                avisos.append(f"Precedente citado sem cadastro: {pid} ({ins['id']})")
    por_id = {i['id']: i for i in institutos}
    for p in prec.values():
        for iid in p.get('institutos_auto', []):
            if iid in por_id and p['id'] not in por_id[iid]['precedentes']:
                por_id[iid]['precedentes'].append(p['id']); p['institutos'].append(iid)
    for p in prec.values():
        if not p.get('dispositivos'):
            p['dispositivos'] = citacoes((p.get('questao') or '') + ' ' + (p.get('tese') or ''), todos_ids)
    # referências usadas pelo conteúdo, para a página não precisar abrir todos os diplomas
    usados = set()
    for ins in institutos:
        usados |= {x['d'] for x in ins['fundamentos']} | {c.get('d') for c in ins.get('cadeia', []) if c.get('d')}
        usados |= {c['f'] for c in ins['checklist']}
        for lado in ('fazenda', 'defesa'):
            for a in ins['pratica'][lado]:
                usados |= set(a['refs'])
        for c in ins['controversias']:
            for pos in c['posicoes']:
                usados |= set(pos['refs'])
    for e in rel['arestas']:
        usados |= {e['de'], e['para']}
    for a in alertas:
        usados |= {a['a'], a['b']}
    for p in prec.values():
        usados |= set(p['dispositivos'])
    for did in sorted(usados):
        k, _, n = did.partition('.')
        a = extraidos.get(k, {}).get(n)
        if a:
            refs[did] = {'r': a['r'], 's': next(d['sigla'] for d in diplomas if d['id'] == k), 'fl': primeira(a)[:160],
                         'alt': any(str(datetime.now().year) in (l[1] or '') for l in a['l']), 'rev': a['rev']}
        elif not did.startswith(('stj.', 'stf.', 'tst.')):
            avisos.append(f'Dispositivo referenciado fora da base: {did}')
    idx = {
        'gerado_em': agora, 'versao': 2,
        'taxonomia': J('conteudo/taxonomia.json'), 'alteradoras': J('conteudo/alteradoras.json'),
        'diplomas': diplomas, 'institutos': institutos, 'alertas': alertas, 'comparacoes': comps,
        'relacoes': rel, 'precedentes': prec, 'refs': refs, 'alterados_ano': alterados,
        'changelog': ler('estado/changelog.json', [])[-80:], 'pendencias': ler('estado/pendencias.json', []),
        'dou': ler('estado/dou.json', [])[-60:], 'execucao': ler('estado/ultima_execucao.json', {}),
        'fontes': ler('estado/fontes_status.json', {}), 'avisos': avisos,
    }
    salvar('index.json', idx)
    salvar('busca.json', busca)
    return idx


if __name__ == '__main__':
    i = construir()
    print(len(i['diplomas']), 'diplomas;', sum(d['n'] for d in i['diplomas']), 'artigos;', len(i['precedentes']), 'precedentes;', len(i['avisos']), 'avisos')
    for a in i['avisos'][:20]:
        print(' -', a)
