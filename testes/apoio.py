"""Apoio aos testes do Mapa Eleitoral: raiz temporária com o conteúdo curado real e
snapshots sintéticos, para testar o pipeline sem tocar em estado/ nem em docs/."""
import json, os, shutil, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('coletor', 'coletor/eleicoes', 'coletor/eleicoes/tse'):
    sys.path.insert(0, os.path.join(RAIZ, p))

import repositorio  # noqa: E402
import cliente  # noqa: E402

AGORA = '2026-09-29T12:00:00+00:00'
DEPOIS = '2026-09-30T12:00:00+00:00'


def raiz_temporaria(com_fixtures=True):
    tmp = tempfile.mkdtemp(prefix='mapa-eleitoral-')
    origem = os.path.join(RAIZ, 'conteudo', 'eleicoes')
    destino = os.path.join(tmp, 'conteudo', 'eleicoes')
    shutil.copytree(origem, destino)
    if not com_fixtures:
        shutil.rmtree(os.path.join(destino, 'fixtures'))
    os.makedirs(os.path.join(tmp, 'estado', 'eleicoes'))
    json.dump({'versao': repositorio.VERSAO_ESQUEMA}, open(os.path.join(tmp, 'estado', 'eleicoes', '_esquema.json'), 'w'))
    # afirmação de vagas do Senado, que em produção vem de legislativo.py
    est = os.path.join(tmp, 'estado', 'eleicoes')
    json.dump([{'id': 'senado-teste', 'titulo': 'Senado (teste)', 'publicador': 'Senado Federal', 'url': 'https://legis.senado.leg.br/x',
                'tipo': 'LEGISLATIVE_RECORD', 'acessado_em': AGORA, 'origem_dado': 'OFFICIAL'}], open(os.path.join(est, 'fontes.json'), 'w'))
    json.dump([{'id': 'vagas-2026-senado-sc', 'tipo': 'COMPUTED', 'texto': 'Duas vagas (teste).', 'status_revisao': 'AUTO_GENERATED',
                'valor': {'vagas': 2}, 'criado_em': AGORA, 'atualizado_em': AGORA, 'origem_dado': 'DERIVED'}], open(os.path.join(est, 'afirmacoes.json'), 'w'))
    json.dump([{'id': 'vagas-teste', 'afirmacao_id': 'vagas-2026-senado-sc', 'fonte_id': 'senado-teste', 'relacao': 'SUPPORTS'}],
              open(os.path.join(est, 'afirmacao_fontes.json'), 'w'))
    return tmp


def item_lista(sq, numero, nome, situacao='Deferido', sigla='PX', completo=None):
    return {'id': sq, 'nomeUrna': nome, 'numero': numero, 'nomeCompleto': completo or nome, 'descricaoSituacao': situacao,
            'descricaoTotalizacao': 'Concorrendo', 'nomeColigacao': sigla, 'partido': {'sigla': sigla}, 'st_REELEICAO': False,
            'candidatoApto': True, 'ufCandidatura': 'SC'}


def gravar_snapshots(pasta, por_cargo, eleicao='20322002026', ano=2026, detalhes=None):
    """por_cargo: {(uf, codigo_cargo): [itens]}; detalhes: {sq: dict de detalhe}. Cargos sem
    itens recebem lista vazia, para que a sincronização encontre resposta em todos."""
    os.makedirs(pasta, exist_ok=True)
    for uf, cod in (('BR', 1), ('SC', 3), ('SC', 5), ('SC', 6), ('SC', 7)):
        itens = por_cargo.get((uf, cod), [])
        url = cliente.LISTAR.format(ano=ano, uf=uf, eleicao=eleicao, cargo=cod)
        cliente.gravar_snapshot({'url': url, 'capturado_em': AGORA, 'http_status': 200, 'sha256': 'x' * 64, 'bytes': 1,
                                 'via': 'teste', 'corpo': {'candidatos': itens}}, pasta)
    for sq, d in (detalhes or {}).items():
        uf = 'BR' if str(d.get('cargo', {}).get('codigo')) == '1' else 'SC'
        url = cliente.BUSCAR.format(ano=ano, uf=uf, eleicao=eleicao, id=sq)
        cliente.gravar_snapshot({'url': url, 'capturado_em': AGORA, 'http_status': 200, 'sha256': 'y' * 64, 'bytes': 1,
                                 'via': 'teste', 'corpo': d}, pasta)
