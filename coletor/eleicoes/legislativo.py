"""Dados do Poder Legislativo usados pelo Mapa Eleitoral (dados abertos do Senado Federal).

Vagas do Senado em disputa: a representação de cada Estado é renovada alternadamente
por um e dois terços (CF, art. 46, § 2º). O número de cadeiras em disputa numa eleição
é o número de mandatos do Estado que terminam no início da legislatura seguinte, dado
publicado pelo Senado em /dadosabertos/senador/lista/atual. A afirmação resultante é do
tipo COMPUTED e cita as duas fontes (o registro legislativo e a Constituição).

Vagas da Câmara e das Assembleias não são calculadas aqui: dependem da representação
fixada para a eleição (CF, art. 45, § 1º), que pode mudar em relação à legislatura
atual. A fonte correta é o arquivo Vagas do TSE (ainda não acessível a este coletor).

    python3 coletor/eleicoes/legislativo.py [--uf SC] [--ano 2026]
"""
import argparse, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import repositorio  # noqa: E402

SENADO_ATUAL = 'https://legis.senado.leg.br/dadosabertos/senador/lista/atual'


def _json(url):
    r = subprocess.run(['curl', '-sL', '--max-time', '60', '-A', 'Mozilla/5.0', '-H', 'Accept: application/json', url], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None, None
    try:
        return json.loads(r.stdout.decode('utf-8')), hashlib.sha256(r.stdout).hexdigest()
    except ValueError:
        return None, None


def mandatos_que_terminam(dados, uf, fim):
    """Códigos dos mandatos do Estado cuja segunda legislatura termina na data `fim`."""
    ps = (((dados or {}).get('ListaParlamentarEmExercicio') or {}).get('Parlamentares') or {}).get('Parlamentar') or []
    if isinstance(ps, dict):
        ps = [ps]
    cods = set()
    for p in ps:
        m = p.get('Mandato') or {}
        if m.get('UfParlamentar') != uf:
            continue
        seg = m.get('SegundaLegislaturaDoMandato') or {}
        if seg.get('DataFim') == fim:
            cods.add(m.get('CodigoMandato'))
    return sorted(c for c in cods if c)


def sincronizar_vagas_senado(uf='SC', ano=2026, raiz=repositorio.RAIZ, obter=_json, agora=None):
    agora = agora or datetime.now(timezone.utc).isoformat(timespec='seconds')
    banco = repositorio.carregar(raiz)
    log = {'id': f'senado-vagas-{uf.lower()}-{agora}', 'fonte': 'Senado Federal, dados abertos', 'rotulo': 'Senado, vagas em disputa',
           'iniciado_em': agora, 'transporte': 'http', 'fetched': 0, 'created': 0, 'updated': 0, 'unchanged': 0, 'missing': 0,
           'errors': 0, 'erros': [], 'avisos': [], 'snapshots': [], 'origem_dado': 'OFFICIAL'}
    dados, sha = obter(SENADO_ATUAL)
    fim = f'{ano + 1}-01-31'
    cods = mandatos_que_terminam(dados, uf, fim) if dados else []
    if not dados:
        log['erros'].append(f'{SENADO_ATUAL}: sem resposta válida')
    elif not cods:
        log['erros'].append(f'{SENADO_ATUAL}: nenhum mandato de {uf} termina em {fim}; conferir o formato da resposta')
    if not log['erros']:
        log['fetched'] = 1
        log['snapshots'].append({'url': SENADO_ATUAL, 'sha256': sha, 'capturado_em': agora})
        fid = f'senado-senadores-em-exercicio'
        fonte = {'id': fid, 'titulo': 'Senadores em exercício, dados abertos do Senado Federal', 'publicador': 'Senado Federal',
                 'url': SENADO_ATUAL, 'tipo': 'LEGISLATIVE_RECORD', 'acessado_em': agora, 'sha256': sha, 'origem_dado': 'OFFICIAL',
                 'descricao': 'Lista oficial dos parlamentares em exercício, com o período de cada mandato.'}
        aid = f'vagas-{ano}-senado-{uf.lower()}'
        n = len(cods)
        afirm = {'id': aid, 'tipo': 'COMPUTED', 'confianca': 'HIGH', 'status_revisao': 'AUTO_GENERATED', 'valor': {'vagas': n, 'mandatos': cods},
                 'texto': f'Em {ano} estão em disputa {n} das três cadeiras de {uf} no Senado: são os mandatos que terminam em {fim[8:10]}/{fim[5:7]}/{fim[:4]}.',
                 'criado_em': agora, 'atualizado_em': agora, 'origem_dado': 'DERIVED'}
        rel = [{'id': f'{aid}-senado', 'afirmacao_id': aid, 'fonte_id': fid, 'relacao': 'SUPPORTS', 'origem_dado': 'OFFICIAL',
                'localizador': f'mandatos de {uf} com SegundaLegislaturaDoMandato.DataFim = {fim}: ' + ', '.join(cods)},
               {'id': f'{aid}-cf', 'afirmacao_id': aid, 'fonte_id': 'fonte-cf-planalto', 'relacao': 'SUPPORTS',
                'localizador': 'art. 46, §§ 1º e 2º', 'origem_dado': 'OFFICIAL'}]
        for tabela, regs in (('fontes', [fonte]), ('afirmacoes', [afirm]), ('afirmacao_fontes', rel)):
            c, _ = banco.sincronizar(tabela, regs, agora)
            for k in ('created', 'updated', 'unchanged'):
                log[k] += c[k] if tabela == 'afirmacoes' else 0
            banco.gravar(tabela)
    log['errors'] = len(log['erros'])
    log['concluido_em'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    repositorio.registrar_ingestao(banco, log)
    return log


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--uf', default='SC')
    ap.add_argument('--ano', type=int, default=2026)
    a = ap.parse_args()
    lg = sincronizar_vagas_senado(a.uf, a.ano)
    print(json.dumps({k: lg[k] for k in ('rotulo', 'fetched', 'created', 'updated', 'unchanged', 'errors', 'erros')}, ensure_ascii=False))
