"""Rotina de atualização. Rodada de hora em hora pela rotina na nuvem.

Etapas: (1) DOU, edição normal e extra, de hoje e de ontem; (2) legislação compilada
do Planalto, com comparação de cada artigo pelo hash; (3) STJ, temas pendentes a cada
execução e busca de temas novos na primeira execução do dia; (4) súmulas do STJ uma vez
por dia; (5) geração dos arquivos publicados. Nada é apagado: toda mudança vai para
estado/changelog.json com data e fonte.
"""
import argparse, json, os, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(__file__))
import planalto, dou, stj, congresso
from fontes import MARCADORES_DOU
from fontes import DIPLOMAS
from construir import construir, RAIZ, CACHE

EST = os.path.join(RAIZ, 'estado')
BRT = timezone(timedelta(hours=-3))


def ler(nome, padrao):
    try:
        return json.load(open(os.path.join(EST, nome)))
    except FileNotFoundError:
        return padrao


def gravar(nome, obj):
    os.makedirs(EST, exist_ok=True)
    json.dump(obj, open(os.path.join(EST, nome), 'w'), ensure_ascii=False, indent=1)


def limpar_pendencias(agora, dias=45):
    """Pendências antigas saem da lista: o ato continua no histórico e no registro do DOU."""
    pend = ler('pendencias.json', [])
    limite = (agora - timedelta(days=dias)).isoformat(timespec='seconds')
    gravar('pendencias.json', [p for p in pend if (p.get('desde') or '') >= limite])


def etapa_dou(agora, log, status):
    vistos = ler('dou.json', [])
    ids = {x['id'] for x in vistos}
    pend = ler('pendencias.json', [])
    novos = 0
    for dias in range(4):  # hoje e os três dias anteriores: cobre fins de semana e edições extras
        d = (agora.astimezone(BRT) - timedelta(days=dias)).strftime('%d-%m-%Y')
        for secao in ('do1', 'do1e'):
            atos = dou.edicao(d, secao)
            if atos is None:
                status['DOU'] = 'falha na leitura'; continue
            status['DOU'] = 'ok'
            for a in dou.relevantes(atos):
                if a['id'] in ids:
                    continue
                a['detectado_em'] = agora.isoformat(timespec='seconds'); vistos.append(a); ids.add(a['id']); novos += 1
                for dip in a['diplomas'] or [None]:
                    pend.append({'diploma': dip, 'ato': a['titulo'], 'url': a['url'], 'desde': a['detectado_em'],
                                 'situacao': 'alteração publicada, compilação oficial pendente' if dip else 'novo ato normativo a avaliar'})
                log.append({'data': a['detectado_em'], 'fonte': 'DOU', 'tipo': 'publicacao', 'titulo': a['titulo'], 'url': a['url'], 'diplomas': a['diplomas']})
    gravar('dou.json', vistos[-400:]); gravar('pendencias.json', pend)
    return novos


def etapa_planalto(agora, log, status, completo=False):
    hashes = ler('hashes.json', {})
    verif = hashes.setdefault('_verificado', {})
    etags = ler('etags.json', {})
    baixados, mudancas, inalterados = {}, 0, set()
    for f in DIPLOMAS:
        cam = os.path.join(CACHE, f['cache'] + '.htm')
        if f['cache'] not in baixados and f['cache'] not in inalterados and not completo:
            cab = planalto.cabecalho(f['url'])
            if cab and cab['etag'] and etags.get(f['url'], {}).get('etag') == cab['etag'] and f['id'] in hashes:
                inalterados.add(f['cache'])
        if f['cache'] in inalterados:
            status['Planalto: ' + f['sigla']] = 'ok, sem alteração'
            verif[f['id']] = agora.isoformat(timespec='seconds'); continue
        if f['cache'] not in baixados:
            ok = planalto.baixar(f['url'], cam + '.novo')
            baixados[f['cache']] = ok
            if ok:
                os.replace(cam + '.novo', cam)
                cab = planalto.cabecalho(f['url'])
                if cab:
                    etags[f['url']] = cab
            elif os.path.exists(cam + '.novo'):
                os.remove(cam + '.novo')
        if not baixados[f['cache']]:
            status['Planalto: ' + f['sigla']] = 'falha no download; mantida a última versão'; continue
        status['Planalto: ' + f['sigla']] = 'ok'
        arts = planalto.extrair(cam, f)
        antigos = hashes.get(f['id'], {})
        atuais = {n: a['hash'] for n, a in arts.items()}
        if antigos:
            for n, h in atuais.items():
                if n not in antigos:
                    log.append({'data': agora.isoformat(timespec='seconds'), 'fonte': 'Planalto', 'tipo': 'incluido', 'd': f"{f['id']}.{n}", 'titulo': f"{f['sigla']}, {arts[n]['r']}: dispositivo incluído", 'url': f['url']}); mudancas += 1
                elif antigos[n] != h:
                    notas = sorted({l[1] for l in arts[n]['l'] if l[1]})[-1:] 
                    log.append({'data': agora.isoformat(timespec='seconds'), 'fonte': 'Planalto', 'tipo': 'revogado' if arts[n]['rev'] else 'alterado', 'd': f"{f['id']}.{n}", 'titulo': f"{f['sigla']}, {arts[n]['r']}: texto alterado", 'nota': notas[0] if notas else '', 'url': f['url']}); mudancas += 1
        if antigos != atuais:
            hashes[f['id']] = atuais
            if antigos:
                pend = [p for p in ler('pendencias.json', []) if p.get('diploma') != f['id']]
                gravar('pendencias.json', pend)
        verif[f['id']] = agora.isoformat(timespec='seconds')
    gravar('hashes.json', hashes); gravar('etags.json', etags)
    return mudancas


def etapa_stj(agora, log, status, diario):
    prec = ler('precedentes.json', {})
    alterados = 0
    # A cada hora: temas ainda não transitados, em lotes de 25 que se revezam; na execução
    # diária, todos os temas ligados a institutos também são reconferidos.
    pendentes = sorted((p for p in prec.values() if p['trib'] == 'STJ' and p['tipo'] == 'Tema repetitivo'
                        and 'trânsito' not in (p.get('situacao') or '').lower()), key=lambda p: p.get('verificado_em') or '')
    alvo = pendentes[:25]
    if diario:
        refs = {x for i in json.load(open(os.path.join(RAIZ, 'conteudo', 'institutos.json'))) for x in i['precedentes']}
        ligados = [p for p in prec.values() if p['id'] in refs and p['tipo'] == 'Tema repetitivo']
        alvo += [p for p in ligados if p not in alvo]
    for p in alvo:
        t = stj.tema(p['numero'])
        if not t:
            status['STJ, temas'] = 'portal indisponível nesta execução; coberto pelo Jusratio'; break
        status.setdefault('STJ, temas', 'ok')
        mudou = (t['situacao'], t['tese']) != (p.get('situacao'), p.get('tese'))
        if mudou:
            log.append({'data': agora.isoformat(timespec='seconds'), 'fonte': 'STJ', 'tipo': 'precedente', 'titulo': f"Tema {p['numero']}/STJ: {t['situacao']}" + (' · tese firmada' if t['tese'] and not p.get('tese') else ''), 'url': t['url'], 'p': p['id']})
            alterados += 1
        p.update({'situacao': t['situacao'], 'tese': t['tese'], 'questao': t['questao'], 'orgao': t['orgao'] or p.get('orgao'),
                  'processos': t['processos'] or p.get('processos', []), 'verificado_em': agora.isoformat(timespec='seconds')})
        p['data'] = next((x['julgado'] for x in p['processos'] if x.get('julgado')), p.get('data'))
    if diario:
        # temas novos: sonda os números seguintes ao maior já visto
        carga_inicial = not os.path.exists(os.path.join(EST, 'stj_maior.json'))
        maior = max([int(p['numero']) for p in prec.values() if p['trib'] == 'STJ' and p['tipo'] == 'Tema repetitivo'] + [ler('stj_maior.json', {}).get('n', 0)])
        vazios = 0; n = maior
        while vazios < 5 and (carga_inicial or n < maior + 40):
            n += 1
            t = stj.tema(n)
            if t is None and vazios == 0 and n == maior + 1 and not stj.tema(maior):
                break  # portal bloqueado neste ambiente
            if not t or not t['situacao']:
                vazios += 1; continue
            vazios = 0
            pid = f'stj.tema.{n}'
            prec[pid] = {'id': pid, 'trib': 'STJ', 'tipo': 'Tema repetitivo', 'nivel': 'B', 'numero': str(n), 'titulo': f'Tema {n}/STJ',
                         'orgao': t['orgao'], 'situacao': t['situacao'], 'questao': t['questao'], 'tese': t['tese'], 'ramo': t['ramo'],
                         'processos': t['processos'], 'data': next((x['julgado'] for x in t['processos'] if x.get('julgado')), None),
                         'dispositivos': [], 'url': t['url'], 'fonte': 'STJ, Precedentes Qualificados', 'verificado_em': agora.date().isoformat(), 'novo': not carga_inicial}
            if not carga_inicial:
                    log.append({'data': agora.isoformat(timespec='seconds'), 'fonte': 'STJ', 'tipo': 'novo_tema', 'titulo': f'Tema {n}/STJ ({t["ramo"] or "sem ramo"}): {t["situacao"]}', 'url': t['url'], 'p': pid})
            gravar('stj_maior.json', {'n': n})
    gravar('precedentes.json', prec)
    return alterados


def etapa_sumulas(agora, log, status):
    try:
        import sumulas
        todas = sumulas.todas(os.path.join(CACHE, 'verbetes.pdf'))
    except BaseException as e:  # a leitura do PDF pode derrubar o interpretador por conflito de bibliotecas
        status['STJ, súmulas'] = f'indisponível nesta execução ({e.__class__.__name__}); coberto pelo Jusratio'; return 0
    status['STJ, súmulas'] = 'ok'
    prec = ler('precedentes.json', {})
    maior = ler('stj_sumula_maior.json', {}).get('n', 0) or max(int(k) for k in todas)
    novos = 0
    for k, txt in todas.items():
        pid = f'stj.sum.{k}'
        if pid in prec:
            if prec[pid]['tese'] != txt:
                log.append({'data': agora.isoformat(timespec='seconds'), 'fonte': 'STJ', 'tipo': 'precedente', 'titulo': f'Súmula {k}/STJ: enunciado alterado na fonte', 'url': sumulas.URL, 'p': pid})
                prec[pid]['tese'] = txt
        elif int(k) > maior:
            prec[pid] = {'id': pid, 'trib': 'STJ', 'tipo': 'Súmula', 'nivel': 'A', 'numero': k, 'titulo': f'Súmula {k}/STJ', 'orgao': None,
                         'situacao': 'Vigente', 'questao': None, 'tese': txt, 'processos': [], 'data': None, 'dispositivos': [],
                         'url': sumulas.URL, 'fonte': 'STJ, Verbetes sumulares (PDF oficial)', 'verificado_em': agora.date().isoformat(), 'novo': True}
            log.append({'data': agora.isoformat(timespec='seconds'), 'fonte': 'STJ', 'tipo': 'nova_sumula', 'titulo': f'Súmula {k}/STJ publicada', 'url': sumulas.URL, 'p': pid})
            novos += 1
    gravar('stj_sumula_maior.json', {'n': max(int(k) for k in todas)})
    gravar('precedentes.json', prec)
    return novos


def etapa_congresso(agora, log, status, diario):
    """Senado: normas novas (a cada execução). Câmara: projetos que alteram diplomas (uma vez por dia)."""
    ano = agora.astimezone(BRT).year
    normas = congresso.normas_senado(ano)
    if normas is not None and agora.astimezone(BRT).month == 1:
        anteriores = congresso.normas_senado(ano - 1)
        normas = (anteriores or []) + normas
    if normas is None:
        status['Senado, legislação'] = 'falha na leitura'
    else:
        status['Senado, legislação'] = 'ok'
        vistas = ler('normas_vistas.json', None)
        ids = {n['id'] for n in (vistas or [])}
        pend = ler('pendencias.json', [])
        for n in normas:
            if n['id'] in ids:
                continue
            if vistas is not None:  # na primeira leitura, só forma a linha de base
                afeta = [d for d, ms in MARCADORES_DOU.items() if any(m.lower() in n['ementa'].lower() for m in ms)]
                log.append({'data': agora.isoformat(timespec='seconds'), 'fonte': 'Senado', 'tipo': 'nova_norma', 'titulo': n['titulo'] + ' publicada', 'nota': n['ementa'][:220], 'url': n['url'], 'diplomas': afeta})
                pend.append({'diploma': afeta[0] if afeta else None, 'ato': n['titulo'], 'url': n['url'], 'desde': agora.isoformat(timespec='seconds'),
                             'situacao': 'alteração publicada, compilação oficial pendente' if afeta else 'nova norma a avaliar para inclusão na base'})
        gravar('normas_vistas.json', (vistas or []) + [n for n in normas if n['id'] not in ids])
        gravar('pendencias.json', pend)
    if diario:
        props = congresso.proposicoes_camara(ano, MARCADORES_DOU)
        status['Câmara, proposições'] = 'ok' if props is not None else 'falha na leitura'
        if props is not None:
            gravar('proposicoes.json', props)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--diario', action='store_true', help='inclui busca de temas novos e súmulas')
    ap.add_argument('--sem-rede', action='store_true', help='só regenera os arquivos publicados')
    a = ap.parse_args()
    agora = datetime.now(timezone.utc)
    local = agora.astimezone(BRT)
    diario = a.diario or local.hour == 6
    semanal = diario and local.weekday() == 0  # segunda-feira: jurisprudência pelo Jusratio
    log, status, resumo = [], {}, {}
    if not a.sem_rede:
        limpar_pendencias(agora)
        resumo['dou'] = etapa_dou(agora, log, status)
        resumo['planalto'] = etapa_planalto(agora, log, status, completo=semanal)
        etapa_congresso(agora, log, status, diario)
        resumo['stj'] = etapa_stj(agora, log, status, diario)
        if diario:
            resumo['sumulas'] = etapa_sumulas(agora, log, status)
    ch = ler('changelog.json', []) + log
    gravar('changelog.json', ch[-2000:])
    if a.sem_rede:  # só regenera os arquivos publicados; preserva o registro da última coleta
        idx = construir(ler('ultima_execucao.json', {}).get('em') or agora.isoformat(timespec='seconds'))
        print(json.dumps({'regenerado': True, 'avisos': idx['avisos'][:10]}, ensure_ascii=False)); return
    gravar('fontes_status.json', {k: {'status': v, 'em': agora.isoformat(timespec='seconds')} for k, v in status.items()} | {k: v for k, v in ler('fontes_status.json', {}).items() if k not in status})
    gravar('ultima_execucao.json', {'em': agora.isoformat(timespec='seconds'), 'diario': diario, 'semanal': semanal, 'resumo': resumo, 'mudancas': len(log)})
    idx = construir(agora.isoformat(timespec='seconds'))
    print(json.dumps({'mudancas': len(log), 'resumo': resumo, 'status': status, 'avisos': idx['avisos'][:10]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
