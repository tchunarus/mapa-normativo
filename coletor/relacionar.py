"""Registra relações propostas pela rotina, com validação.

Uso: python3 coletor/relacionar.py < relacoes.json
Entrada: {"analisados": ["ctn.135", ...], "relacoes": [{"de", "para", "tipo", "grau", "porque"}]}
Recusa ids inexistentes, tipos ou graus fora da lista, justificativas curtas e
duplicatas. Marca os artigos analisados para não voltarem à fila.
"""
import json, os, re, sys
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, EST, CONT = os.path.join(RAIZ, 'docs', 'data'), os.path.join(RAIZ, 'estado'), os.path.join(RAIZ, 'conteudo')


def main():
    entrada = json.load(sys.stdin)
    rel = json.load(open(os.path.join(CONT, 'relacoes.json')))
    auto_p = os.path.join(CONT, 'relacoes_auto.json')
    auto = json.load(open(auto_p)) if os.path.exists(auto_p) else []
    ids = {b[0] for b in json.load(open(os.path.join(DATA, 'busca.json')))}
    textos = {}

    def texto(did):
        if did not in textos:
            k, n = did.split('.', 1)
            try:
                d = json.load(open(os.path.join(DATA, 'diplomas', k + '.json')))
                textos[did] = '\n'.join(l[0] for l in d['artigos'][n]['l'])
            except (OSError, KeyError):
                textos[did] = ''
        return textos[did]

    def referencias_inexistentes(e):
        """Parágrafo único ou § citado na justificativa que não existe no texto vigente do artigo citado."""
        porque = e['porque']
        numeros = {e['de'].split('.', 1)[1].split('-')[0]: e['de'], e['para'].split('.', 1)[1].split('-')[0]: e['para']}
        for m in re.finditer(r'art(?:igo)?\.?\s*(\d{1,4}(?:\.\d{3})?)[^.;]{0,25}?(par[áa]grafo [úu]nico|§\s*\d+)', porque, re.I):
            alvo = numeros.get(m.group(1).replace('.', ''))
            if not alvo:
                continue
            t = texto(alvo)
            ref = m.group(2)
            if ref.lower().startswith('par') and not re.search(r'Par[áa]grafo [úu]nico', t, re.I):
                return f'o art. {m.group(1)} não tem parágrafo único no texto vigente'
            n = re.findall(r'\d+', ref)
            if n and not ref.lower().startswith('par') and not re.search(r'§\s*' + n[0] + r'(?:º|°|o)?\b', t):
                return f'o art. {m.group(1)} não tem § {n[0]} no texto vigente'
        t = texto(e['de']) + '\n' + texto(e['para'])
        if re.search(r'par[áa]grafo [úu]nico', porque, re.I) and not re.search(r'Par[áa]grafo [úu]nico', t, re.I):
            return 'parágrafo único citado não existe no texto vigente'
        for n in re.findall(r'(?:§|par[áa]grafo)\s*(\d+)', porque, re.I):
            if not re.search(r'§\s*' + n + r'(?:º|°|o)?\b', t):
                return f'§ {n} citado não existe no texto vigente'
        return None
    existentes = {(e['de'], e['para']) for e in rel['arestas'] + auto} | {(e['para'], e['de']) for e in rel['arestas'] + auto}
    agora = datetime.now(timezone.utc).isoformat(timespec='seconds')
    aceitas, recusadas = [], []
    for e in entrada.get('relacoes', []):
        motivo = None
        if e.get('de') not in ids or e.get('para') not in ids: motivo = 'dispositivo inexistente'
        elif e['de'].split('.')[0] == e['para'].split('.')[0] and e.get('tipo') != 'remete_a': motivo = 'mesma norma: use apenas remete_a'
        elif e.get('tipo') not in rel['tipos']: motivo = 'tipo inválido'
        elif e.get('grau') not in rel['graus']: motivo = 'grau inválido'
        elif len((e.get('porque') or '').strip()) < 40: motivo = 'justificativa insuficiente'
        elif '—' in e['porque']: motivo = 'travessão no texto'
        elif (e['de'], e['para']) in existentes: motivo = 'relação já registrada'
        elif not re.search(r'[áàâãéêíóôõúç]', e['porque'], re.I): motivo = 'texto sem acentuação'
        elif referencias_inexistentes(e): motivo = referencias_inexistentes(e)
        if motivo:
            recusadas.append({'de': e.get('de'), 'para': e.get('para'), 'motivo': motivo}); continue
        auto.append({'de': e['de'], 'para': e['para'], 'tipo': e['tipo'], 'grau': e['grau'], 'porque': e['porque'].strip(),
                     'refs': [], 'origem': 'rotina', 'em': agora})
        existentes |= {(e['de'], e['para']), (e['para'], e['de'])}
        aceitas.append(f"{e['de']} -> {e['para']}")
    json.dump(auto, open(auto_p, 'w'), ensure_ascii=False, indent=1)
    proc_p = os.path.join(EST, 'relacoes_processados.json')
    proc = set(json.load(open(proc_p))) if os.path.exists(proc_p) else set()
    proc |= {i for i in entrada.get('analisados', []) if i in ids}
    json.dump(sorted(proc), open(proc_p, 'w'), ensure_ascii=False)
    print(json.dumps({'aceitas': len(aceitas), 'recusadas': recusadas, 'processados_total': len(proc)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
