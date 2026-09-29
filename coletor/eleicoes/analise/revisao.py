"""AnalisadorRevisado: aplica as revisões humanas gravadas em conteudo/eleicoes/revisoes.json.

A análise automática nunca é sobrescrita. A revisão é um registro próprio, com revisor,
data e o `hash_entrada` que foi revisado:

- REVIEWED: a análise automática foi conferida e mantida;
- CORRECTED: os campos em `correcao` substituem os da análise automática (a original
  continua gravada, para auditoria);
- PENDING_REVIEW: marcada para revisão.

Se o `hash_entrada` atual for diferente do revisado (a proposta, a competência ou o
texto do dispositivo mudaram), a revisão fica desatualizada: o status volta a
PENDING_REVIEW e o painel aponta a divergência.
"""
from . import AnalisadorProposta

CAMPOS_CORRIGIVEIS = ('classificacao', 'competencia_direta', 'pode_iniciar', 'explicacao', 'instrumento_id',
                      'resumo_fundamento', 'confianca', 'observacoes')


class AnalisadorRevisado(AnalisadorProposta):
    nome = 'HumanReviewedAnalyzer'

    def __init__(self, base, revisoes):
        self.base = base
        self.versao = base.versao
        self.revisoes = {r['analise_id']: r for r in revisoes}

    def analisar(self, proposta, cargo, ctx):
        res = self.base.analisar(proposta, cargo, ctx)
        rv = self.revisoes.get(res.analise['id'])
        if not rv:
            return res
        a = res.analise
        if rv['hash_entrada_revisada'] != a['hash_entrada']:
            a['status_revisao'] = 'PENDING_REVIEW'
            a['observacoes'] = (a.get('observacoes') or []) + [
                f'Revisão de {rv["revisado_em"][:10]} por {rv["revisor"]} desatualizada: os dados da análise mudaram depois dela.']
            return res
        a['status_revisao'] = rv['status']
        a['revisao_id'] = rv['id']
        if rv['status'] == 'CORRECTED':
            original = {}
            for k in CAMPOS_CORRIGIVEIS:
                if k in (rv.get('correcao') or {}):
                    original[k] = a.get(k)
                    a[k] = rv['correcao'][k]
            a['original'] = original
        return res
