"""Repositório, fontes, fixtures e ponte com o Mapa Normativo."""
import json, os, shutil, unittest

import apoio
import repositorio, normativo
import publicar


def escrever(raiz, rel, dados):
    cam = os.path.join(raiz, rel)
    os.makedirs(os.path.dirname(cam), exist_ok=True)
    json.dump(dados, open(cam, 'w'), ensure_ascii=False)


class Integridade(unittest.TestCase):
    def setUp(self):
        self.raiz = apoio.raiz_temporaria()

    def tearDown(self):
        shutil.rmtree(self.raiz)

    def test_conteudo_real_valido(self):
        erros, _ = repositorio.carregar(self.raiz).validar()
        self.assertEqual(erros, [])

    def test_chave_estrangeira_enum_e_travessao(self):
        p = os.path.join(self.raiz, 'conteudo', 'eleicoes', 'temas.json')
        temas = json.load(open(p))
        temas.append({'id': 'x', 'nome': 'Tema \u2014 com travessão', 'pai_id': 'inexistente'})
        json.dump(temas, open(p, 'w'))
        erros, _ = repositorio.carregar(self.raiz).validar()
        self.assertTrue(any('temas.x: pai_id aponta' in e for e in erros))
        self.assertTrue(any('travessão' in e for e in erros))

    def test_id_duplicado(self):
        p = os.path.join(self.raiz, 'conteudo', 'eleicoes', 'temas.json')
        temas = json.load(open(p)); temas.append(dict(temas[0])); json.dump(temas, open(p, 'w'))
        erros, _ = repositorio.carregar(self.raiz).validar()
        self.assertTrue(any('id duplicado' in e for e in erros))

    def test_dado_real_nao_aponta_para_fixture(self):
        p = os.path.join(self.raiz, 'conteudo', 'eleicoes', 'afirmacoes.json')
        a = json.load(open(p))
        a.append({'id': 'real-x', 'tipo': 'FACT', 'texto': 'Afirmação real.', 'status_revisao': 'REVIEWED', 'proposta_id': 'fx-ana-ir',
                  'criado_em': apoio.AGORA, 'atualizado_em': apoio.AGORA})
        json.dump(a, open(p, 'w'))
        erros, _ = repositorio.carregar(self.raiz).validar()
        self.assertTrue(any('dado real aponta para registro fictício' in e for e in erros))

    def test_fixture_nao_aponta_para_dado_real(self):
        p = os.path.join(self.raiz, 'conteudo', 'eleicoes', 'fixtures', 'afirmacao_fontes.json')
        a = json.load(open(p)); a.append({'id': 'fx-contaminada', 'afirmacao_id': 'fx-ana-ir--afirmacao', 'fonte_id': 'fonte-cf-planalto', 'relacao': 'MENTIONS'})
        json.dump(a, open(p, 'w'))
        erros, _ = repositorio.carregar(self.raiz).validar()
        self.assertTrue(any('fictício (DEVELOPMENT_FIXTURE) aponta para dado real' in e for e in erros))

    def test_fixture_nao_pode_se_declarar_real(self):
        p = os.path.join(self.raiz, 'conteudo', 'eleicoes', 'fixtures', 'partidos.json')
        a = json.load(open(p)); a[0]['origem_dado'] = 'OFFICIAL'; json.dump(a, open(p, 'w'))
        erros, _ = repositorio.carregar(self.raiz).validar()
        self.assertTrue(any('registro em fixtures/ com origem_dado OFFICIAL' in e for e in erros))

    def test_sincronizar_detecta_duplicidade_na_mesma_carga(self):
        b = repositorio.carregar(self.raiz)
        cont, _ = b.sincronizar('partidos', [{'id': 'p1', 'sigla': 'A'}, {'id': 'p1', 'sigla': 'A'}], apoio.AGORA)
        self.assertEqual(cont['created'] + cont['unchanged'], 2)
        self.assertEqual(len([r for r in b.tabelas['partidos'] if r['id'] == 'p1']), 1)


class Fontes(unittest.TestCase):
    def setUp(self):
        self.raiz = apoio.raiz_temporaria()

    def tearDown(self):
        shutil.rmtree(self.raiz)

    def test_proposta_e_afirmacao_sem_fonte_nao_sao_publicadas(self):
        b = repositorio.carregar(self.raiz)
        _, avisos = b.validar()
        self.assertTrue(any('fx-elisa-sem-fonte: proposta sem afirmação com fonte' in a for a in avisos))
        pub = publicar.Publicador(b, normativo.conferir_todas(b.tabelas['regras'])[1], apoio.AGORA)
        props = b.por_id('propostas')
        self.assertFalse(pub.publicavel(props['fx-elisa-sem-fonte']))
        self.assertTrue(pub.publicavel(props['fx-ana-ir']))
        self.assertIsNone(pub.afirmacao(b.por_id('afirmacoes')['fx-elisa-sem-fonte--afirmacao']))

    def test_afirmacao_com_varias_fontes_e_divergencia(self):
        b = repositorio.carregar(self.raiz)
        pub = publicar.Publicador(b, {}, apoio.AGORA)
        a = pub.afirmacao(b.por_id('afirmacoes')['fx-clara-ir--posicao'])
        self.assertEqual({f['relacao'] for f in a['fontes']}, {'SUPPORTS', 'CONTRADICTS'})
        self.assertTrue(a['divergencia'])
        self.assertEqual(len(pub.afirmacao(b.por_id('afirmacoes')['fx-clara-ir--afirmacao'])['fontes']), 2)

    def test_fonte_ficticia_leva_marca(self):
        b = repositorio.carregar(self.raiz)
        pub = publicar.Publicador(b, {}, apoio.AGORA)
        self.assertTrue(pub.fonte('fx-programa-presidente')['fixture'])
        self.assertNotIn('fixture', pub.fonte('fonte-cf-planalto'))


class PonteNormativa(unittest.TestCase):
    def art(self, linhas):
        return {'l': [[l, ''] for l in linhas], 'hash': 'h', 'r': 'Art. 1'}

    def test_localizadores(self):
        a = self.art(['Art. 1º Caput.', 'I - um;', 'II - dois:', 'a) letra a;', 'b) letra b;', 'III - três.', '§ 1º Parágrafo.', 'I - inciso do parágrafo.', '§ 2º Outro.', 'Parágrafo único. Fim.'])
        self.assertEqual(normativo.localizar(a, None), [0])
        self.assertEqual(normativo.localizar(a, 'II'), [2, 3, 4])
        self.assertEqual(normativo.localizar(a, 'II, b'), [4])
        self.assertEqual(normativo.localizar(a, '§ 1º, I'), [7])
        self.assertEqual(normativo.localizar(a, 'Parágrafo único'), [9])
        self.assertIsNone(normativo.localizar(a, 'IV'))
        self.assertIsNone(normativo.localizar(a, '§ 1º, II'))  # não atravessa para outro parágrafo
        self.assertIsNone(normativo.localizar(a, 'I, a'))

    def test_regras_reais_conferem_com_o_texto_vigente(self):
        regras = json.load(open(os.path.join(apoio.RAIZ, 'conteudo', 'eleicoes', 'regras.json')))
        erros, info = normativo.conferir_todas(regras)
        self.assertEqual(erros, [])
        self.assertIn('Presidente da República', ' '.join(info['cf-60-ii']['trecho_vigente']))

    def test_regra_invalida_e_recusada(self):
        e, _ = normativo.conferir_regra({'id': 'x', 'diploma_id': 'cf', 'dispositivo': 'cf.9999', 'rotulo': 'x', 'resumo': 'x'})
        self.assertTrue(e and 'não existe' in e[0])
        e, _ = normativo.conferir_regra({'id': 'y', 'diploma_id': 'cf', 'dispositivo': 'cf.84', 'localizador': 'XC', 'rotulo': 'x', 'resumo': 'x'})
        self.assertTrue(e and 'localizador' in e[0])


class Publicacao(unittest.TestCase):
    def test_urls_publicadas(self):
        self.assertEqual(normativo.artigo('cf.84')[1]['r'], 'Art. 84')
        url = __import__('cliente').PAGINA_CANDIDATO.format(regiao='SUL', uf='SC', eleicao='20322002026', id=1, ano=2026)
        self.assertEqual(url, 'https://divulgacandcontas.tse.jus.br/divulga/#/candidato/SUL/SC/20322002026/1/2026/SC')
        self.assertEqual(__import__('cliente').nome_snapshot('https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura/listar/2026/SC/1/3/candidatos'),
                         'candidatura_listar_2026_SC_1_3_candidatos.json')


if __name__ == '__main__':
    unittest.main()
