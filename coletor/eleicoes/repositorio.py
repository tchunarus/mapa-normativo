"""Repositório do Mapa Eleitoral: carrega, valida e grava as tabelas declaradas em esquema.py.

É a camada que faz as vezes de banco de dados. Toda leitura e toda escrita dos dados
eleitorais passa por aqui, para que as regras de integridade valham igualmente para o
conteúdo curado, para os dados vindos do TSE e para as análises geradas.

Uso de linha de comando (validação completa, a mesma usada pelo hook do projeto):

    python3 coletor/eleicoes/repositorio.py
"""
import hashlib, json, os, re, sys
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))
from esquema import TABELAS, REFERENCIA, VERSAO_ESQUEMA  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(AQUI))
PASTAS = {
    'conteudo': os.path.join('conteudo', 'eleicoes'),
    'fixtures': os.path.join('conteudo', 'eleicoes', 'fixtures'),
    'estado': os.path.join('estado', 'eleicoes'),
}
FIXTURE = 'DEVELOPMENT_FIXTURE'
DATA = re.compile(r'^\d{4}-\d{2}-\d{2}$')
CAMPOS_VOLATEIS = ('criado_em', 'atualizado_em', 'ausente_desde', '_origem')


def entes_validos():
    """União ('BR') mais os entes do registro compartilhado com o Mapa Normativo."""
    from fontes import ENTES
    return {'BR'} | set(ENTES)


def hash_registro(r, ignorar=CAMPOS_VOLATEIS):
    """Hash estável do conteúdo de um registro, sem os campos de controle."""
    base = {k: v for k, v in r.items() if k not in ignorar}
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


class Banco:
    def __init__(self, raiz=RAIZ):
        self.raiz = raiz
        self.tabelas = {n: [] for n in TABELAS}
        self.erros_carga = []

    # -------------------------------------------------------------- carga
    def caminho(self, tabela, origem):
        return os.path.join(self.raiz, PASTAS[origem], tabela + '.json')

    def carregar(self, com_fixtures=True):
        for nome, t in TABELAS.items():
            for origem in t.origens:
                if origem == 'fixtures' and not com_fixtures:
                    continue
                cam = self.caminho(nome, origem)
                if not os.path.exists(cam):
                    continue
                try:
                    linhas = json.load(open(cam, encoding='utf-8'))
                except ValueError as e:
                    self.erros_carga.append(f'{os.path.relpath(cam, self.raiz)}: JSON inválido ({e})'); continue
                if not isinstance(linhas, list):
                    self.erros_carga.append(f'{os.path.relpath(cam, self.raiz)}: o arquivo deve conter uma lista de registros'); continue
                for r in linhas:
                    r = dict(r)
                    r['_origem'] = origem
                    if origem == 'fixtures':
                        if r.get('origem_dado') not in (None, FIXTURE):
                            self.erros_carga.append(f'{nome}.{r.get("id")}: registro em fixtures/ com origem_dado {r.get("origem_dado")}')
                        r['origem_dado'] = FIXTURE
                    self.tabelas[nome].append(r)
        return self

    def por_id(self, tabela):
        return {r['id']: r for r in self.tabelas[tabela] if 'id' in r}

    def onde(self, tabela, **filtro):
        return [r for r in self.tabelas[tabela] if all(r.get(k) == v for k, v in filtro.items())]

    # -------------------------------------------------------------- validação
    def validar(self):
        """Devolve (erros, avisos). Erro impede a publicação; aviso vai para o painel."""
        erros, avisos = list(self.erros_carga), []
        ids = {n: self.por_id(n) for n in TABELAS}
        entes = entes_validos()
        for nome, t in TABELAS.items():
            vistos = {}
            unicos = {u: {} for u in t.unicos}
            for r in self.tabelas[nome]:
                rid = r.get('id')
                ref = f'{nome}.{rid}'
                if not rid:
                    erros.append(f'{nome}: registro sem id ({json.dumps(r, ensure_ascii=False)[:80]})'); continue
                if rid in vistos:
                    erros.append(f'{ref}: id duplicado ({vistos[rid]} e {r["_origem"]})')
                vistos[rid] = r['_origem']
                for campo in r:
                    if campo not in t.campos and not campo.startswith('_'):
                        erros.append(f'{ref}: campo desconhecido "{campo}"')
                for campo, c in t.campos.items():
                    v = r.get(campo)
                    if v is None or v == '' or v == []:
                        if c.obrigatorio:
                            erros.append(f'{ref}: campo obrigatório "{campo}" ausente')
                        continue
                    erros.extend(self._tipo(ref, campo, c, v, entes))
                    for alvo in (v if c.tipo == 'lista' and c.fk else [v] if c.fk else []):
                        destino = ids[c.fk].get(alvo)
                        if destino is None:
                            erros.append(f'{ref}: {campo} aponta para {c.fk}.{alvo}, que não existe')
                        elif c.fk not in REFERENCIA:
                            fx_o, fx_d = r.get('origem_dado') == FIXTURE, destino.get('origem_dado') == FIXTURE
                            if fx_o and not fx_d:
                                erros.append(f'{ref}: registro fictício (DEVELOPMENT_FIXTURE) aponta para dado real {c.fk}.{alvo}')
                            if fx_d and not fx_o:
                                erros.append(f'{ref}: dado real aponta para registro fictício {c.fk}.{alvo}')
                for u in t.unicos:
                    chave = tuple(r.get(k) for k in u)
                    if chave[0] is None:
                        continue
                    if chave in unicos[u]:
                        erros.append(f'{ref}: duplicidade em ({", ".join(u)}) com {nome}.{unicos[u][chave]}')
                    unicos[u][chave] = rid
        erros.extend(self._regras_de_dominio(ids, avisos))
        return erros, avisos

    @staticmethod
    def _tipo(ref, campo, c, v, entes):
        e = []
        tipos = {'str': str, 'int': int, 'bool': bool, 'dict': dict, 'lista': list, 'data': str, 'datahora': str}
        if not isinstance(v, tipos[c.tipo]) or (c.tipo == 'int' and isinstance(v, bool)):
            return [f'{ref}: campo "{campo}" deveria ser {c.tipo}']
        if c.tipo == 'data' and not DATA.match(v):
            e.append(f'{ref}: data inválida em "{campo}" ({v}); use AAAA-MM-DD')
        if c.tipo == 'datahora':
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                e.append(f'{ref}: data e hora inválidas em "{campo}" ({v})')
        if c.enum and v not in c.enum:
            e.append(f'{ref}: valor "{v}" fora da enumeração de "{campo}" ({", ".join(c.enum)})')
        if c.ente and v not in entes:
            e.append(f'{ref}: ente "{v}" não cadastrado em ENTES (coletor/fontes.py)')
        if c.max_len and isinstance(v, str) and len(v) > c.max_len:
            e.append(f'{ref}: "{campo}" excede {c.max_len} caracteres ({len(v)})')
        if isinstance(v, str) and '\u2014' in v:
            e.append(f'{ref}: travessão em "{campo}"; use vírgula ou parênteses')
        return e

    def _regras_de_dominio(self, ids, avisos):
        erros = []
        fontes_por_afirmacao = {}
        for cs in self.tabelas['afirmacao_fontes']:
            fontes_por_afirmacao.setdefault(cs['afirmacao_id'], []).append(cs)
        for a in self.tabelas['afirmacoes']:
            if not fontes_por_afirmacao.get(a['id']):
                avisos.append(f'afirmacoes.{a["id"]}: afirmação sem fonte; não será publicada')
            if not a.get('candidatura_id') and not a.get('proposta_id') and a.get('tipo') == 'PROPOSAL':
                erros.append(f'afirmacoes.{a["id"]}: afirmação de proposta precisa de proposta_id ou candidatura_id')
        afirm_por_proposta = {}
        for a in self.tabelas['afirmacoes']:
            if a.get('proposta_id'):
                afirm_por_proposta.setdefault(a['proposta_id'], []).append(a)
        for p in self.tabelas['propostas']:
            if not any(fontes_por_afirmacao.get(a['id']) for a in afirm_por_proposta.get(p['id'], [])):
                avisos.append(f'propostas.{p["id"]}: proposta sem afirmação com fonte; não será publicada')
        for r in self.tabelas['regras']:
            if r.get('fora_da_base'):
                if not r.get('url') or not r.get('norma'):
                    erros.append(f'regras.{r["id"]}: regra fora da base exige "norma" e "url" da fonte oficial')
            elif not r.get('dispositivo'):
                erros.append(f'regras.{r["id"]}: regra sem dispositivo do Mapa Normativo; marque fora_da_base se for o caso')
        for c in self.tabelas['cargos_eleicao']:
            a = ids['afirmacoes'].get(c.get('vagas_afirmacao_id'))
            if a is not None and not isinstance((a.get('valor') or {}).get('vagas'), int):
                erros.append(f'cargos_eleicao.{c["id"]}: a afirmação de vagas precisa de valor.vagas (inteiro)')
        # Número repetido no mesmo cargo é esperado quando há substituição (o substituto
        # herda o número); fica como aviso para conferência, com as situações de cada um.
        por_numero = {}
        for c in self.tabelas['candidaturas']:
            por_numero.setdefault((c.get('eleicao_id'), c.get('cargo_eleicao_id') or c.get('cargo_id'), c.get('numero')), []).append(c)
        for (_, esc, num), cs in sorted(por_numero.items(), key=lambda x: str(x[0])):
            if len(cs) > 1:
                avisos.append(f'candidaturas: número {num} repetido em {esc} (' + '; '.join(
                    f'{c["id"]} {c.get("situacao_oficial") or c.get("situacao")}' for c in cs) + '); provável substituição')
        for rv in self.tabelas['revisoes']:
            if rv['analise_id'] not in ids['analises']:
                avisos.append(f'revisoes.{rv["id"]}: revisão de análise inexistente ({rv["analise_id"]})')
            if rv['status'] == 'CORRECTED' and not rv.get('correcao'):
                erros.append(f'revisoes.{rv["id"]}: status CORRECTED exige o campo "correcao"')
        return erros

    # -------------------------------------------------------------- escrita (tabelas geradas)
    def sincronizar(self, tabela, novos, agora, origem='estado', marcar_ausentes=None):
        """Upsert com detecção de mudança por hash. Devolve contagens e a lista de mudanças.

        Nada é apagado: registro que deixou de vir da fonte recebe `ausente_desde`
        (só em tabelas que declaram esse campo e quando `marcar_ausentes` é um filtro
        que delimita o escopo da coleta, por exemplo {'cargo_id': 'governador'})."""
        t = TABELAS[tabela]
        atuais = {r['id']: r for r in self.tabelas[tabela] if r['_origem'] == origem}
        outros = [r for r in self.tabelas[tabela] if r['_origem'] != origem]
        cont = {'fetched': len(novos), 'created': 0, 'updated': 0, 'unchanged': 0, 'missing': 0}
        mudancas, vistos = [], set()
        for n in novos:
            n = {k: v for k, v in n.items() if v is not None}
            n['_origem'] = origem
            vistos.add(n['id'])
            velho = atuais.get(n['id'])
            if velho is None:
                if 'criado_em' in t.campos:
                    n['criado_em'] = agora
                if 'atualizado_em' in t.campos:
                    n['atualizado_em'] = agora
                atuais[n['id']] = n; cont['created'] += 1
                mudancas.append({'tipo': 'criado', 'tabela': tabela, 'id': n['id'], 'em': agora})
            elif hash_registro(velho) != hash_registro(n):
                campos = sorted(k for k in set(velho) | set(n) if k not in CAMPOS_VOLATEIS and velho.get(k) != n.get(k))
                for k in ('criado_em',):
                    if k in velho:
                        n[k] = velho[k]
                if 'atualizado_em' in t.campos:
                    n['atualizado_em'] = agora
                atuais[n['id']] = n; cont['updated'] += 1
                mudancas.append({'tipo': 'atualizado', 'tabela': tabela, 'id': n['id'], 'em': agora, 'campos': campos,
                                 'antes': {k: velho.get(k) for k in campos}, 'depois': {k: n.get(k) for k in campos}})
            else:
                if velho.get('ausente_desde'):
                    velho.pop('ausente_desde')
                    mudancas.append({'tipo': 'reapareceu', 'tabela': tabela, 'id': n['id'], 'em': agora})
                cont['unchanged'] += 1
        if marcar_ausentes is not None and 'ausente_desde' in t.campos:
            for rid, r in atuais.items():
                if rid in vistos or not all(r.get(k) == v for k, v in marcar_ausentes.items()):
                    continue
                cont['missing'] += 1
                if not r.get('ausente_desde'):
                    r['ausente_desde'] = agora
                    mudancas.append({'tipo': 'ausente', 'tabela': tabela, 'id': rid, 'em': agora})
        self.tabelas[tabela] = outros + list(atuais.values())
        return cont, mudancas

    def substituir(self, tabela, registros, origem='estado'):
        """Troca todos os registros de uma origem (usado por tabelas derivadas, como análises)."""
        for r in registros:
            r['_origem'] = origem
        self.tabelas[tabela] = [r for r in self.tabelas[tabela] if r['_origem'] != origem] + list(registros)

    def gravar(self, tabela, origem='estado'):
        linhas = sorted((r for r in self.tabelas[tabela] if r['_origem'] == origem), key=lambda r: str(r['id']))
        limpas = [{k: v for k, v in r.items() if not k.startswith('_')} for r in linhas]
        cam = self.caminho(tabela, origem)
        os.makedirs(os.path.dirname(cam), exist_ok=True)
        with open(cam, 'w', encoding='utf-8') as f:
            json.dump(limpas, f, ensure_ascii=False, indent=1)
            f.write('\n')


def registrar_ingestao(banco, log, limite=500):
    """Acrescenta um registro ao log de ingestão e grava; mantém os `limite` mais recentes."""
    banco.tabelas['ingestoes'].append(dict(log, _origem='estado'))
    banco.tabelas['ingestoes'] = sorted(banco.tabelas['ingestoes'], key=lambda r: r['iniciado_em'])[-limite:]
    banco.gravar('ingestoes')


def versao_gravada(raiz=RAIZ):
    cam = os.path.join(raiz, PASTAS['estado'], '_esquema.json')
    try:
        return json.load(open(cam)).get('versao', 0)
    except FileNotFoundError:
        return 0


def carregar(raiz=RAIZ, com_fixtures=True):
    return Banco(raiz).carregar(com_fixtures=com_fixtures)


def main():
    b = carregar()
    erros, avisos = b.validar()
    if versao_gravada() != VERSAO_ESQUEMA:
        erros.append(f'estado/eleicoes/_esquema.json na versão {versao_gravada()}; o esquema está na {VERSAO_ESQUEMA}. '
                     'Rode python3 coletor/eleicoes/migrar.py')
    n = {k: len(v) for k, v in b.tabelas.items() if v}
    print(json.dumps({'registros': n, 'erros': erros[:50], 'n_erros': len(erros), 'avisos': avisos[:50], 'n_avisos': len(avisos)},
                     ensure_ascii=False, indent=1))
    sys.exit(1 if erros else 0)


if __name__ == '__main__':
    main()
