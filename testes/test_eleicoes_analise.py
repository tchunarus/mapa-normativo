"""Classificação de competência (AnalisadorPorRegras) e revisão (AnalisadorRevisado)."""
import json, os, shutil, unittest

import apoio
import repositorio, normativo
from analise import Contexto
from analise.regras import AnalisadorPorRegras
from analise.revisao import AnalisadorRevisado
from analise.llm import AnalisadorLLM
import analisar

ESPERADO = {  # proposta fictícia -> (classificação, competência direta, pode iniciar, instrumento)
    'fx-ana-ir': ('LEGISLATION_REQUIRED', 'NO', 'YES', 'lei-ordinaria-federal'),
    'fx-ana-ipi': ('DIRECT_POWER', 'YES', 'YES', 'decreto-federal'),
    'fx-ana-reeleicao': ('CONSTITUTIONAL_AMENDMENT_REQUIRED', 'NO', 'YES', 'pec'),
    'fx-ana-iptu': ('MUNICIPAL_DEPENDENCY', 'NO', 'NO', 'lei-municipal'),
    'fx-ana-vaga': ('INSUFFICIENT_INFORMATION', 'NOT_APPLICABLE', 'NOT_APPLICABLE', None),
    'fx-bruno-ipva': ('LEGISLATION_REQUIRED', 'NO', 'YES', 'lei-estadual'),
    'fx-bruno-policiamento': ('DIRECT_POWER', 'YES', 'YES', 'ato-administrativo-estadual'),
    'fx-bruno-hospital': ('SHARED_COMPETENCE', 'YES', 'YES', 'ato-administrativo-estadual'),
    'fx-bruno-inss': ('FEDERAL_DEPENDENCY', 'NO', 'NO', 'lei-ordinaria-federal'),
    'fx-clara-ir': ('LEGISLATION_REQUIRED', 'NO', 'YES', 'lei-ordinaria-federal'),
    'fx-clara-pec': ('CONSTITUTIONAL_AMENDMENT_REQUIRED', 'NO', 'DEPENDS', 'pec'),
    'fx-clara-ipva': ('STATE_DEPENDENCY', 'NO', 'NO', 'lei-estadual'),
    'fx-davi-policlinica': ('OTHER_BRANCH_DEPENDENCY', 'NO', 'NO', 'ato-administrativo-federal'),
    'fx-davi-penas': ('LEGISLATION_REQUIRED', 'NO', 'YES', 'lei-ordinaria-federal'),
    'fx-davi-ipi': ('OUTSIDE_OFFICE_COMPETENCE', 'NO', 'NO', 'decreto-federal'),
    'fx-elisa-animais': ('SHARED_COMPETENCE', 'NO', 'YES', 'lei-estadual'),
    'fx-elisa-pec': ('FEDERAL_DEPENDENCY', 'NO', 'DEPENDS', 'pec'),
    'fx-elisa-tarifa': ('MUNICIPAL_DEPENDENCY', 'NO', 'NO', 'ato-administrativo-municipal'),
}


class Classificacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raiz = apoio.raiz_temporaria()
        cls.banco = repositorio.carregar(cls.raiz)
        erros, info = normativo.conferir_todas(cls.banco.tabelas['regras'])
        assert not erros, erros
        cls.ctx = Contexto(cls.banco, info)
        cls.an = AnalisadorPorRegras()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.raiz)

    def analisar(self, pid, **mudancas):
        p = dict(self.ctx.t['propostas'][pid], **mudancas)
        cargo = self.ctx.t['cargos'][self.ctx.t['candidaturas'][p['candidatura_id']]['cargo_id']]
        return self.an.analisar(p, cargo, self.ctx)

    def test_todas_as_classificacoes(self):
        vistas = set()
        for pid, (cls_, direta, inicia, instr) in ESPERADO.items():
            with self.subTest(pid):
                a = self.analisar(pid).analise
                self.assertEqual((a['classificacao'], a['competencia_direta'], a['pode_iniciar'], a.get('instrumento_id')), (cls_, direta, inicia, instr))
                self.assertEqual(a['status_revisao'], 'AUTO_GENERATED')
                self.assertNotIn('\u2014', a['explicacao'])
                self.assertNotIn('..', a['explicacao'])
                vistas.add(cls_)
        self.assertEqual(vistas, set(__import__('esquema').CLASSIFICACAO))

    def test_dependencias_do_projeto_de_lei_presidencial(self):
        r = self.analisar('fx-ana-ir')
        obrig = [d['instituicao_id'] for d in r.dependencias if not d.get('condicional')]
        self.assertEqual(obrig, ['camara', 'senado'])  # a sanção é do próprio Presidente
        self.assertEqual([d['instituicao_id'] for d in r.dependencias if d.get('condicional')], ['congresso'])
        self.assertEqual([x['instrumento_id'] for x in r.alternativas], ['medida-provisoria'])
        self.assertIn('sancioná-lo ou vetá-lo', r.analise['explicacao'])

    def test_pec_nao_passa_por_sancao(self):
        r = self.analisar('fx-ana-reeleicao')
        self.assertIn('mesas-congresso', [d['instituicao_id'] for d in r.dependencias])
        self.assertNotIn('presidencia', [d['instituicao_id'] for d in r.dependencias])
        self.assertTrue(any('não passa por sanção' in o for o in r.analise['observacoes']))
        self.assertIn('cf-60-ii', [f['regra_id'] for f in r.fundamentos])

    def test_fundamentos_existem_e_guardam_hash(self):
        regras = self.ctx.t['regras']
        for pid in ESPERADO:
            for f in self.analisar(pid).fundamentos:
                self.assertIn(f['regra_id'], regras)
                if not regras[f['regra_id']].get('fora_da_base'):
                    self.assertTrue(f['hash_dispositivo'])

    def test_constituicao_estadual_fora_da_base_reduz_confianca(self):
        self.assertEqual(self.analisar('fx-bruno-ipva').analise['confianca'], 'MEDIUM')
        self.assertEqual(self.analisar('fx-ana-ir').analise['confianca'], 'HIGH')

    def test_mudanca_na_entrada_muda_o_hash(self):
        a = self.analisar('fx-ana-ir').analise['hash_entrada']
        b = self.analisar('fx-ana-ir', natureza_medida='COMPLEMENTARY_LAW_CHANGE')
        self.assertNotEqual(a, b.analise['hash_entrada'])
        self.assertEqual(b.analise['instrumento_id'], 'lei-complementar-federal')
        self.assertEqual(b.alternativas, [])  # MP é alternativa só ao projeto de lei ordinária (CF, art. 62, § 1º, III)
        self.assertEqual(a, self.analisar('fx-ana-ir').analise['hash_entrada'])  # determinístico

    def test_sem_materia_e_insuficiente(self):
        r = self.analisar('fx-ana-ir', materia_id=None)
        self.assertEqual(r.analise['classificacao'], 'INSUFFICIENT_INFORMATION')
        self.assertEqual(r.analise['confianca'], 'LOW')

    def test_llm_ainda_nao_implementado(self):
        with self.assertRaises(NotImplementedError):
            AnalisadorLLM().analisar({}, {}, self.ctx)


class Revisao(unittest.TestCase):
    def setUp(self):
        self.raiz = apoio.raiz_temporaria()
        b = repositorio.carregar(self.raiz)
        _, info = normativo.conferir_todas(b.tabelas['regras'])
        self.ctx = Contexto(b, info)
        self.p = self.ctx.t['propostas']['fx-ana-ir']
        self.cargo = self.ctx.t['cargos']['presidente']
        self.hash = AnalisadorPorRegras().analisar(self.p, self.cargo, self.ctx).analise['hash_entrada']

    def tearDown(self):
        shutil.rmtree(self.raiz)

    def rev(self, **kw):
        base = {'id': 'r1', 'analise_id': 'fx-ana-ir--presidente', 'status': 'REVIEWED', 'revisor': 'teste', 'revisado_em': apoio.AGORA,
                'hash_entrada_revisada': self.hash}
        base.update(kw)
        return AnalisadorRevisado(AnalisadorPorRegras(), [base]).analisar(self.p, self.cargo, self.ctx).analise

    def test_revisada(self):
        self.assertEqual(self.rev()['status_revisao'], 'REVIEWED')

    def test_corrigida_guarda_o_original(self):
        a = self.rev(status='CORRECTED', correcao={'explicacao': 'Texto corrigido pela revisão.'})
        self.assertEqual(a['status_revisao'], 'CORRECTED')
        self.assertEqual(a['explicacao'], 'Texto corrigido pela revisão.')
        self.assertIn('O Presidente tem meios', a['original']['explicacao'])

    def test_revisao_desatualizada_volta_a_pendente(self):
        a = self.rev(hash_entrada_revisada='outro')
        self.assertEqual(a['status_revisao'], 'PENDING_REVIEW')
        self.assertTrue(any('desatualizada' in o for o in a['observacoes']))


class Persistencia(unittest.TestCase):
    def test_analisar_grava_e_e_idempotente(self):
        raiz = apoio.raiz_temporaria()
        try:
            log = analisar.analisar_tudo(raiz, apoio.AGORA)
            self.assertEqual((log['errors'], log['created']), (0, len(ESPERADO) + 1))
            log = analisar.analisar_tudo(raiz, apoio.DEPOIS)
            self.assertEqual((log['created'], log['updated'], log['unchanged']), (0, 0, len(ESPERADO) + 1))
            b = repositorio.carregar(raiz)
            self.assertEqual(b.validar()[0], [])
            a = b.por_id('analises')['fx-ana-ir--presidente']
            self.assertEqual(a['criado_em'], apoio.AGORA)
            self.assertEqual(a['origem_dado'], 'DEVELOPMENT_FIXTURE')
        finally:
            shutil.rmtree(raiz)


if __name__ == '__main__':
    unittest.main()
