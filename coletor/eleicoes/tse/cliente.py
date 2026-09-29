"""Cliente do TSE: busca as respostas oficiais e as guarda como snapshots auditáveis.

Fonte: API pública do DivulgaCandContas (divulgacandcontas.tse.jus.br), a mesma que
alimenta a consulta oficial de candidaturas, em JSON. O Portal de Dados Abertos do TSE
(dadosabertos.tse.jus.br) publica os mesmos dados em CSV compactado (consulta_cand_<ano>
.zip), preparado para uma futura carga completa; os endereços estão em DADOS_ABERTOS.

Dois transportes, com a mesma saída:

- TransporteHTTP: requisição direta (curl, como os demais coletores do projeto).
  O TSE recusa, com HTTP 403 do Akamai, requisições deste computador e de parte dos
  ambientes de nuvem; quando isso ocorre, o erro vai para o log de ingestão.
- TransporteSnapshot: lê respostas já capturadas em estado/eleicoes/tse/snapshots/,
  gravadas por uma coleta anterior ou pela importação de uma captura feita no
  navegador (importar_captura.py). Permite reprocessar tudo sem nova requisição.

Snapshot: {url, capturado_em, http_status, sha256, bytes, via, campos_selecionados,
corpo}. `sha256` e `bytes` são os da resposta original, calculados no momento da
captura; o corpo guardado é o original ou a seleção de campos documentada em
`campos_selecionados` (dados pessoais sensíveis nunca são gravados).
"""
import hashlib, json, os, subprocess
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SNAPSHOTS = os.path.join(RAIZ, 'estado', 'eleicoes', 'tse', 'snapshots')

API = 'https://divulgacandcontas.tse.jus.br/divulga/rest/v1'
LISTAR = API + '/candidatura/listar/{ano}/{uf}/{eleicao}/{cargo}/candidatos'
BUSCAR = API + '/candidatura/buscar/{ano}/{uf}/{eleicao}/candidato/{id}'
# Endereços públicos derivados da consulta oficial (conferidos no código do DivulgaCand):
PAGINA_CANDIDATO = 'https://divulgacandcontas.tse.jus.br/divulga/#/candidato/{regiao}/{uf}/{eleicao}/{id}/{ano}/{uf}'
DOCUMENTO = 'https://divulgacandcontas.tse.jus.br/divulga/rest/arquivo/doc/{id_arquivo}'
COD_PROPOSTA_GOVERNO = '5'  # codTipo do arquivo "Proposta de Governo" no DivulgaCand
REGIAO = {'BR': 'BR', 'SC': 'SUL', 'PR': 'SUL', 'RS': 'SUL'}

DADOS_ABERTOS = {
    'pacote': 'https://dadosabertos.tse.jus.br/dataset/candidatos-{ano}',
    'candidatos': 'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip',
    'vagas': 'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_{ano}.zip',
    'propostas': 'https://cdn.tse.jus.br/estatistica/sead/odsele/proposta_governo/proposta_governo_{ano}_{uf}.zip',
}

# Campos da resposta de detalhe que o projeto aproveita. Todo o resto é descartado na
# captura; CPF, título de eleitor, data de nascimento, gênero, cor ou raça, estado civil,
# e-mails, bens e certidões nunca são gravados (minimização de dados pessoais).
CAMPOS_DETALHE = ['id', 'nomeUrna', 'nomeCompleto', 'numero', 'partido', 'cargo', 'ufCandidatura', 'descricaoSituacao',
                  'descricaoTotalizacao', 'nomeColigacao', 'composicaoColigacao', 'descricaoTipoDrap', 'grauInstrucao',
                  'ocupacao', 'nomeMunicipioNascimento', 'sgUfNascimento', 'st_REELEICAO', 'candidatoApto', 'fotoUrl',
                  'fotoUrlPublicavel', 'dataUltimaAtualizacao', 'numeroProcesso', 'arquivos (só Proposta de Governo)',
                  'vices (nome, cargo, partido, número)']
CAMPOS_LISTA = ['id', 'nomeUrna', 'numero', 'nomeCompleto', 'descricaoSituacao', 'descricaoTotalizacao',
                'nomeColigacao', 'partido.sigla', 'st_REELEICAO', 'candidatoApto', 'ufCandidatura']


class ErroTransporte(Exception):
    pass


def _pega(d, caminho):
    for k in caminho.split('.'):
        d = (d or {}).get(k)
    return d


def reduzir_candidato_lista(c):
    out = {k: c.get(k) for k in CAMPOS_LISTA if '.' not in k}
    out['partido'] = {'sigla': _pega(c, 'partido.sigla')}
    return out


def reduzir_candidato_detalhe(j):
    out = {k: j.get(k) for k in CAMPOS_DETALHE if ' ' not in k and k not in ('partido', 'cargo')}
    p, c = j.get('partido') or {}, j.get('cargo') or {}
    out['partido'] = {'numero': p.get('numero'), 'sigla': p.get('sigla'), 'nome': p.get('nome')}
    out['cargo'] = {'codigo': c.get('codigo'), 'nome': c.get('nome')}
    out['arquivos'] = [{'idArquivo': a.get('idArquivo'), 'nome': a.get('nome'), 'codTipo': str(a.get('codTipo'))}
                       for a in (j.get('arquivos') or []) if str(a.get('codTipo')) == COD_PROPOSTA_GOVERNO]
    out['vices'] = [{'sq_CANDIDATO': v.get('sq_CANDIDATO'), 'nm_URNA': v.get('nm_URNA'), 'ds_CARGO': v.get('ds_CARGO'),
                     'sg_PARTIDO': v.get('sg_PARTIDO'), 'nr_CANDIDATO': v.get('nr_CANDIDATO')} for v in (j.get('vices') or [])]
    return out


def reduzir(url, dados):
    """Aplica a minimização de dados antes de qualquer gravação. Devolve (corpo, campos)."""
    if '/candidatura/buscar/' in url:
        return reduzir_candidato_detalhe(dados), CAMPOS_DETALHE
    if '/candidatura/listar/' in url:
        return {'unidadeEleitoral': dados.get('unidadeEleitoral'), 'cargo': dados.get('cargo'),
                'candidatos': [reduzir_candidato_lista(c) for c in dados.get('candidatos') or []]}, CAMPOS_LISTA
    return dados, None


def agora():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def nome_snapshot(url):
    """Nome de arquivo estável a partir do endereço consultado."""
    parte = url.split('/rest/v1/', 1)[-1]
    return parte.replace('/', '_') + '.json'


class TransporteHTTP:
    nome = 'http'

    def __init__(self, gravar=True, timeout=60):
        self.gravar, self.timeout = gravar, timeout

    def obter(self, url):
        r = subprocess.run(['curl', '-sS', '-L', '--max-time', str(self.timeout), '-A', 'Mozilla/5.0',
                            '-H', 'Accept: application/json', '-w', '\n%{http_code}', url], capture_output=True)
        if r.returncode != 0:
            raise ErroTransporte(f'{url}: falha de conexão ({r.stderr.decode("utf-8", "replace").strip()[:160]})')
        corpo, _, status = r.stdout.rpartition(b'\n')
        status = int(status or 0)
        if status != 200:
            raise ErroTransporte(f'{url}: HTTP {status}')
        try:
            dados = json.loads(corpo.decode('utf-8'))
        except ValueError:
            raise ErroTransporte(f'{url}: resposta não é JSON')
        reduzido, campos = reduzir(url, dados)
        snap = {'url': url, 'capturado_em': agora(), 'http_status': status, 'sha256': hashlib.sha256(corpo).hexdigest(),
                'bytes': len(corpo), 'via': 'TransporteHTTP (curl)', 'campos_selecionados': campos, 'corpo': reduzido}
        if self.gravar:
            gravar_snapshot(snap)
        return snap


class TransporteSnapshot:
    nome = 'snapshot'

    def __init__(self, pasta=SNAPSHOTS):
        self.pasta = pasta

    def obter(self, url):
        cam = os.path.join(self.pasta, nome_snapshot(url))
        if not os.path.exists(cam):
            raise ErroTransporte(f'{url}: sem snapshot em {os.path.relpath(cam, RAIZ)}')
        return json.load(open(cam, encoding='utf-8'))


def gravar_snapshot(snap, pasta=SNAPSHOTS):
    os.makedirs(pasta, exist_ok=True)
    cam = os.path.join(pasta, nome_snapshot(snap['url']))
    with open(cam, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
        f.write('\n')
    return cam


class ClienteTSE:
    def __init__(self, transporte):
        self.transporte = transporte

    def listar_candidatos(self, ano, uf, eleicao, cargo):
        return self.transporte.obter(LISTAR.format(ano=ano, uf=uf, eleicao=eleicao, cargo=cargo))

    def buscar_candidato(self, ano, uf, eleicao, sq):
        return self.transporte.obter(BUSCAR.format(ano=ano, uf=uf, eleicao=eleicao, id=sq))
