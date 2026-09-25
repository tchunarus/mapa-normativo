"""Leitura do Diário Oficial da União (seção 1 e edição extra) pela página oficial de leitura."""
import json, re, subprocess
from fontes import MARCADORES_DOU, TIPOS_DOU, ORGAOS_DOU

URL = 'https://www.in.gov.br/leiturajornal?data={d}&secao={s}'
ATO = 'https://www.in.gov.br/web/dou/-/{slug}'


def edicao(data_br, secao):
    r = subprocess.run(['curl', '-sL', '--max-time', '60', '-A', 'Mozilla/5.0', URL.format(d=data_br, s=secao)], capture_output=True)
    t = r.stdout.decode('utf-8', 'ignore')
    m = re.search(r'<script id="params" type="application/json">(.*?)</script>', t, re.S)
    return json.loads(m.group(1)).get('jsonArray', []) if m else None


def relevantes(atos):
    """Filtra atos normativos que citam diplomas acompanhados."""
    out = []
    for a in atos:
        tipo = a.get('artType') or ''
        orgao = a.get('hierarchyStr') or ''
        if not any(tipo.startswith(x) for x in TIPOS_DOU):
            continue
        if not any(o in orgao for o in ORGAOS_DOU) and not tipo.startswith(('Lei', 'Emenda', 'Medida')):
            continue
        texto = (a.get('title') or '') + ' ' + (a.get('content') or '')
        afeta = [d for d, marcas in MARCADORES_DOU.items() if any(m.lower() in texto.lower() for m in marcas)]
        novo_diploma = tipo.startswith(('Lei Complementar', 'Emenda Constitucional'))
        if afeta or novo_diploma:
            out.append({'titulo': a.get('title'), 'tipo': tipo, 'orgao': orgao, 'data': a.get('pubDate'),
                        'resumo': (a.get('content') or '')[:400], 'url': ATO.format(slug=a.get('urlTitle')),
                        'diplomas': afeta, 'id': a.get('urlTitle')})
    return out
