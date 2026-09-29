"""Integração com o TSE: minimização, parser, normalização, sincronização e atualização."""
import json, os, shutil, unittest

import apoio
import cliente, parser, normalizador, sincronizar, repositorio


class Minimizacao(unittest.TestCase):
    def test_detalhe_descarta_dados_pessoais(self):
        bruto = {'id': 1, 'numero': 22, 'nomeUrna': 'FULANO', 'cpf': '00000000000', 'tituloEleitor': '1', 'dataDeNascimento': '1980-01-01',
                 'descricaoCorRaca': 'X', 'descricaoEstadoCivil': 'Y', 'emails': ['a@b'], 'bens': [{}],
                 'arquivos': [{'idArquivo': 9, 'nome': 'certidao.pdf', 'codTipo': '11'}, {'idArquivo': 10, 'nome': 'plano.pdf', 'codTipo': '5'}],
                 'vices': [{'sq_CANDIDATO': 2, 'nm_URNA': 'VICE', 'cpf': '1', 'ds_CARGO': 'Vice-governador'}]}
        corpo, campos = cliente.reduzir(cliente.BUSCAR.format(ano=2026, uf='SC', eleicao='1', id=1), bruto)
        texto = json.dumps(corpo)
        for proibido in ('cpf', 'tituloEleitor', 'dataDeNascimento', 'descricaoCorRaca', 'descricaoEstadoCivil', 'emails', 'bens', 'certidao'):
            self.assertNotIn(proibido, texto)
        self.assertEqual([a['idArquivo'] for a in corpo['arquivos']], [10])
        self.assertTrue(campos)

    def test_lista_mantem_so_campos_da_lista_branca(self):
        corpo, _ = cliente.reduzir(cliente.LISTAR.format(ano=2026, uf='SC', eleicao='1', cargo=3),
                                   {'candidatos': [{'id': 1, 'numero': 1, 'nomeUrna': 'A', 'tituloEleitor': '9', 'partido': {'sigla': 'PX', 'numero': 0}}]})
        self.assertNotIn('tituloEleitor', corpo['candidatos'][0])
        self.assertEqual(corpo['candidatos'][0]['partido'], {'sigla': 'PX'})


class Parser(unittest.TestCase):
    def test_itens_defeituosos_e_repetidos_viram_erro(self):
        snap = {'url': 'u', 'corpo': {'candidatos': [apoio.item_lista(1, 10, 'A'), {'id': 2, 'numero': None, 'nomeUrna': 'B'}, apoio.item_lista(1, 10, 'A')]}}
        itens, erros = parser.candidatos_da_lista(snap)
        self.assertEqual(len(itens), 1)
        self.assertEqual(len(erros), 2)

    def test_resposta_sem_lista_falha(self):
        with self.assertRaises(parser.ErroFormato):
            parser.candidatos_da_lista({'url': 'u', 'corpo': {'erro': 'x'}})


class Normalizacao(unittest.TestCase):
    CTX = {'eleicao_id': '2026-geral', 'cargo_id': 'governador', 'cargo_eleicao_id': '2026-sc-governador', 'ente': 'SC', 'ano': 2026,
           'uf': 'SC', 'tse_eleicao': '20322002026', 'fonte_lista_id': 'tse-lista-x'}

    def test_nome_de_exibicao(self):
        self.assertEqual(normalizador.nome_exibicao('BRUNO PEDREIRO DO PCO', {'PCO'}), 'Bruno Pedreiro do PCO')
        self.assertEqual(normalizador.nome_exibicao('MARIA DAS DORES DE SOUZA'), 'Maria das Dores de Souza')
        self.assertEqual(normalizador.nome_exibicao("JOANA D'ARC SILVA-COSTA"), "Joana D'Arc Silva-Costa")
        self.assertEqual(normalizador.nome_exibicao('JOÃO NOVO', {'NOVO'}), 'João Novo')

    def test_situacoes(self):
        self.assertEqual(normalizador.situacao('Deferido'), ('DEFERIDO', True))
        self.assertEqual(normalizador.situacao('Indeferido em prazo recursal ou com recurso'), ('INDEFERIDO_COM_RECURSO', True))
        self.assertEqual(normalizador.situacao('Renúncia'), ('RENUNCIA', True))
        self.assertEqual(normalizador.situacao('Algo novo'), ('OUTRO', False))

    def test_candidatura_com_detalhe(self):
        item = apoio.item_lista(240002553718, 29, 'FULANO DO PX', sigla='PX')
        det = dict(item, ocupacao='Advogado', grauInstrucao='Superior completo', nomeMunicipioNascimento='SÃO JOSÉ', sgUfNascimento='SC',
                   fotoUrl='https://divulgacandcontas.tse.jus.br/f.jpg', fotoUrlPublicavel=True, partido={'sigla': 'PX', 'numero': 91, 'nome': 'PARTIDO X'},
                   arquivos=[{'idArquivo': 5, 'nome': 'plano.pdf', 'codTipo': '5'}], vices=[{'nm_URNA': 'VICE X', 'ds_CARGO': 'Vice-governador', 'sg_PARTIDO': 'PX'}])
        snap = {'url': cliente.BUSCAR.format(ano=2026, uf='SC', eleicao='20322002026', id=240002553718), 'capturado_em': apoio.AGORA, 'sha256': 'a' * 64}
        pessoa, cand, part, fontes, avisos = normalizador.normalizar(item, det, snap, self.CTX, {'PX'})
        self.assertEqual(pessoa['nome_urna'], 'Fulano do PX')
        self.assertEqual(pessoa['nome_urna_oficial'], 'FULANO DO PX')
        self.assertEqual(pessoa['naturalidade'], 'São José/SC')
        self.assertEqual(cand['id'], 'tse-240002553718')
        self.assertEqual(cand['partido_id'], 'partido-px')
        self.assertEqual(part['nome'], 'Partido X')
        self.assertEqual(cand['vices'][0]['nome_urna'], 'Vice X')
        self.assertIsNone(cand['coligacao'])  # coligação igual à sigla é partido isolado
        self.assertEqual({f['tipo'] for f in fontes}, {'TSE', 'CANDIDATE_DOCUMENT'})
        self.assertEqual(cand['proposta_governo_fonte_id'], 'tse-documento-5')
        self.assertFalse(avisos)

    def test_foto_nao_publicavel_e_situacao_desconhecida(self):
        item = apoio.item_lista(1, 22, 'A', situacao='Situação inédita')
        _, cand, _, _, avisos = normalizador.normalizar(item, None, None, self.CTX)
        self.assertEqual(cand['situacao'], 'OUTRO')
        self.assertEqual(len(avisos), 1)
        self.assertIsNone(cand['foto_url'])
        self.assertEqual(cand['fonte_id'], 'tse-lista-x')


class Sincronizacao(unittest.TestCase):
    def setUp(self):
        self.raiz = apoio.raiz_temporaria(com_fixtures=False)
        self.snaps = os.path.join(self.raiz, 'snapshots')

    def tearDown(self):
        shutil.rmtree(self.raiz)

    def rodar(self, por_cargo, agora):
        apoio.gravar_snapshots(self.snaps, por_cargo)
        return sincronizar.sincronizar('2026-geral', cliente.TransporteSnapshot(self.snaps), 'nenhum', raiz=self.raiz, agora=agora)

    def test_carga_atualizacao_ausencia_e_log(self):
        base = {('SC', 3): [apoio.item_lista(10, 22, 'A'), apoio.item_lista(11, 55, 'B')], ('SC', 7): [apoio.item_lista(20, 22123, 'C')]}
        log = self.rodar(base, apoio.AGORA)
        self.assertEqual((log['fetched'], log['created'], log['updated'], log['unchanged'], log['errors']), (3, 3, 0, 0, 0))
        log = self.rodar(base, apoio.DEPOIS)
        self.assertEqual((log['created'], log['updated'], log['unchanged']), (0, 0, 3))
        mudou = {('SC', 3): [apoio.item_lista(10, 22, 'A', situacao='Renúncia')], ('SC', 7): base[('SC', 7)]}
        log = self.rodar(mudou, apoio.DEPOIS)
        self.assertEqual((log['updated'], log['unchanged'], log['missing']), (1, 1, 1))
        banco = repositorio.carregar(self.raiz)
        c = banco.por_id('candidaturas')
        self.assertEqual(c['tse-10']['situacao'], 'RENUNCIA')
        self.assertEqual(c['tse-11']['ausente_desde'], apoio.DEPOIS)  # não é apagada
        self.assertEqual(c['tse-10']['criado_em'], apoio.AGORA)
        mud = json.load(open(os.path.join(self.raiz, 'estado', 'eleicoes', 'mudancas.json')))
        alt = [m for m in mud if m['tipo'] == 'atualizado' and m['id'] == 'tse-10'][0]
        self.assertEqual(alt['antes']['situacao'], 'DEFERIDO')
        self.assertEqual(len(banco.tabelas['ingestoes']), 3)

    def test_numero_repetido_por_substituicao_nao_bloqueia(self):
        log = self.rodar({('SC', 7): [apoio.item_lista(1, 25000, 'A', situacao='Renúncia'), apoio.item_lista(2, 25000, 'B')]}, apoio.AGORA)
        self.assertEqual(log['errors'], 0)
        _, avisos = repositorio.carregar(self.raiz).validar()
        self.assertTrue(any('25000 repetido' in a for a in avisos))

    def test_falha_de_transporte_e_registrada(self):
        log = sincronizar.sincronizar('2026-geral', cliente.TransporteSnapshot(os.path.join(self.raiz, 'vazio')), 'nenhum',
                                      raiz=self.raiz, agora=apoio.AGORA)
        self.assertEqual(log['errors'], 5)
        self.assertEqual(log['fetched'], 0)
        self.assertTrue(os.path.exists(os.path.join(self.raiz, 'estado', 'eleicoes', 'ingestoes.json')))


if __name__ == '__main__':
    unittest.main()
