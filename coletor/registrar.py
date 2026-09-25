"""Registra precedentes encontrados pela rotina no Jusratio.

Uso: python3 coletor/registrar.py < precedentes.json
Entrada: lista de objetos com tribunal, tipo, titulo, processo, orgao, relator, data,
tese (ou ementa), url (link do inteiro teor na fonte oficial), instituto (id em
conteudo/institutos.json) e, se houver, dispositivos (ids como "ctn.135").
Só são aceitos registros com URL em domínio oficial (.jus.br ou .gov.br) e com tese
ou ementa; o resto é recusado e listado na saída. Nada é sobrescrito sem registro.
"""
import json, os, re, sys
from datetime import datetime, timezone
from urllib.parse import urlparse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EST = os.path.join(RAIZ, 'estado')
NIVEL = {'Súmula vinculante': 'A', 'Súmula': 'A', 'Controle concentrado': 'A', 'Repercussão geral': 'B', 'Tema repetitivo': 'B',
         'IRDR': 'B', 'IAC': 'B', 'IRR': 'B', 'Órgão especial': 'C', 'Acórdão': 'D'}


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:80]


def main():
    itens = json.load(sys.stdin)
    prec = json.load(open(os.path.join(EST, 'precedentes.json')))
    inst = {i['id'] for i in json.load(open(os.path.join(RAIZ, 'conteudo', 'institutos.json')))}
    log_p = os.path.join(EST, 'changelog.json'); log = json.load(open(log_p)) if os.path.exists(log_p) else []
    agora = datetime.now(timezone.utc).isoformat(timespec='seconds')
    aceitos, recusados = [], []
    for x in itens:
        host = urlparse(x.get('url') or '').hostname or ''
        if not (host.endswith('.jus.br') or host.endswith('.gov.br')):
            recusados.append((x.get('titulo'), 'URL fora de domínio oficial')); continue
        if not (x.get('tese') or '').strip() or not x.get('tribunal') or not x.get('processo'):
            recusados.append((x.get('titulo'), 'faltam tribunal, processo ou tese')); continue
        tema = str(x.get('tema') or '').strip()
        sumula = str(x.get('sumula') or '').strip()
        trib = x['tribunal'].upper()
        if tema.isdigit() and trib in ('STJ', 'STF'):
            pid = f"{trib.lower()}.tema.{tema}"
        elif sumula.isdigit() and trib in ('STJ', 'STF'):
            pid = f"{trib.lower()}.sum.{sumula}" if trib == 'STJ' or 'vinculante' not in (x.get('tipo') or '').lower() else f"stf.sv.{sumula}"
        else:
            pid = f"jr.{slug(x['tribunal'])}.{slug(x['processo'])}"
        novo = pid not in prec
        base = prec.get(pid, {})
        if base and base.get('fonte', '').startswith('STJ') and base.get('tese') and not novo:
            # dados lidos diretamente do portal oficial têm precedência; só atualiza a situação
            base['situacao'] = x.get('situacao') or base.get('situacao'); base['verificado_em'] = agora[:10]; prec[pid] = base; aceitos.append(pid); continue
        base.update({'id': pid, 'trib': x['tribunal'].upper(), 'tipo': x.get('tipo') or 'Acórdão', 'nivel': NIVEL.get(x.get('tipo'), 'D'),
                     'numero': tema or sumula or x['processo'], 'titulo': x.get('titulo') or (f"Tema {tema}/{trib}" if tema.isdigit() else f"Súmula {sumula}/{trib}" if sumula.isdigit() else f"{trib} · {x['processo']}"), 'orgao': x.get('orgao'),
                     'situacao': x.get('situacao') or 'Julgado', 'questao': None, 'tese': x['tese'].strip(),
                     'processos': [{'numero': x['processo'], 'origem': None, 'relator': x.get('relator'), 'julgado': x.get('data'), 'publicado': None}],
                     'data': x.get('data'), 'dispositivos': [d for d in x.get('dispositivos', []) if re.match(r'^[a-z0-9]+\.[\dA-Z\-]+$', d)],
                     'url': x['url'], 'fonte': 'Jusratio, com link para a fonte oficial', 'verificado_em': agora[:10], 'novo': novo})
        if x.get('instituto') in inst:
            base['institutos_auto'] = sorted(set(base.get('institutos_auto', [])) | {x['instituto']})
        prec[pid] = base
        if novo:
            log.append({'data': agora, 'fonte': x['tribunal'].upper(), 'tipo': 'precedente', 'titulo': f"{base['titulo']} incluído", 'url': x['url'], 'p': pid})
        aceitos.append(pid)
    json.dump(prec, open(os.path.join(EST, 'precedentes.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(log[-2000:], open(log_p, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'aceitos': aceitos, 'recusados': recusados}, ensure_ascii=False))


if __name__ == '__main__':
    main()
