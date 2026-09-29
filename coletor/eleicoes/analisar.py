"""Roda a análise de competência de todas as propostas e grava o resultado estruturado.

    python3 coletor/eleicoes/analisar.py

Etapas: confere cada fundamento contra o Mapa Normativo (dispositivo existente, não
revogado, localizador presente); analisa cada proposta com o AnalisadorPorRegras;
aplica as revisões gravadas (AnalisadorRevisado); valida a integridade; grava
estado/eleicoes/analises.json, analise_regras.json, analise_alternativas.json e
dependencias.json; registra a execução em estado/eleicoes/ingestoes.json.

Se algum fundamento não conferir com o texto vigente, nada é gravado.
"""
import json, os, sys
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))
import repositorio, normativo  # noqa: E402
from analise import Contexto  # noqa: E402
from analise.regras import AnalisadorPorRegras  # noqa: E402
from analise.revisao import AnalisadorRevisado  # noqa: E402

FILHAS = (('fundamentos', 'analise_regras'), ('alternativas', 'analise_alternativas'), ('dependencias', 'dependencias'))


def analisar_tudo(raiz=repositorio.RAIZ, agora=None, pasta_diplomas=normativo.DIPLOMAS, registrar_sem_mudanca=True):
    """`registrar_sem_mudanca=False` (usado pela rotina horária) não grava no log as
    execuções em que nenhuma análise mudou, para não gerar commit sem conteúdo."""
    agora = agora or datetime.now(timezone.utc).isoformat(timespec='seconds')
    banco = repositorio.carregar(raiz)
    log = {'id': f'analise-{agora}', 'fonte': 'Mapa Eleitoral', 'rotulo': 'Análise de competência', 'iniciado_em': agora,
           'transporte': 'local', 'fetched': 0, 'created': 0, 'updated': 0, 'unchanged': 0, 'missing': 0, 'errors': 0,
           'erros': [], 'avisos': [], 'snapshots': [], 'origem_dado': 'DERIVED'}
    erros_regras, info = normativo.conferir_todas(banco.tabelas['regras'], pasta_diplomas)
    if erros_regras:
        log['erros'] = erros_regras
    else:
        ctx = Contexto(banco, info)
        analisador = AnalisadorRevisado(AnalisadorPorRegras(), banco.tabelas['revisoes'])
        cand = banco.por_id('candidaturas')
        cargos = banco.por_id('cargos')
        anteriores = banco.por_id('analises')
        saida = {'analises': []} | {t: [] for _, t in FILHAS}
        for p in sorted(banco.tabelas['propostas'], key=lambda x: x['id']):
            c = cand.get(p['candidatura_id'])
            if not c:
                log['erros'].append(f'propostas.{p["id"]}: candidatura {p["candidatura_id"]} inexistente'); continue
            res = analisador.analisar(p, cargos[c['cargo_id']], ctx)
            a = res.analise
            ant = anteriores.get(a['id'])
            a['criado_em'] = ant['criado_em'] if ant else agora
            a['atualizado_em'] = agora
            origem = p.get('origem_dado') or 'DERIVED'
            a['origem_dado'] = origem if origem == repositorio.FIXTURE else 'DERIVED'
            saida['analises'].append(a)
            for attr, tabela in FILHAS:
                for linha in getattr(res, attr):
                    linha['origem_dado'] = a['origem_dado']
                    saida[tabela].append(linha)
        log['fetched'] = len(saida['analises'])
        for tabela, regs in saida.items():
            ids = {r['id'] for r in regs}
            antigos = [r for r in banco.tabelas[tabela] if r['_origem'] == 'estado' and r['id'] not in ids]
            cont, _ = banco.sincronizar(tabela, regs, agora)
            if tabela == 'analises':
                for k in ('created', 'updated', 'unchanged'):
                    log[k] = cont[k]
            # análise de proposta excluída não é mantida como vigente: sai da tabela derivada
            banco.tabelas[tabela] = [r for r in banco.tabelas[tabela] if r not in antigos]
            if tabela == 'analises':
                log['missing'] = len(antigos)
        erros, _ = banco.validar()
        erros = [e for e in erros if e.split('.')[0] in ('analises', 'analise_regras', 'analise_alternativas', 'dependencias')]
        if erros:
            log['erros'].extend(erros[:50]); log['avisos'].append('análises não gravadas: a validação de integridade falhou')
        else:
            for tabela in saida:
                banco.gravar(tabela)
    log['errors'] = len(log['erros'])
    log['concluido_em'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    if registrar_sem_mudanca or log['errors'] or log['created'] or log['updated'] or log['missing']:
        repositorio.registrar_ingestao(banco, log)
    return log


if __name__ == '__main__':
    lg = analisar_tudo()
    print(json.dumps({k: lg[k] for k in ('rotulo', 'fetched', 'created', 'updated', 'unchanged', 'missing', 'errors')} | {'erros': lg['erros'][:10]}, ensure_ascii=False))
    sys.exit(1 if lg['errors'] else 0)
