"""Sincroniza as candidaturas oficiais: cliente -> parser -> normalizador -> repositório.

    python3 coletor/eleicoes/tse/sincronizar.py [--eleicao 2026-geral] [--transporte http|snapshot]
                                               [--detalhar todos|majoritarios|nenhum]

Com `--transporte http` (padrão), cada resposta é gravada como snapshot; se o TSE
recusar a conexão, a execução registra o erro no log de ingestão e nada é alterado.
Com `--transporte snapshot`, reprocessa as respostas já guardadas, sem rede.

Toda execução grava um registro em estado/eleicoes/ingestoes.json (buscados, criados,
atualizados, inalterados, ausentes, erros) e as mudanças em estado/eleicoes/mudancas.json.
Registro que some da fonte não é apagado: recebe `ausente_desde`.
"""
import argparse, json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))
import cliente, parser, normalizador  # noqa: E402
import repositorio  # noqa: E402

UF = {'BR': 'BR', 'SC': 'SC'}


def gravar_mudancas(raiz, mudancas, limite=5000):
    cam = os.path.join(raiz, 'estado', 'eleicoes', 'mudancas.json')
    antigas = json.load(open(cam, encoding='utf-8')) if os.path.exists(cam) else []
    with open(cam, 'w', encoding='utf-8') as f:
        json.dump((antigas + mudancas)[-limite:], f, ensure_ascii=False, indent=1)
        f.write('\n')


def sincronizar(eleicao_id='2026-geral', transporte=None, detalhar='majoritarios', raiz=repositorio.RAIZ, agora=None):
    agora = agora or cliente.agora()
    transporte = transporte or cliente.TransporteHTTP()
    tse = cliente.ClienteTSE(transporte)
    banco = repositorio.carregar(raiz)
    eleicao = banco.por_id('eleicoes').get(eleicao_id)
    if not eleicao or not eleicao.get('tse_codigo'):
        raise SystemExit(f'Eleição {eleicao_id} sem código do TSE em conteudo/eleicoes/eleicoes.json')
    cargos = banco.por_id('cargos')
    log = {'id': f'tse-candidaturas-{agora}', 'fonte': 'TSE, DivulgaCandContas', 'rotulo': 'TSE Candidates',
           'iniciado_em': agora, 'transporte': transporte.nome, 'fetched': 0, 'created': 0, 'updated': 0, 'unchanged': 0,
           'missing': 0, 'errors': 0, 'erros': [], 'avisos': [], 'snapshots': [], 'por_escopo': [], 'origem_dado': 'OFFICIAL'}
    mudancas = []
    candidatos, candidaturas, fontes, partidos = [], [], [], {}
    escopos = []
    for ce in sorted(banco.onde('cargos_eleicao', eleicao_id=eleicao_id), key=lambda x: x.get('ordem', 0)):
        cargo = cargos[ce['cargo_id']]
        uf = UF.get(ce['ente'], ce['ente'])
        esc = {'escopo': ce['id'], 'fetched': 0, 'erros': 0}
        try:
            snap = tse.listar_candidatos(eleicao['ano'], uf, eleicao['tse_codigo'], cargo['tse_codigo'])
            itens, erros = parser.candidatos_da_lista(snap)
        except (cliente.ErroTransporte, parser.ErroFormato) as e:
            log['erros'].append(str(e)); esc['erros'] += 1; log['por_escopo'].append(esc); continue
        log['erros'].extend(erros); esc['erros'] += len(erros)
        log['snapshots'].append({'url': snap['url'], 'sha256': snap.get('sha256'), 'capturado_em': snap['capturado_em']})
        rot_ente = 'Brasil' if ce['ente'] == 'BR' else 'Santa Catarina' if ce['ente'] == 'SC' else ce['ente']
        fl = normalizador.fonte_lista(snap, cargo['nome'], rot_ente)
        fontes.append(fl)
        siglas = {(i.get('partido') or {}).get('sigla') for i in itens}
        ctx = {'eleicao_id': eleicao_id, 'cargo_id': cargo['id'], 'cargo_eleicao_id': ce['id'], 'ente': ce['ente'],
               'ano': eleicao['ano'], 'uf': uf, 'tse_eleicao': eleicao['tse_codigo'], 'fonte_lista_id': fl['id']}
        detalhar_este = detalhar == 'todos' or (detalhar == 'majoritarios' and cargo.get('sistema') == 'MAJORITARIAN')
        for item in itens:
            det, det_snap = None, None
            if detalhar_este:
                try:
                    det_snap = tse.buscar_candidato(eleicao['ano'], uf, eleicao['tse_codigo'], item['id'])
                    det = parser.candidato_do_detalhe(det_snap)
                    log['snapshots'].append({'url': det_snap['url'], 'sha256': det_snap.get('sha256'), 'capturado_em': det_snap['capturado_em']})
                except (cliente.ErroTransporte, parser.ErroFormato) as e:
                    log['erros'].append(str(e)); esc['erros'] += 1
            pessoa, cand, part, fs, avisos = normalizador.normalizar(item, det, det_snap, ctx, siglas)
            log['avisos'].extend(avisos)
            candidatos.append(pessoa); candidaturas.append(cand); fontes.extend(fs)
            if part:  # o detalhe traz nome e número do partido; a lista, só a sigla
                atual = partidos.setdefault(part['id'], {})
                for k, v in part.items():
                    if v is not None and (atual.get(k) is None or (det is not None and k in ('nome', 'numero', 'fonte_id'))):
                        atual[k] = v
            esc['fetched'] += 1
        escopos.append(ce['id'])
        log['por_escopo'].append(esc)
    # só marca ausências nos escopos lidos com sucesso nesta execução
    for tabela, regs in (('fontes', fontes), ('partidos', list(partidos.values())), ('candidatos', candidatos)):
        _, m = banco.sincronizar(tabela, regs, agora)
        mudancas.extend(m)
    cont_total = {'fetched': 0, 'created': 0, 'updated': 0, 'unchanged': 0, 'missing': 0}
    for esc in escopos:
        regs = [c for c in candidaturas if c['cargo_eleicao_id'] == esc]
        cont, m = banco.sincronizar('candidaturas', regs, agora, marcar_ausentes={'cargo_eleicao_id': esc})
        for k in cont_total:
            cont_total[k] += cont[k]
        mudancas.extend(m)
        for e in log['por_escopo']:
            if e['escopo'] == esc:
                e.update({k: cont[k] for k in ('created', 'updated', 'unchanged', 'missing')})
    log.update(cont_total)
    log['errors'] = len(log['erros'])
    log['concluido_em'] = cliente.agora()
    erros, _ = banco.validar()
    novos_erros = [e for e in erros if e.split(':')[0].split('.')[0] in ('candidaturas', 'candidatos', 'partidos', 'fontes')]
    if novos_erros:
        log['erros'].extend('integridade: ' + e for e in novos_erros[:50])
        log['errors'] = len(log['erros'])
        log['avisos'].append('dados não gravados: a validação de integridade falhou')
    else:
        for t in ('fontes', 'partidos', 'candidatos', 'candidaturas'):
            banco.gravar(t)
        gravar_mudancas(raiz, mudancas)
    repositorio.registrar_ingestao(banco, log)
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--eleicao', default='2026-geral')
    ap.add_argument('--transporte', choices=('http', 'snapshot'), default='http')
    ap.add_argument('--detalhar', choices=('todos', 'majoritarios', 'nenhum'), default='majoritarios')
    a = ap.parse_args()
    t = cliente.TransporteHTTP() if a.transporte == 'http' else cliente.TransporteSnapshot()
    log = sincronizar(a.eleicao, t, a.detalhar)
    resumo = {k: log[k] for k in ('rotulo', 'transporte', 'fetched', 'created', 'updated', 'unchanged', 'missing', 'errors')}
    resumo['primeiros_erros'] = log['erros'][:5]
    print(json.dumps(resumo, ensure_ascii=False))


if __name__ == '__main__':
    main()
