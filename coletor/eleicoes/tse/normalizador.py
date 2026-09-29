"""Normalizador: converte os itens brutos do TSE nas entidades do esquema.

Só campos da lista branca chegam ao repositório. Os nomes oficiais (em maiúsculas,
como o TSE publica) são preservados em `nome_urna_oficial`; `nome_urna` é a forma de
exibição. Situações desconhecidas viram OUTRO e geram aviso, em vez de sumir.
"""
import os, re, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cliente  # noqa: E402

PARTICULAS = {'da', 'de', 'do', 'das', 'dos', 'e', 'di', 'du', 'del', 'van', 'von'}
PUBLICADOR = 'Tribunal Superior Eleitoral'


def sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', sem_acento(s).lower()).strip('-')


SITUACOES = {
    'deferido': 'DEFERIDO', 'deferido com recurso': 'DEFERIDO_COM_RECURSO', 'indeferido': 'INDEFERIDO',
    'indeferido com recurso': 'INDEFERIDO_COM_RECURSO',
    'indeferido em prazo recursal ou com recurso': 'INDEFERIDO_COM_RECURSO', 'aguardando julgamento': 'AGUARDANDO_JULGAMENTO',
    'pendente de julgamento': 'AGUARDANDO_JULGAMENTO', 'cancelado': 'CANCELADO', 'cancelado com recurso': 'CANCELADO',
    'cassado': 'CASSADO', 'cassado com recurso': 'CASSADO', 'renuncia': 'RENUNCIA', 'falecido': 'FALECIDO',
    'nao conhecimento do pedido': 'NAO_CONHECIDO', 'pedido nao conhecido': 'NAO_CONHECIDO',
}


def situacao(texto):
    """(enum, reconhecida?)."""
    chave = re.sub(r'\s+', ' ', sem_acento(texto or '').lower()).strip()
    if chave in SITUACOES:
        return SITUACOES[chave], True
    return 'OUTRO', False


def nome_exibicao(nome, siglas=()):
    """Maiúsculas do TSE para forma de exibição: partículas em minúsculas, sigla de
    partido preservada quando vem depois de "do" ou "da" ("Bruno Pedreiro do PCO")."""
    siglas = {s.upper() for s in siglas if s}
    out = []
    palavras = (nome or '').split()
    for i, p in enumerate(palavras):
        ant = palavras[i - 1].lower() if i else ''
        if p.upper() in siglas and ant in ('do', 'da'):
            out.append(p.upper()); continue
        if i and p.lower() in PARTICULAS:
            out.append(p.lower()); continue
        partes = re.split(r"([-'’])", p.lower())
        out.append(''.join(x[:1].upper() + x[1:] if x not in "-'’" else x for x in partes))
    return ' '.join(out)


def id_partido(sigla):
    return 'partido-' + slug(sigla)


def fonte_lista(snap, rotulo_cargo, rotulo_ente):
    cod = snap['url'].rstrip('/').split('/')
    return {'id': 'tse-lista-' + '-'.join(cod[-5:-1]).lower(), 'titulo': f'Candidaturas a {rotulo_cargo} ({rotulo_ente}), DivulgaCandContas',
            'publicador': PUBLICADOR, 'url': snap['url'], 'tipo': 'TSE', 'acessado_em': snap['capturado_em'],
            'descricao': 'Lista oficial de candidaturas do cargo na API pública do DivulgaCandContas.',
            'sha256': snap.get('sha256'), 'snapshot': 'estado/eleicoes/tse/snapshots/' + cliente.nome_snapshot(snap['url']),
            'origem_dado': 'OFFICIAL'}


def fonte_candidatura(det_snap, c, ano, uf, eleicao, nome):
    return {'id': f'tse-candidatura-{c["id"]}', 'titulo': f'Ficha de candidatura de {nome}, DivulgaCandContas',
            'publicador': PUBLICADOR, 'tipo': 'TSE', 'acessado_em': det_snap['capturado_em'],
            'url': cliente.PAGINA_CANDIDATO.format(regiao=cliente.REGIAO.get(uf, 'BR'), uf=uf, eleicao=eleicao, id=c['id'], ano=ano),
            'descricao': 'Dados de registro publicados pelo TSE; a resposta da API consultada está no snapshot.',
            'sha256': det_snap.get('sha256'), 'snapshot': 'estado/eleicoes/tse/snapshots/' + cliente.nome_snapshot(det_snap['url']),
            'origem_dado': 'OFFICIAL'}


def fonte_proposta_governo(arq, det_snap, nome):
    return {'id': f'tse-documento-{arq["idArquivo"]}', 'titulo': f'Proposta de Governo registrada por {nome} ({arq.get("nome") or "PDF"})',
            'publicador': PUBLICADOR, 'autor': nome, 'tipo': 'CANDIDATE_DOCUMENT', 'acessado_em': det_snap['capturado_em'],
            'url': cliente.DOCUMENTO.format(id_arquivo=arq['idArquivo']),
            'descricao': 'Documento apresentado pela candidatura no registro e publicado pelo TSE. O conteúdo ainda não foi processado pelo Mapa Eleitoral.',
            'origem_dado': 'OFFICIAL'}


def normalizar(item, detalhe, det_snap, ctx, siglas=()):
    """item: registro da lista; detalhe: registro de detalhe ou None. ctx: eleicao_id,
    cargo_id, cargo_eleicao_id, ente, ano, uf, tse_eleicao, fonte_lista_id.
    Devolve (candidato, candidatura, partido, fontes, avisos)."""
    c = dict(item)
    if detalhe:
        c.update({k: v for k, v in detalhe.items() if v is not None})
    avisos = []
    sit, ok = situacao(c.get('descricaoSituacao'))
    if not ok:
        avisos.append(f'candidatura {c["id"]}: situação "{c.get("descricaoSituacao")}" não mapeada; registrada como OUTRO')
    partido = c.get('partido') or {}
    sigla = (partido.get('sigla') or '').strip()
    nome = nome_exibicao(c['nomeUrna'], siglas)
    fontes = []
    fonte_id = ctx['fonte_lista_id']
    if detalhe and det_snap:
        f = fonte_candidatura(det_snap, c, ctx['ano'], ctx['uf'], ctx['tse_eleicao'], nome)
        fontes.append(f); fonte_id = f['id']
    prop_id = None
    for a in (c.get('arquivos') or []) if detalhe else []:
        if str(a.get('codTipo')) == cliente.COD_PROPOSTA_GOVERNO and a.get('idArquivo'):
            f = fonte_proposta_governo(a, det_snap, nome); fontes.append(f); prop_id = prop_id or f['id']
    natural = None
    if c.get('nomeMunicipioNascimento'):
        natural = nome_exibicao(c['nomeMunicipioNascimento']) + (f'/{c["sgUfNascimento"]}' if c.get('sgUfNascimento') else '')
    cid = f'tse-{c["id"]}'
    candidato = {'id': 'pessoa-' + cid, 'nome_urna': nome, 'nome_urna_oficial': c['nomeUrna'],
                 'nome_completo': c.get('nomeCompleto'), 'ocupacao': c.get('ocupacao'), 'grau_instrucao': c.get('grauInstrucao'),
                 'naturalidade': natural, 'fonte_id': fonte_id, 'origem_dado': 'OFFICIAL'}
    vices = [{'nome_urna': nome_exibicao(v.get('nm_URNA'), siglas), 'cargo': v.get('ds_CARGO'), 'partido': v.get('sg_PARTIDO')}
             for v in (c.get('vices') or []) if detalhe and v.get('nm_URNA')]
    candidatura = {'id': cid, 'candidato_id': candidato['id'], 'eleicao_id': ctx['eleicao_id'], 'cargo_id': ctx['cargo_id'],
                   'cargo_eleicao_id': ctx['cargo_eleicao_id'], 'ente': ctx['ente'],
                   'partido_id': id_partido(sigla) if sigla else None, 'numero': int(c['numero']),
                   'situacao': sit, 'situacao_oficial': c.get('descricaoSituacao'), 'totalizacao_oficial': c.get('descricaoTotalizacao'),
                   'coligacao': c.get('nomeColigacao') if c.get('nomeColigacao') != sigla else None,
                   'composicao_coligacao': c.get('composicaoColigacao') if c.get('composicaoColigacao') not in (None, '**') else None,
                   'reeleicao': c.get('st_REELEICAO'), 'apta': c.get('candidatoApto'),
                   'foto_url': c.get('fotoUrl') if c.get('fotoUrlPublicavel') else None,
                   'tse_sq': str(c['id']), 'tse_processo': c.get('numeroProcesso'), 'fonte_id': fonte_id,
                   'proposta_governo_fonte_id': prop_id, 'detalhada': bool(detalhe), 'vices': vices or None,
                   'origem_dado': 'OFFICIAL'}
    part = None
    if sigla:
        part = {'id': id_partido(sigla), 'sigla': sigla, 'origem_dado': 'OFFICIAL', 'fonte_id': fonte_id,
                'nome': nome_exibicao(partido.get('nome')) if partido.get('nome') else None,
                'numero': partido.get('numero') or None}
    return candidato, candidatura, part, fontes, avisos
