"""Fila de artigos para mapeamento de relações.

Uso: python3 coletor/fila_relacoes.py --n 10 > fila.json
Devolve os próximos artigos ainda não analisados, cada um com seu texto e até 25
candidatos de outros diplomas, escolhidos por semelhança de vocabulário. A rotina lê
os textos, decide quais relações existem de fato e as registra com relacionar.py.
"""
import argparse, json, math, os, re, unicodedata
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, 'docs', 'data')
EST = os.path.join(RAIZ, 'estado')
PRIORIDADE = ['ctn', 'lef', 'cf', 'lcp214', 'cpc', 'cc', 'lindb', 'ec132', 'adct', 'lcp227']
STOP = set('de da do das dos e em no na nos nas o a os as um uma por para com que se ao aos ou sua seu suas seus art lei nº não como pelo pela pelos pelas este esta deste desta será ser são sobre caso quando inciso paragrafo caput termos disposto previsto'.split())


def toks(s):
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return [w for w in re.findall(r'[a-z]{4,}', s) if w not in STOP]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--n', type=int, default=10); a = ap.parse_args()
    idx = json.load(open(os.path.join(DATA, 'index.json')))
    feitos = set(json.load(open(os.path.join(EST, 'relacoes_processados.json')))) if os.path.exists(os.path.join(EST, 'relacoes_processados.json')) else set()
    ordem_dip = PRIORIDADE + [d['id'] for d in idx['diplomas'] if d['id'] not in PRIORIDADE]
    textos, siglas = {}, {d['id']: d['sigla'] for d in idx['diplomas']}
    for k in ordem_dip:
        p = os.path.join(DATA, 'diplomas', k + '.json')
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        for n in d['ordem']:
            art = d['artigos'][n]
            if not art['rev']:
                textos[f'{k}.{n}'] = '\n'.join(l[0] for l in art['l'])
    # artigos citados pelo conteúdo analítico vêm primeiro
    citados = list(idx.get('refs', {}).keys())
    fila = [i for i in citados if i in textos] + [i for i in textos if i not in citados]
    fila = [i for i in fila if i not in feitos][:a.n]
    df = Counter(); vetores = {}
    for i, t in textos.items():
        c = Counter(toks(t)); vetores[i] = c; df.update(c.keys())
    N = len(textos)
    def peso(c):
        v = {w: (1 + math.log(f)) * math.log(N / (1 + df[w])) for w, f in c.items()}
        nrm = math.sqrt(sum(x * x for x in v.values())) or 1
        return {w: x / nrm for w, x in v.items()}
    pesos = {i: peso(c) for i, c in vetores.items()}
    saida = []
    for i in fila:
        k = i.split('.')[0]; vi = pesos[i]
        cand = []
        for j, vj in pesos.items():
            if j.split('.')[0] == k:
                continue
            s = sum(x * vj.get(w, 0) for w, x in vi.items())
            if s > 0.08:
                cand.append((s, j))
        cand.sort(reverse=True)
        saida.append({'id': i, 'rotulo': f"{siglas[k]}, {i.split('.',1)[1]}", 'texto': textos[i][:3000],
                      'candidatos': [{'id': j, 'rotulo': f"{siglas[j.split('.')[0]]}, art. {j.split('.',1)[1]}", 'texto': textos[j][:600]} for _, j in cand[:25]]})
    print(json.dumps({'tipos': idx['relacoes']['tipos'], 'graus': idx['relacoes']['graus'], 'itens': saida}, ensure_ascii=False))


if __name__ == '__main__':
    main()
