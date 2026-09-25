"""Fontes do Poder Legislativo: Senado Federal (normas publicadas) e Câmara dos Deputados
(proposições em tramitação que alteram diplomas acompanhados). Ambas por dados abertos oficiais."""
import json, subprocess

SENADO = 'https://legis.senado.leg.br/dadosabertos/legislacao/lista?tipo={t}&ano={a}'
SENADO_NORMA = 'https://legis.senado.leg.br/norma/{id}'
CAMARA = 'https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo={t}&ano={a}&ordem=DESC&ordenarPor=id&itens=100&pagina={p}'
CAMARA_FICHA = 'https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={id}'
TIPOS_NORMA = {'LCP': 'Lei Complementar', 'LEI': 'Lei', 'EMC': 'Emenda Constitucional', 'MPV': 'Medida Provisória', 'DEL': 'Decreto-Lei'}


def _json(url):
    r = subprocess.run(['curl', '-sL', '--max-time', '60', '-A', 'Mozilla/5.0', '-H', 'Accept: application/json', url], capture_output=True)
    try:
        return json.loads(r.stdout.decode('utf-8'))
    except ValueError:
        return None


def normas_senado(ano):
    """Normas federais do ano, por tipo. Devolve None se o serviço não responder."""
    out = []
    for t in TIPOS_NORMA:
        d = _json(SENADO.format(t=t, a=ano))
        if d is None:
            return None
        docs = (((d.get('ListaDocumento') or {}).get('documentos') or {}).get('documento')) or []
        if isinstance(docs, dict):
            docs = [docs]
        for x in docs:
            out.append({'id': f"senado.{x['id']}", 'titulo': f"{TIPOS_NORMA[t]} nº {x['numero']}, de {x.get('dataassinatura','')}",
                        'tipo': TIPOS_NORMA[t], 'numero': x['numero'], 'data': x.get('dataassinatura'), 'ementa': x.get('ementa') or '',
                        'url': SENADO_NORMA.format(id=x['id']), 'fonte': 'Senado Federal, Legislação'})
    return out


def proposicoes_camara(ano, marcadores, paginas=3):
    """Proposições do ano (PL, PLP, PEC, MPV) cujas ementas citam diplomas acompanhados."""
    out = {}
    for t in ('PLP', 'PEC', 'PL', 'MPV'):
        for p in range(1, paginas + 1):
            d = _json(CAMARA.format(t=t, a=ano, p=p))
            if not d or not d.get('dados'):
                break
            for x in d['dados']:
                em = x.get('ementa') or ''
                afeta = [k for k, ms in marcadores.items() if any(m.lower() in em.lower() for m in ms)]
                if afeta:
                    out[str(x['id'])] = {'id': f"camara.{x['id']}", 'titulo': f"{x['siglaTipo']} {x['numero']}/{x['ano']}", 'ementa': em,
                                         'apresentacao': (x.get('dataApresentacao') or '')[:10], 'diplomas': afeta,
                                         'url': CAMARA_FICHA.format(id=x['id']), 'fonte': 'Câmara dos Deputados'}
    return list(out.values())
