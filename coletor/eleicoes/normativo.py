"""Ponte entre o Mapa Eleitoral e a base do Mapa Normativo.

O Mapa Eleitoral não mantém uma segunda base normativa. Cada fundamento jurídico
(tabela `regras`) aponta para um dispositivo já publicado pelo Mapa Normativo
(`docs/data/diplomas/<diploma>.json`, que é a redação vigente) e, se preciso, para um
localizador dentro dele ("III", "§ 1º", "§ 2º, I", "III, b"). Daqui saem três coisas:

- a verificação de que o dispositivo existe, não foi revogado e contém o localizador;
- o trecho vigente correspondente, copiado da compilação oficial (nunca de memória);
- o hash do artigo, gravado na análise para acusar quando o texto mudar depois dela.
"""
import json, os, re

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIPLOMAS = os.path.join(RAIZ, 'docs', 'data', 'diplomas')
ROMANO = re.compile(r'^[IVXLCDM]+$')
_cache = {}


def diploma(did, pasta=DIPLOMAS):
    chave = (pasta, did)
    if chave not in _cache:
        cam = os.path.join(pasta, did + '.json')
        _cache[chave] = json.load(open(cam, encoding='utf-8')) if os.path.exists(cam) else None
    return _cache[chave]


def artigo(dispositivo, pasta=DIPLOMAS):
    did, _, num = dispositivo.partition('.')
    d = diploma(did, pasta)
    return (d, d['artigos'].get(num)) if d else (None, None)


def _norm(s):
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()


def _nivel(linha):
    """Nível estrutural de uma linha do artigo: 'par', 'inc', 'ali' ou None."""
    t = _norm(linha)
    if t.startswith('§') or t.lower().startswith('parágrafo único'):
        return 'par'
    if re.match(r'^[IVXLCDM]+\s*(?:[-–.]|\s)', t):
        return 'inc'
    if re.match(r'^[a-z]\)', t):
        return 'ali'
    return None


def _casa(linha, parte):
    t = _norm(linha)
    p = _norm(parte)
    if p.lower() == 'parágrafo único':
        return t.lower().startswith('parágrafo único')
    if p.startswith('§'):
        num = re.sub(r'[^\dA-Z-]', '', p[1:].replace('º', '').replace('°', ''))
        m = re.match(r'^§\s*(\d+(?:-[A-Z])?)\s*[º°o]?', t)
        return bool(m) and m.group(1) == num
    if ROMANO.match(p):
        return bool(re.match(r'^' + p + r'(?:\s*[-–.]|\s)', t))
    if re.match(r'^[a-z]$', p):
        return t.startswith(p + ')')
    return False


def localizar(art, localizador):
    """Índices das linhas do artigo que correspondem ao localizador, ou None.

    "caput" ou vazio devolve a primeira linha. Cada parte procura a partir da anterior e
    não atravessa um marcador de nível igual ou superior ao da parte anterior."""
    linhas = [l[0] for l in art['l']]
    if not localizador or localizador.strip().lower() == 'caput':
        return [0]
    partes = [p.strip() for p in localizador.split(',') if p.strip()]
    ordem = {'par': 0, 'inc': 1, 'ali': 2}
    ini, limite_nivel, achado = 1, None, None
    for p in partes:
        nivel_p = 'par' if (p.startswith('§') or p.lower() == 'parágrafo único') else 'inc' if ROMANO.match(p) else 'ali'
        achado = None
        for i in range(ini, len(linhas)):
            n = _nivel(linhas[i])
            if n == nivel_p and _casa(linhas[i], p):
                achado = i; break
            if limite_nivel is not None and n is not None and ordem[n] <= ordem[limite_nivel]:
                break  # saiu do parágrafo ou inciso da parte anterior
        if achado is None:
            return None
        ini, limite_nivel = achado + 1, nivel_p
    # o trecho vai da linha achada até o próximo marcador de nível igual ou superior
    fim = achado + 1
    while fim < len(linhas):
        n = _nivel(linhas[fim])
        if n is not None and ordem[n] <= ordem[limite_nivel]:
            break
        fim += 1
    return list(range(achado, fim))


def conferir_regra(r, pasta=DIPLOMAS):
    """Confere uma regra contra a base. Devolve (erros, informações publicáveis)."""
    if r.get('fora_da_base'):
        return [], {'fora_da_base': True}
    d, a = artigo(r['dispositivo'], pasta)
    if d is None:
        return [f'regras.{r["id"]}: diploma "{r["dispositivo"].split(".")[0]}" não está publicado no Mapa Normativo'], {}
    if a is None:
        return [f'regras.{r["id"]}: dispositivo {r["dispositivo"]} não existe na redação vigente'], {}
    if r['diploma_id'] != d['id']:
        return [f'regras.{r["id"]}: diploma_id "{r["diploma_id"]}" não confere com o dispositivo {r["dispositivo"]}'], {}
    erros = []
    if a.get('rev'):
        erros.append(f'regras.{r["id"]}: {r["dispositivo"]} está revogado na compilação oficial')
    idx = localizar(a, r.get('localizador'))
    if idx is None:
        erros.append(f'regras.{r["id"]}: localizador "{r.get("localizador")}" não encontrado no texto vigente de {r["dispositivo"]}')
        idx = []
    info = {'hash': a['hash'], 'rotulo_artigo': a['r'], 'diploma': d['sigla'], 'diploma_nome': d['nome'],
            'url_oficial': d['url'], 'verificado_em': d.get('verificado_em'),
            'trecho_vigente': [a['l'][i][0] for i in idx][:12], 'caput': a['l'][0][0] if a['l'] else ''}
    return erros, info


def conferir_todas(regras, pasta=DIPLOMAS):
    erros, info = [], {}
    for r in regras:
        e, i = conferir_regra(r, pasta)
        erros.extend(e)
        info[r['id']] = i
    return erros, info
