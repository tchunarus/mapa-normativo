"""Registra relações propostas pela rotina, com validação.

Uso: python3 coletor/relacionar.py < relacoes.json
Entrada: {"analisados": ["ctn.135", ...], "relacoes": [{"de", "para", "tipo", "grau", "porque"}]}
Recusa ids inexistentes, tipos ou graus fora da lista, justificativas curtas e
duplicatas. Marca os artigos analisados para não voltarem à fila.
"""
import json, os, sys
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, EST, CONT = os.path.join(RAIZ, 'docs', 'data'), os.path.join(RAIZ, 'estado'), os.path.join(RAIZ, 'conteudo')


def main():
    entrada = json.load(sys.stdin)
    rel = json.load(open(os.path.join(CONT, 'relacoes.json')))
    auto_p = os.path.join(CONT, 'relacoes_auto.json')
    auto = json.load(open(auto_p)) if os.path.exists(auto_p) else []
    ids = {b[0] for b in json.load(open(os.path.join(DATA, 'busca.json')))}
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
