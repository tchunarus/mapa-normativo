"""Importa uma captura feita no navegador para estado/eleicoes/tse/snapshots/.

Quando o TSE recusa requisições diretas (HTTP 403), as respostas da API pública do
DivulgaCandContas podem ser lidas num navegador comum e exportadas como JSON:

    {"listas": {"<UF><cargo>": {url, status, capturado_em, sha256, bytes, cols, rows, ue, cargo}},
     "det": {"<id>": {url, status, capturado_em, sha256, bytes, c: {...campos de detalhe}}}}

`sha256` e `bytes` são os da resposta original, calculados no navegador antes da
seleção de campos. Este script remonta cada resposta no formato de snapshot do
TransporteHTTP e aplica de novo a minimização (cliente.reduzir), de modo que o parser
trate as duas origens da mesma forma.

    python3 coletor/eleicoes/tse/importar_captura.py <arquivo>
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cliente  # noqa: E402

VIA = 'captura no navegador (API pública do DivulgaCandContas), importada por importar_captura.py'


def ler_captura(caminho):
    """Aceita o JSON direto ou a saída da ferramenta de navegador (texto JSON codificado)."""
    bruto = open(caminho, encoding='utf-8').read()
    d = json.loads(bruto)
    if isinstance(d, list) and d and isinstance(d[0], dict) and 'text' in d[0]:
        t = d[0]['text']
        t = t[:t.rfind('"') + 1] if '(captured at origin' in t else t
        d = json.loads(t)
    if isinstance(d, str):
        d = json.loads(d)
    return d


def _desachatar(cols, row):
    out = {}
    for k, v in zip(cols, row):
        if '.' in k:
            a, b = k.split('.', 1)
            out.setdefault(a, {})[b] = v
        else:
            out[k] = v
    return out


def importar(captura, pasta=cliente.SNAPSHOTS):
    gravados = []
    for chave, l in captura.get('listas', {}).items():
        corpo = {'unidadeEleitoral': l.get('ue'), 'cargo': l.get('cargo'),
                 'candidatos': [_desachatar(l['cols'], r) for r in l['rows']]}
        corpo, campos = cliente.reduzir(l['url'], corpo)
        snap = {'url': l['url'], 'capturado_em': l['capturado_em'], 'http_status': l['status'], 'sha256': l['sha256'],
                'bytes': l['bytes'], 'via': VIA, 'campos_selecionados': campos, 'corpo': corpo}
        gravados.append(cliente.gravar_snapshot(snap, pasta))
    for sq, d in captura.get('det', {}).items():
        corpo, campos = cliente.reduzir(d['url'], d['c'])
        snap = {'url': d['url'], 'capturado_em': d['capturado_em'], 'http_status': d['status'], 'sha256': d['sha256'],
                'bytes': d['bytes'], 'via': VIA, 'campos_selecionados': campos, 'corpo': corpo}
        gravados.append(cliente.gravar_snapshot(snap, pasta))
    return gravados


if __name__ == '__main__':
    g = importar(ler_captura(sys.argv[1]))
    print(json.dumps({'snapshots': len(g)}, ensure_ascii=False))
