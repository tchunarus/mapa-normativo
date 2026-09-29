"""Esquema de dados do Mapa Eleitoral.

O projeto não tem banco de dados: é um site estático gerado por scripts Python. O
papel do banco é cumprido por tabelas normalizadas em JSON (uma lista de registros
por arquivo), com o esquema declarado aqui e verificado por `repositorio.py`: campos
obrigatórios, tipos, valores de enumeração, chaves estrangeiras, unicidade e a regra
de isolamento das fixtures de desenvolvimento.

Onde cada tabela vive:

- `conteudo/eleicoes/<tabela>.json`: conteúdo curado (cargos, competências,
  fundamentos jurídicos, instrumentos, temas, propostas, afirmações, revisões).
- `estado/eleicoes/<tabela>.json`: dados gerados por script (candidaturas vindas do
  TSE, análises produzidas pelo analisador, log de ingestão). Não se editam à mão.
- `conteudo/eleicoes/fixtures/<tabela>.json`: dados fictícios de desenvolvimento
  (DEVELOPMENT_FIXTURE). Todo registro dali recebe `origem_dado` DEVELOPMENT_FIXTURE e
  só pode apontar para outros registros fictícios ou para dados de referência
  (cargos, regras, competências etc.), nunca para candidatura ou fonte reais.

Correspondência com as entidades do projeto: Election = eleicoes; Office = cargos
(e cargos_eleicao, o cargo disputado numa eleição e circunscrição); Candidate =
candidatos (pessoa); CandidateOffice = candidaturas; Party = partidos; Proposal =
propostas; ProposalTheme = temas + proposta_temas; Source = fontes; Claim =
afirmacoes; ClaimSource = afirmacao_fontes; LegalRule = regras; GovernmentCompetence
= competencias; ProposalCompetenceAnalysis = analises; ProposalDependency =
dependencias; State e Municipality = registro ENTES de coletor/fontes.py, o mesmo
usado pelo Mapa Normativo (não há segunda tabela de entes).

Os nomes dos campos seguem o português do restante do código; os valores das
enumerações seguem os nomes definidos na especificação do Mapa Eleitoral.
"""

VERSAO_ESQUEMA = 1

# ------------------------------------------------------------------ enumerações
ORIGEM_DADO = ('OFFICIAL', 'CURATED', 'DERIVED', 'DEVELOPMENT_FIXTURE')
TIPO_FONTE = ('TSE', 'LEGISLATION', 'COURT_DECISION', 'LEGISLATIVE_RECORD', 'GOVERNMENT_DOCUMENT',
              'CANDIDATE_DOCUMENT', 'CANDIDATE_STATEMENT', 'INTERVIEW', 'NEWS', 'FACT_CHECK', 'POLL',
              'ACADEMIC', 'OTHER')
TIPO_ELEICAO = ('GENERAL', 'MUNICIPAL', 'DEMONSTRATION')
ESFERA = ('FEDERAL', 'STATE', 'MUNICIPAL')
NIVEL_COMPETENCIA = ('FEDERAL', 'STATE', 'MUNICIPAL', 'SHARED')
PODER = ('EXECUTIVE', 'LEGISLATIVE', 'JUDICIARY')
SISTEMA_ELEITORAL = ('MAJORITARIAN', 'PROPORTIONAL')
# O tipo de competência da especificação mistura duas dimensões independentes: o que
# se faz (natureza) e com quem se divide (titularidade). Aqui ficam separadas.
NATUREZA_COMPETENCIA = ('MATERIAL', 'LEGISLATIVE', 'ADMINISTRATIVE', 'BUDGETARY', 'REGULATORY')
TITULARIDADE_COMPETENCIA = ('EXCLUSIVE', 'PRIVATE', 'COMMON', 'CONCURRENT')
CATEGORIA_COMPETENCIA = ('SUBJECT_MATTER', 'OFFICE_POWER')
MODO_EXERCICIO = ('EXERCISES', 'PARTICIPATES')
CLASSIFICACAO = ('DIRECT_POWER', 'LEGISLATION_REQUIRED', 'CONSTITUTIONAL_AMENDMENT_REQUIRED',
                 'SHARED_COMPETENCE', 'FEDERAL_DEPENDENCY', 'STATE_DEPENDENCY', 'MUNICIPAL_DEPENDENCY',
                 'OTHER_BRANCH_DEPENDENCY', 'OUTSIDE_OFFICE_COMPETENCE', 'INSUFFICIENT_INFORMATION')
STATUS_REVISAO = ('AUTO_GENERATED', 'PENDING_REVIEW', 'REVIEWED', 'CORRECTED')
CONFIANCA = ('HIGH', 'MEDIUM', 'LOW')
SIM_NAO = ('YES', 'NO', 'PARTIAL', 'DEPENDS', 'NOT_APPLICABLE')
TIPO_AFIRMACAO = ('PROPOSAL', 'BIOGRAPHICAL', 'POSITION', 'STATEMENT', 'FACT', 'COMPUTED')
RELACAO_FONTE = ('SUPPORTS', 'CONTRADICTS', 'CORRECTS', 'MENTIONS')
NATUREZA_MEDIDA = ('CONSTITUTIONAL_CHANGE', 'COMPLEMENTARY_LAW_CHANGE', 'LEGAL_CHANGE', 'EXECUTIVE_REGULATION',
                   'ADMINISTRATIVE_ACTION', 'PUBLIC_WORK_OR_SERVICE', 'BUDGET_ALLOCATION', 'OVERSIGHT',
                   'UNSPECIFIED')
PAPEL_ETAPA = ('INITIATIVE', 'DELIBERATION', 'SANCTION_VETO', 'PROMULGATION', 'EXECUTION', 'REGULATION',
               'BUDGET_AMENDMENT', 'VETO_REVIEW')
TIPO_DEPENDENCIA = ('LEGISLATIVE_APPROVAL', 'EXECUTIVE_SANCTION', 'CONSTITUTIONAL_PROMULGATION',
                    'OTHER_ENTITY_ACTION', 'OTHER_BRANCH_ACTION', 'BUDGET_ALLOCATION',
                    'INTERGOVERNMENTAL_COOPERATION', 'REGULATION')
PAPEL_FUNDAMENTO = ('COMPETENCE', 'INSTRUMENT', 'INITIATIVE', 'PROCEDURE', 'LIMIT')
SITUACAO_CANDIDATURA = ('DEFERIDO', 'DEFERIDO_COM_RECURSO', 'INDEFERIDO', 'INDEFERIDO_COM_RECURSO',
                        'AGUARDANDO_JULGAMENTO', 'CANCELADO', 'CASSADO', 'RENUNCIA', 'FALECIDO', 'NAO_CONHECIDO',
                        'OUTRO')
TIPO_INSTITUICAO = ('SINGLE_OFFICE', 'COLLEGIATE', 'ENTITY')


class Campo:
    """tipo: 'str', 'int', 'bool', 'data' (AAAA-MM-DD), 'datahora' (ISO 8601), 'dict', 'lista'.
    fk: nome da tabela referenciada (para 'lista', cada item é uma chave). enum: tupla."""

    def __init__(self, tipo='str', obrigatorio=False, enum=None, fk=None, ente=False, max_len=None):
        self.tipo, self.obrigatorio, self.enum, self.fk, self.ente, self.max_len = tipo, obrigatorio, enum, fk, ente, max_len


class Tabela:
    """origens: onde os registros ficam ('conteudo', 'estado', 'fixtures'); uma tabela pode
    reunir registros de mais de uma origem (ex.: fontes curadas e fontes do TSE).
    unicos: tuplas de campos que não podem se repetir; indices: campos pelos quais a
    publicação agrupa registros (os "índices" deste banco em arquivo)."""

    def __init__(self, nome, campos, origens=('conteudo',), unicos=(), indices=(), gerada=False):
        self.nome, self.campos, self.origens, self.unicos, self.indices, self.gerada = nome, campos, origens, unicos, indices, gerada
        self.campos.setdefault('id', Campo(obrigatorio=True))
        self.campos.setdefault('origem_dado', Campo(enum=ORIGEM_DADO))


C = Campo
CF = ('conteudo', 'fixtures')

TABELAS = {t.nome: t for t in [
    # ---------------------------------------------------------- referência jurídica
    Tabela('instituicoes', {
        'nome': C(obrigatorio=True), 'artigo': C(obrigatorio=True, enum=('o', 'a', 'os', 'as')), 'sigla': C(),
        'esfera': C(obrigatorio=True, enum=ESFERA),
        'poder': C(enum=PODER), 'ente': C(obrigatorio=True, ente=True), 'tipo': C(obrigatorio=True, enum=TIPO_INSTITUICAO),
        'descricao': C(max_len=600),
    }),
    Tabela('regras', {  # LegalRule: ponte para o dispositivo do Mapa Normativo
        'diploma_id': C(obrigatorio=True), 'dispositivo': C(), 'localizador': C(), 'rotulo': C(obrigatorio=True),
        'resumo': C(obrigatorio=True, max_len=400), 'fora_da_base': C('bool'), 'norma': C(), 'url': C(), 'observacao': C(max_len=600),
    }, unicos=[('dispositivo', 'localizador')]),
    Tabela('instrumentos', {
        'nome': C(obrigatorio=True), 'nome_curto': C(obrigatorio=True), 'esfera': C(obrigatorio=True, enum=ESFERA),
        'descricao': C(obrigatorio=True, max_len=700), 'regra_id': C(fk='regras'), 'exige_sancao': C('bool'),
        'quorum': C(max_len=300), 'ordem': C('int'), 'alternativa_a': C(fk='instrumentos'), 'nota_alternativa': C(max_len=400),
    }),
    Tabela('instrumento_etapas', {
        'instrumento_id': C(obrigatorio=True, fk='instrumentos'), 'ordem': C('int', obrigatorio=True),
        'papel': C(obrigatorio=True, enum=PAPEL_ETAPA), 'instituicao_id': C(obrigatorio=True, fk='instituicoes'),
        'descricao': C(obrigatorio=True, max_len=500), 'regra_id': C(fk='regras'), 'condicional': C('bool'),
        'exercicio_individual': C('bool'),
    }, unicos=[('instrumento_id', 'ordem', 'instituicao_id')], indices=('instrumento_id',)),
    Tabela('temas', {'nome': C(obrigatorio=True), 'descricao': C(max_len=400), 'pai_id': C(fk='temas'), 'ordem': C('int')}),
    Tabela('materias', {
        'nome': C(obrigatorio=True), 'descricao': C(max_len=500), 'tema_id': C(fk='temas'),
        'nivel': C(obrigatorio=True, enum=NIVEL_COMPETENCIA), 'exige_lei_complementar': C('bool'),
        'regulamentavel_por_decreto': C('bool'), 'observacao': C(max_len=600),
        'iniciativa_reservada_a': C(fk='instituicoes'), 'regra_iniciativa_id': C(fk='regras'),
        'regra_limite_ids': C('lista', fk='regras'),
    }),
    Tabela('competencias', {  # GovernmentCompetence
        'categoria': C(obrigatorio=True, enum=CATEGORIA_COMPETENCIA), 'nivel': C(obrigatorio=True, enum=NIVEL_COMPETENCIA),
        'autoridade_id': C(obrigatorio=True, fk='instituicoes'), 'materia_id': C(fk='materias'),
        'natureza': C(obrigatorio=True, enum=NATUREZA_COMPETENCIA), 'titularidade': C(enum=TITULARIDADE_COMPETENCIA),
        'regra_id': C(obrigatorio=True, fk='regras'), 'instrumento_id': C(fk='instrumentos'),
        'descricao': C(obrigatorio=True, max_len=600),
    }, indices=('materia_id', 'autoridade_id')),
    # ---------------------------------------------------------- eleições e cargos
    Tabela('eleicoes', {
        'nome': C(obrigatorio=True), 'ano': C('int', obrigatorio=True), 'tipo': C(obrigatorio=True, enum=TIPO_ELEICAO),
        'data_primeiro_turno': C('data'), 'data_segundo_turno': C('data'), 'tse_codigo': C(), 'rota': C(obrigatorio=True),
        'descricao': C(max_len=800), 'fonte_ids': C('lista', fk='fontes'), 'afirmacao_ids': C('lista', fk='afirmacoes'),
    }, origens=CF, unicos=[('rota',)]),
    Tabela('cargos', {  # Office
        'nome': C(obrigatorio=True), 'nome_curto': C(obrigatorio=True), 'esfera': C(obrigatorio=True, enum=ESFERA),
        'poder': C(obrigatorio=True, enum=PODER), 'instituicao_id': C(obrigatorio=True, fk='instituicoes'),
        'sistema': C(enum=SISTEMA_ELEITORAL), 'mandato_anos': C('int'), 'tse_codigo': C('int'),
        'funcao_resumo': C(obrigatorio=True, max_len=500), 'regra_ids': C('lista', fk='regras'),
        'titular_id': C(fk='cargos'), 'slug': C(obrigatorio=True), 'ordem': C('int'),
    }, unicos=[('slug',)]),
    Tabela('cargo_competencias', {
        'cargo_id': C(obrigatorio=True, fk='cargos'), 'competencia_id': C(obrigatorio=True, fk='competencias'),
        'modo': C(obrigatorio=True, enum=MODO_EXERCICIO), 'destaque': C('bool'), 'ordem': C('int'),
    }, unicos=[('cargo_id', 'competencia_id')], indices=('cargo_id',)),
    Tabela('cargos_eleicao', {
        'eleicao_id': C(obrigatorio=True, fk='eleicoes'), 'cargo_id': C(obrigatorio=True, fk='cargos'),
        'ente': C(obrigatorio=True, ente=True), 'rota': C(obrigatorio=True),
        'escolhas_por_eleitor': C('int'), 'vagas_afirmacao_id': C(fk='afirmacoes'), 'ordem': C('int'),
        'observacao': C(max_len=500),
    }, origens=CF, unicos=[('eleicao_id', 'rota')], indices=('eleicao_id',)),
    # ---------------------------------------------------------- dados do TSE (gerados)
    Tabela('partidos', {'sigla': C(obrigatorio=True), 'nome': C(), 'numero': C('int'), 'fonte_id': C(fk='fontes')},
           origens=('estado', 'fixtures'), gerada=True),
    Tabela('candidatos', {  # Candidate: a pessoa
        'nome_urna': C(obrigatorio=True), 'nome_urna_oficial': C(obrigatorio=True), 'nome_completo': C(),
        'ocupacao': C(), 'grau_instrucao': C(), 'naturalidade': C(), 'fonte_id': C(fk='fontes'),
    }, origens=('estado', 'fixtures'), gerada=True),
    Tabela('candidaturas', {  # CandidateOffice
        'candidato_id': C(obrigatorio=True, fk='candidatos'), 'eleicao_id': C(obrigatorio=True, fk='eleicoes'),
        'cargo_id': C(obrigatorio=True, fk='cargos'), 'cargo_eleicao_id': C(fk='cargos_eleicao'),
        'ente': C(obrigatorio=True, ente=True), 'partido_id': C(fk='partidos'), 'numero': C('int', obrigatorio=True),
        'situacao': C(obrigatorio=True, enum=SITUACAO_CANDIDATURA), 'situacao_oficial': C(), 'totalizacao_oficial': C(),
        'coligacao': C(), 'composicao_coligacao': C(), 'reeleicao': C('bool'), 'apta': C('bool'),
        'titular_id': C(fk='candidaturas'), 'foto_url': C(), 'tse_sq': C(), 'tse_processo': C(),
        'fonte_id': C(obrigatorio=True, fk='fontes'), 'proposta_governo_fonte_id': C(fk='fontes'),
        'detalhada': C('bool'), 'vices': C('lista'), 'ausente_desde': C('datahora'), 'criado_em': C('datahora'), 'atualizado_em': C('datahora'),
    }, origens=('estado', 'fixtures'), unicos=[('tse_sq', 'eleicao_id')],
       indices=('cargo_eleicao_id', 'partido_id'), gerada=True),
    # ---------------------------------------------------------- fontes e afirmações
    Tabela('fontes', {  # Source: entidade de primeira classe
        'titulo': C(obrigatorio=True), 'publicador': C(obrigatorio=True), 'url': C(obrigatorio=True),
        'tipo': C(obrigatorio=True, enum=TIPO_FONTE), 'data_publicacao': C('data'), 'data_documento': C('data'),
        'acessado_em': C('datahora', obrigatorio=True), 'autor': C(), 'descricao': C(max_len=800), 'url_arquivada': C(),
        'sha256': C(), 'snapshot': C(),
    }, origens=('conteudo', 'estado', 'fixtures'), unicos=[('url', 'acessado_em')]),
    Tabela('afirmacoes', {  # Claim
        'candidatura_id': C(fk='candidaturas'), 'proposta_id': C(fk='propostas'), 'texto': C(obrigatorio=True, max_len=1200),
        'tipo': C(obrigatorio=True, enum=TIPO_AFIRMACAO), 'data_evento': C('data'), 'confianca': C(enum=CONFIANCA),
        'status_revisao': C(obrigatorio=True, enum=STATUS_REVISAO), 'criado_em': C('datahora', obrigatorio=True),
        'atualizado_em': C('datahora', obrigatorio=True), 'valor': C('dict'),
    }, origens=('conteudo', 'estado', 'fixtures'), indices=('proposta_id', 'candidatura_id')),
    Tabela('afirmacao_fontes', {  # ClaimSource
        'afirmacao_id': C(obrigatorio=True, fk='afirmacoes'), 'fonte_id': C(obrigatorio=True, fk='fontes'),
        'relacao': C(obrigatorio=True, enum=RELACAO_FONTE), 'localizador': C(), 'trecho': C(max_len=400),
    }, origens=('conteudo', 'estado', 'fixtures'), unicos=[('afirmacao_id', 'fonte_id', 'localizador')], indices=('afirmacao_id',)),
    # ---------------------------------------------------------- propostas
    Tabela('grupos_proposta', {'titulo': C(obrigatorio=True), 'descricao': C(max_len=500)}, origens=CF),
    Tabela('propostas', {  # Proposal
        'candidatura_id': C(obrigatorio=True, fk='candidaturas'), 'titulo': C(obrigatorio=True, max_len=160),
        'descricao': C(obrigatorio=True, max_len=1200), 'materia_id': C(fk='materias'),
        'natureza_medida': C(obrigatorio=True, enum=NATUREZA_MEDIDA), 'grupo_id': C(fk='grupos_proposta'),
        'status_revisao': C(obrigatorio=True, enum=STATUS_REVISAO), 'criado_em': C('datahora', obrigatorio=True),
        'atualizado_em': C('datahora', obrigatorio=True),
    }, origens=CF, indices=('candidatura_id', 'materia_id')),
    Tabela('proposta_temas', {
        'proposta_id': C(obrigatorio=True, fk='propostas'), 'tema_id': C(obrigatorio=True, fk='temas'), 'principal': C('bool'),
    }, origens=CF, unicos=[('proposta_id', 'tema_id')], indices=('proposta_id', 'tema_id')),
    # ---------------------------------------------------------- análise (gerada) e revisão (curada)
    Tabela('analises', {  # ProposalCompetenceAnalysis
        'proposta_id': C(obrigatorio=True, fk='propostas'), 'cargo_id': C(obrigatorio=True, fk='cargos'),
        'classificacao': C(obrigatorio=True, enum=CLASSIFICACAO), 'competencia_direta': C(obrigatorio=True, enum=SIM_NAO),
        'pode_iniciar': C(obrigatorio=True, enum=SIM_NAO), 'explicacao': C(obrigatorio=True, max_len=2000),
        'instrumento_id': C(fk='instrumentos'), 'resumo_fundamento': C(max_len=600),
        'confianca': C(obrigatorio=True, enum=CONFIANCA), 'status_revisao': C(obrigatorio=True, enum=STATUS_REVISAO),
        'analisador': C(obrigatorio=True), 'versao_analisador': C(obrigatorio=True), 'hash_entrada': C(obrigatorio=True),
        'observacoes': C('lista'), 'revisao_id': C(fk='revisoes'), 'original': C('dict'),
        'criado_em': C('datahora', obrigatorio=True), 'atualizado_em': C('datahora', obrigatorio=True),
    }, origens=('estado',), unicos=[('proposta_id', 'cargo_id')], indices=('proposta_id',), gerada=True),
    Tabela('analise_regras', {
        'analise_id': C(obrigatorio=True, fk='analises'), 'regra_id': C(obrigatorio=True, fk='regras'),
        'papel': C(obrigatorio=True, enum=PAPEL_FUNDAMENTO), 'hash_dispositivo': C(), 'nota': C(max_len=400),
    }, origens=('estado',), unicos=[('analise_id', 'regra_id', 'papel')], indices=('analise_id',), gerada=True),
    Tabela('analise_alternativas', {
        'analise_id': C(obrigatorio=True, fk='analises'), 'instrumento_id': C(obrigatorio=True, fk='instrumentos'),
        'nota': C(max_len=400),
    }, origens=('estado',), unicos=[('analise_id', 'instrumento_id')], indices=('analise_id',), gerada=True),
    Tabela('dependencias', {  # ProposalDependency
        'analise_id': C(obrigatorio=True, fk='analises'), 'proposta_id': C(obrigatorio=True, fk='propostas'),
        'ordem': C('int', obrigatorio=True), 'tipo': C(obrigatorio=True, enum=TIPO_DEPENDENCIA),
        'instituicao_id': C(obrigatorio=True, fk='instituicoes'), 'explicacao': C(obrigatorio=True, max_len=600),
        'regra_id': C(fk='regras'), 'etapa_ordem': C('int'), 'alternativa': C('bool'), 'condicional': C('bool'),
        'cargo_integra': C('bool'),
    }, origens=('estado',), unicos=[('analise_id', 'ordem')], indices=('proposta_id', 'analise_id'), gerada=True),
    Tabela('revisoes', {
        'analise_id': C(obrigatorio=True), 'status': C(obrigatorio=True, enum=('PENDING_REVIEW', 'REVIEWED', 'CORRECTED')),
        'revisor': C(obrigatorio=True), 'revisado_em': C('datahora', obrigatorio=True), 'hash_entrada_revisada': C(obrigatorio=True),
        'nota': C(max_len=1000), 'correcao': C('dict'),
    }, origens=CF, unicos=[('analise_id',)]),
    # ---------------------------------------------------------- operação
    Tabela('ingestoes', {
        'fonte': C(obrigatorio=True), 'rotulo': C(obrigatorio=True), 'iniciado_em': C('datahora', obrigatorio=True),
        'concluido_em': C('datahora'), 'transporte': C(obrigatorio=True), 'fetched': C('int'), 'created': C('int'),
        'updated': C('int'), 'unchanged': C('int'), 'missing': C('int'), 'errors': C('int'), 'erros': C('lista'),
        'avisos': C('lista'), 'snapshots': C('lista'), 'por_escopo': C('lista'),
    }, origens=('estado',), gerada=True),
]}

# Tabelas de referência: registros fictícios podem apontar para elas sem contaminação,
# porque descrevem o direito e as instituições, não fatos sobre pessoas.
REFERENCIA = {'instituicoes', 'regras', 'instrumentos', 'instrumento_etapas', 'temas', 'materias', 'competencias',
              'cargos', 'cargo_competencias'}
