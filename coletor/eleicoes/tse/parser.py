"""Parser das respostas do DivulgaCandContas: confere a estrutura e extrai os registros.

Não interpreta nada: só verifica se a resposta tem o formato esperado e devolve os
itens brutos, com os erros de formato separados (um item defeituoso não derruba a
coleta inteira, mas também não passa em silêncio).
"""


class ErroFormato(Exception):
    pass


def candidatos_da_lista(snap):
    """Devolve (itens, erros) de uma resposta de candidatura/listar."""
    corpo = snap.get('corpo')
    if not isinstance(corpo, dict) or not isinstance(corpo.get('candidatos'), list):
        raise ErroFormato(f'{snap.get("url")}: resposta sem a lista "candidatos"')
    itens, erros, vistos = [], [], set()
    for i, c in enumerate(corpo['candidatos']):
        falta = [k for k in ('id', 'numero', 'nomeUrna') if c.get(k) in (None, '')]
        if falta:
            erros.append(f'{snap["url"]}: item {i} sem {", ".join(falta)}'); continue
        if c['id'] in vistos:
            erros.append(f'{snap["url"]}: candidatura {c["id"]} repetida na mesma resposta'); continue
        vistos.add(c['id'])
        itens.append(c)
    return itens, erros


def candidato_do_detalhe(snap):
    c = snap.get('corpo')
    if not isinstance(c, dict) or not c.get('id') or c.get('numero') in (None, ''):
        raise ErroFormato(f'{snap.get("url")}: detalhe de candidatura sem id ou número')
    return c
