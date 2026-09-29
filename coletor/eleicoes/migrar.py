"""Migrações do esquema do Mapa Eleitoral.

Cada migração é uma função que recebe o Banco carregado e ajusta os registros para a
versão seguinte do esquema. A versão aplicada fica em estado/eleicoes/_esquema.json,
com a data de cada passo. Para mudar o esquema: aumente VERSAO_ESQUEMA em esquema.py e
acrescente aqui a função da nova versão; nunca edite uma migração já aplicada.

    python3 coletor/eleicoes/migrar.py
"""
import json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from esquema import VERSAO_ESQUEMA  # noqa: E402
import repositorio  # noqa: E402


def v1_criacao(banco):
    """Versão inicial: cria as pastas e os arquivos vazios das tabelas geradas."""
    for nome, t in repositorio.TABELAS.items():
        if 'estado' in t.origens and not os.path.exists(banco.caminho(nome, 'estado')):
            banco.gravar(nome, 'estado')


MIGRACOES = {1: v1_criacao}


def migrar(raiz=repositorio.RAIZ):
    atual = repositorio.versao_gravada(raiz)
    cam = os.path.join(raiz, repositorio.PASTAS['estado'], '_esquema.json')
    historico = json.load(open(cam)).get('historico', []) if os.path.exists(cam) else []
    aplicadas = []
    for v in range(atual + 1, VERSAO_ESQUEMA + 1):
        banco = repositorio.carregar(raiz)
        MIGRACOES[v](banco)
        historico.append({'versao': v, 'migracao': MIGRACOES[v].__name__, 'aplicada_em': datetime.now(timezone.utc).isoformat(timespec='seconds')})
        os.makedirs(os.path.dirname(cam), exist_ok=True)
        json.dump({'versao': v, 'historico': historico}, open(cam, 'w'), ensure_ascii=False, indent=1)
        aplicadas.append(v)
    return aplicadas


if __name__ == '__main__':
    print(json.dumps({'aplicadas': migrar(), 'versao': VERSAO_ESQUEMA}))
