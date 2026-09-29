"""AnalisadorPorRegras: classificação determinística a partir das tabelas curadas.

Entradas: a matéria e o tipo de medida da proposta, o cargo, as competências da
matéria (quem é o ente competente e por qual instrumento), as etapas do instrumento e
os poderes do cargo (cargo_competencias). Nada é decidido por texto livre: a mesma
entrada produz sempre a mesma saída, e cada conclusão aponta para a regra que a apoia.

Ordem de decisão:
1. sem matéria ou tipo de medida identificáveis: INSUFFICIENT_INFORMATION;
2. matéria de outro ente: <NÍVEL>_DEPENDENCY;
3. mudança no texto da Constituição: CONSTITUTIONAL_AMENDMENT_REQUIRED;
4. execução ou gasto que cabe a outro Poder do mesmo ente: OTHER_BRANCH_DEPENDENCY
   (ou OUTSIDE_OFFICE_COMPETENCE, se o cargo não tiver nenhum meio de contribuir);
5. competência comum ou concorrente da qual o nível do cargo participa: SHARED_COMPETENCE;
6. todas as etapas obrigatórias exercidas pelo próprio cargo, sozinho: DIRECT_POWER;
7. cargo sem participação em nenhuma etapa: OUTSIDE_OFFICE_COMPETENCE;
8. demais casos (o cargo participa, mas outros órgãos decidem): LEGISLATION_REQUIRED.
"""
from . import AnalisadorProposta, Resultado

NIVEL_DEP = {'FEDERAL': 'FEDERAL_DEPENDENCY', 'STATE': 'STATE_DEPENDENCY', 'MUNICIPAL': 'MUNICIPAL_DEPENDENCY'}
DO_ENTE = {'FEDERAL': 'da União', 'STATE': 'do Estado', 'MUNICIPAL': 'do Município'}
EXECUCAO = {'ADMINISTRATIVE_ACTION', 'PUBLIC_WORK_OR_SERVICE'}
AFINIDADE = {  # tipo de medida -> naturezas de competência que a realizam
    'LEGAL_CHANGE': ('LEGISLATIVE',), 'COMPLEMENTARY_LAW_CHANGE': ('LEGISLATIVE',),
    'EXECUTIVE_REGULATION': ('REGULATORY',), 'ADMINISTRATIVE_ACTION': ('ADMINISTRATIVE', 'MATERIAL'),
    'PUBLIC_WORK_OR_SERVICE': ('MATERIAL', 'ADMINISTRATIVE'), 'BUDGET_ALLOCATION': ('BUDGETARY',),
}
TIPO_DEP = {'DELIBERATION': 'LEGISLATIVE_APPROVAL', 'SANCTION_VETO': 'EXECUTIVE_SANCTION', 'PROMULGATION': 'CONSTITUTIONAL_PROMULGATION',
            'VETO_REVIEW': 'LEGISLATIVE_APPROVAL', 'REGULATION': 'REGULATION', 'BUDGET_AMENDMENT': 'BUDGET_ALLOCATION'}
ORDEM_NIVEL = {'FEDERAL': 0, 'STATE': 1, 'MUNICIPAL': 2}


DE = {'o': 'do', 'a': 'da', 'os': 'dos', 'as': 'das'}
A = {'o': 'ao', 'a': 'à', 'os': 'aos', 'as': 'às'}


def de(inst):
    return f'{DE[inst["artigo"]]} {inst["nome"]}'


def a(inst):
    return f'{A[inst["artigo"]]} {inst["nome"]}'


def _lista(nomes):
    nomes = [n for i, n in enumerate(nomes) if n not in nomes[:i]]
    return nomes[0] if len(nomes) == 1 else ', '.join(nomes[:-1]) + ' e ' + nomes[-1] if nomes else ''


def _ou(nomes):
    nomes = [n for i, n in enumerate(nomes) if n not in nomes[:i]]
    return nomes[0] if len(nomes) == 1 else ', '.join(nomes[:-1]) + ' ou ' + nomes[-1] if nomes else ''


class AnalisadorPorRegras(AnalisadorProposta):
    nome = 'RuleBasedProposalAnalyzer'
    versao = 'regras-1.0'

    def analisar(self, proposta, cargo, ctx):
        self.ctx, self.cargo, self.proposta = ctx, cargo, proposta
        self.obs, self.fund, self.alts, self.fund_alt, self.fora_da_base = [], [], [], [], False
        aid = f'{proposta["id"]}--{cargo["id"]}'
        m = ctx.t['materias'].get(proposta.get('materia_id'))
        nat = proposta.get('natureza_medida')
        if not m or nat in (None, 'UNSPECIFIED', 'OVERSIGHT') or (nat != 'CONSTITUTIONAL_CHANGE' and not ctx.comp_por_materia.get(m['id'])):
            return self._insuficiente(aid, proposta, cargo, m, nat)

        comp, instr_id, nivel_alvo = self._competencia(m, nat, cargo)
        instr = ctx.t['instrumentos'][instr_id]
        grupos = self._grupos(instr_id)
        inst_cargo = cargo['instituicao_id']
        poderes = ctx.poderes.get(cargo['id'], [])
        autoridades = {inst_cargo} | {c['autoridade_id'] for _, c in poderes if c.get('instrumento_id') == instr_id}
        niveis = sorted({c['nivel'] for c in ctx.comp_por_materia.get(m['id'], [])}, key=ORDEM_NIVEL.get)
        compartilhada = m['nivel'] == 'SHARED' and cargo['esfera'] in niveis

        # quais etapas o cargo exerce sozinho, de quais participa como membro, quais dependem de outros
        deps, participa, inicia = [], False, 'NO'
        self.proprias = []
        for ordem, etapas in grupos:
            minhas = [e for e in etapas if e['instituicao_id'] in autoridades]
            sozinho = [e for e in minhas if self._sozinho(e, inst_cargo)]
            self.proprias.extend(sozinho)
            participa = participa or bool(minhas)
            if ordem == grupos[0][0]:
                inicia = 'YES' if sozinho else 'DEPENDS' if minhas else 'NO'
            alternativa = len(etapas) > 1 and etapas[0]['papel'] in ('INITIATIVE', 'BUDGET_AMENDMENT')
            if sozinho and (alternativa or len(etapas) == 1):
                continue
            for e in etapas:
                if e in sozinho:
                    continue
                deps.append((e, alternativa, e['instituicao_id'] in autoridades))
        obrigatorias = [d for d in deps if not d[0].get('condicional')]
        if m.get('iniciativa_reservada_a') and m['iniciativa_reservada_a'] not in autoridades and inicia != 'NO':
            inicia = 'NO'
            self.obs.append(f'A iniciativa desta matéria é reservada a {ctx.t["instituicoes"][m["iniciativa_reservada_a"]]["nome"]}.')

        executor = next((e for _, es in grupos for e in es if e['papel'] == 'EXECUTION'), None)
        if nivel_alvo != cargo['esfera'] and not compartilhada:
            classe = NIVEL_DEP[nivel_alvo]
        elif nat == 'CONSTITUTIONAL_CHANGE':
            classe = 'CONSTITUTIONAL_AMENDMENT_REQUIRED'
        elif (nat in EXECUCAO or nat == 'BUDGET_ALLOCATION') and executor and executor['instituicao_id'] not in autoridades:
            self._alternativa_orcamentaria(cargo, instr)
            classe = 'OTHER_BRANCH_DEPENDENCY' if self.alts else 'OUTSIDE_OFFICE_COMPETENCE'
        elif compartilhada:
            classe = 'SHARED_COMPETENCE'
        elif not obrigatorias:
            classe = 'DIRECT_POWER'
        elif not participa:
            classe = 'OUTSIDE_OFFICE_COMPETENCE'
            self._alternativa_legislativa(m, cargo, instr_id)
        else:
            classe = 'LEGISLATION_REQUIRED'
        if classe in ('LEGISLATION_REQUIRED',):
            self._alternativa_mp(m, cargo, instr_id)
        if classe.endswith('_DEPENDENCY') and classe != 'OTHER_BRANCH_DEPENDENCY':
            inicia = inicia if participa else 'NO'

        # fundamentos: competência, instrumento, poderes do cargo usados, etapas, limites da matéria
        self._fund(comp['regra_id'], 'COMPETENCE', comp['descricao'])
        for c in ctx.comp_por_materia.get(m['id'], []):
            if c is not comp and (compartilhada or c['nivel'] == nivel_alvo):
                self._fund(c['regra_id'], 'COMPETENCE', c['descricao'])
        self._fund(instr.get('regra_id'), 'INSTRUMENT', instr['nome'])
        for _, c in poderes:
            if c.get('instrumento_id') == instr_id:
                self._fund(c['regra_id'], 'INITIATIVE', c['descricao'])
        for _, es in grupos:
            for e in es:
                self._fund(e.get('regra_id'), 'PROCEDURE', e['descricao'])
        for r in m.get('regra_limite_ids') or []:
            self._fund(r, 'LIMIT', None)
        for f in self.fund_alt:
            self._fund(*f)

        linhas_dep = []
        for i, (e, alternativa, integra) in enumerate(deps, 1):
            inst = ctx.t['instituicoes'][e['instituicao_id']]
            tipo = TIPO_DEP.get(e['papel'])
            if e['papel'] in ('INITIATIVE', 'EXECUTION'):
                tipo = 'OTHER_ENTITY_ACTION' if classe in NIVEL_DEP.values() else 'OTHER_BRANCH_ACTION'
            expl = e['descricao']
            if integra:
                expl += f' O {cargo["nome_curto"]} integra este órgão, mas a decisão é coletiva.'
            linhas_dep.append({'id': f'{aid}--dep-{i:02d}', 'analise_id': aid, 'proposta_id': proposta['id'], 'ordem': i,
                               'tipo': tipo, 'instituicao_id': inst['id'], 'explicacao': expl, 'regra_id': e.get('regra_id'),
                               'etapa_ordem': e['ordem'], 'alternativa': alternativa or None, 'condicional': e.get('condicional') or None,
                               'cargo_integra': integra or None})

        if m.get('observacao'):
            self.obs.append(m['observacao'])
        if nat == 'PUBLIC_WORK_OR_SERVICE':
            self.obs.append('A execução depende de recursos previstos no orçamento aprovado.')
        if instr.get('exige_sancao') is False and nat == 'CONSTITUTIONAL_CHANGE':
            self.obs.append('A emenda constitucional não passa por sanção nem veto do Presidente da República.')
        if self.fora_da_base:
            self.obs.append('Parte do fundamento está na Constituição do Estado de Santa Catarina, ainda não incorporada ao Mapa Normativo; a análise cita apenas os dispositivos da Constituição Federal já conferidos.')
        competencia_direta = 'YES' if classe == 'DIRECT_POWER' or (classe == 'SHARED_COMPETENCE' and not obrigatorias) else 'NO'
        explicacao = self._explicar(classe, comp, instr, nivel_alvo, deps, inicia, m, executor)
        conf = 'LOW' if classe == 'INSUFFICIENT_INFORMATION' else 'MEDIUM' if self.fora_da_base else 'HIGH'
        analise = {'id': aid, 'proposta_id': proposta['id'], 'cargo_id': cargo['id'], 'classificacao': classe,
                   'competencia_direta': competencia_direta, 'pode_iniciar': 'YES' if classe == 'DIRECT_POWER' else inicia,
                   'explicacao': explicacao, 'instrumento_id': instr_id,
                   'resumo_fundamento': '; '.join(ctx.t['regras'][f[0]]['rotulo'] for f in self.fund[:4]),
                   'confianca': conf, 'status_revisao': 'AUTO_GENERATED', 'analisador': self.nome, 'versao_analisador': self.versao,
                   'hash_entrada': ctx.hash_entrada(proposta, cargo), 'observacoes': self.obs or None}
        return Resultado(analise, self._linhas_fund(aid), linhas_dep, self._linhas_alt(aid))

    # ------------------------------------------------------------------ auxiliares
    def _competencia(self, m, nat, cargo):
        ctx = self.ctx
        if nat == 'CONSTITUTIONAL_CHANGE':
            comp = next((c for c in ctx.comp_por_materia.get('texto-constitucional', [])), None)
            if m['id'] != 'texto-constitucional':
                self.obs.append('A proposta pede mudança no texto da Constituição Federal; a análise considera a via da emenda constitucional.')
            return comp, 'pec', 'FEDERAL'
        comps = ctx.comp_por_materia[m['id']]
        afins = [c for c in comps if c['natureza'] in AFINIDADE.get(nat, ())]
        if not afins:
            if nat == 'EXECUTIVE_REGULATION':
                self.obs.append('A matéria não admite alteração por regulamento do Poder Executivo; a mudança pretendida exige lei.')
            else:
                self.obs.append('O tipo de medida não corresponde diretamente às competências cadastradas para a matéria; a análise usa a competência principal.')
            afins = comps
        comp = next((c for c in afins if c['nivel'] == cargo['esfera']), None) or sorted(afins, key=lambda c: ORDEM_NIVEL[c['nivel']])[0]
        instr = comp['instrumento_id']
        if instr == 'lei-ordinaria-federal' and (nat == 'COMPLEMENTARY_LAW_CHANGE' or m.get('exige_lei_complementar')):
            instr = 'lei-complementar-federal'
        return comp, instr, comp['nivel']

    def _grupos(self, instr_id):
        grupos = {}
        for e in self.ctx.etapas.get(instr_id, []):
            grupos.setdefault(e['ordem'], []).append(e)
        return sorted(grupos.items())

    def _sozinho(self, etapa, inst_cargo):
        inst = self.ctx.t['instituicoes'][etapa['instituicao_id']]
        return (etapa['instituicao_id'] == inst_cargo and inst['tipo'] == 'SINGLE_OFFICE') or bool(etapa.get('exercicio_individual')) and etapa['instituicao_id'] == inst_cargo

    def _fund(self, regra_id, papel, nota):
        if not regra_id or any(f[0] == regra_id for f in self.fund):
            return
        if self.ctx.t['regras'][regra_id].get('fora_da_base'):
            self.fora_da_base = True
        self.fund.append((regra_id, papel, nota))

    def _linhas_fund(self, aid):
        out = []
        for r, papel, nota in self.fund:
            out.append({'id': f'{aid}--{r}', 'analise_id': aid, 'regra_id': r, 'papel': papel,
                        'hash_dispositivo': (self.ctx.info_regras.get(r) or {}).get('hash'), 'nota': nota})
        return out

    def _linhas_alt(self, aid):
        return [{'id': f'{aid}--alt-{i}', 'analise_id': aid, 'instrumento_id': i, 'nota': n} for i, n in self.alts]

    def _poder_para(self, cargo, instr_id):
        return next((c for _, c in self.ctx.poderes.get(cargo['id'], []) if c.get('instrumento_id') == instr_id), None)

    def _alternativa_mp(self, m, cargo, instr_id):
        for i in self.ctx.t['instrumentos'].values():
            if i.get('alternativa_a') == instr_id and self._poder_para(cargo, i['id']) and not m.get('exige_lei_complementar'):
                self.alts.append((i['id'], i.get('nota_alternativa')))
                self.fund_alt.append((i.get('regra_id'), 'INSTRUMENT', i['nome']))

    def _alternativa_orcamentaria(self, cargo, instr):
        for _, c in self.ctx.poderes.get(cargo['id'], []):
            alvo = self.ctx.t['instrumentos'].get(c.get('instrumento_id') or '')
            if alvo and c['natureza'] == 'BUDGETARY' and alvo['esfera'] == instr['esfera'] and alvo['id'] != instr['id'] and 'emenda' in alvo['id']:
                self.alts.append((alvo['id'], 'O cargo pode destinar recursos à medida por emenda ao orçamento, cuja execução cabe ao Poder Executivo.'))
                self.fund_alt.append((c['regra_id'], 'INITIATIVE', c['descricao']))

    def _alternativa_legislativa(self, m, cargo, instr_id):
        for c in self.ctx.comp_por_materia.get(m['id'], []):
            i = c.get('instrumento_id')
            if i and i != instr_id and c['natureza'] == 'LEGISLATIVE' and c['nivel'] == cargo['esfera'] and self._poder_para(cargo, i):
                self.alts.append((i, 'Por essa via o cargo pode propor mudança na lei que rege a matéria; a medida na forma proposta, porém, não é ato seu.'))
                self.fund_alt.append((c['regra_id'], 'COMPETENCE', c['descricao']))

    def _insuficiente(self, aid, proposta, cargo, m, nat):
        motivo = 'a matéria' if not m else 'o tipo de medida'
        analise = {'id': aid, 'proposta_id': proposta['id'], 'cargo_id': cargo['id'], 'classificacao': 'INSUFFICIENT_INFORMATION',
                   'competencia_direta': 'NOT_APPLICABLE', 'pode_iniciar': 'NOT_APPLICABLE',
                   'explicacao': f'A proposta, como apresentada, não permite identificar {motivo} com segurança. Sem isso, não é possível dizer se o {cargo["nome_curto"]} tem competência para realizá-la nem qual instrumento seria necessário.',
                   'confianca': 'LOW', 'status_revisao': 'AUTO_GENERATED', 'analisador': self.nome, 'versao_analisador': self.versao,
                   'hash_entrada': self.ctx.hash_entrada(proposta, cargo),
                   'observacoes': ['Para análise, a proposta precisa indicar o que muda (lei, regulamento, serviço, obra ou gasto) e sobre qual assunto.']}
        return Resultado(analise)

    def _etapas_txt(self, deps, instr):
        """Frases sobre de quem a medida depende, agrupadas pelo papel de cada etapa."""
        I = self.ctx.t['instituicoes']
        obrig = [d for d in deps if not d[0].get('condicional')]
        por_papel = {}
        for e, alternativa, _ in obrig:
            por_papel.setdefault('ALT' if alternativa else e['papel'], []).append(I[e['instituicao_id']])
        partes = []
        if por_papel.get('ALT'):
            partes.append(f'A iniciativa cabe {_ou([a(i) for i in por_papel["ALT"]])}.')
        if por_papel.get('INITIATIVE'):
            partes.append(f'A iniciativa cabe {_lista([a(i) for i in por_papel["INITIATIVE"]])}.')
        delib = por_papel.get('DELIBERATION', []) + por_papel.get('VETO_REVIEW', [])
        if delib:
            q = f', com {instr["quorum"][0].lower()}{instr["quorum"][1:].rstrip(".")}' if instr.get('quorum') and instr['id'] == 'pec' else ''
            partes.append(f'A aprovação depende {_lista([de(i) for i in delib])}{q}.')
        if por_papel.get('SANCTION_VETO'):
            partes.append(f'A sanção ou o veto cabe {_lista([a(i) for i in por_papel["SANCTION_VETO"]])}.')
        if por_papel.get('PROMULGATION'):
            partes.append(f'A promulgação cabe {_lista([a(i) for i in por_papel["PROMULGATION"]])}.')
        for papel in ('EXECUTION', 'REGULATION'):
            if por_papel.get(papel):
                partes.append(f'O ato cabe {_lista([a(i) for i in por_papel[papel]])}.')
        return ' '.join(partes)

    def _explicar(self, classe, comp, instr, nivel_alvo, deps, inicia, m, executor):
        ctx, cargo = self.ctx, self.cargo
        nome = cargo['nome_curto']
        rot = lambda r: ctx.t['regras'][r]['rotulo'] if r else ''
        I = ctx.t['instituicoes']
        inome = instr['nome'][0].lower() + instr['nome'][1:]
        obrig = [d for d in deps if not d[0].get('condicional')]
        base = f'{comp["descricao"].rstrip(".")} ({rot(comp["regra_id"])}).' if comp else ''
        etapas = self._etapas_txt(deps, instr)
        papel_inicio = {'YES': f'O {nome} pode dar início ao processo.',
                        'DEPENDS': f'O {nome} participa da iniciativa, mas não pode apresentá-la sozinho.',
                        'NO': f'O {nome} não tem iniciativa nessa matéria.'}[inicia]
        if classe == 'DIRECT_POWER':
            return f'O {nome} pode adotar a medida diretamente, por {inome}, sem depender da aprovação de outro órgão. {base}'
        if classe == 'LEGISLATION_REQUIRED':
            sancao = f'Aprovado o projeto, cabe ao próprio {nome} sancioná-lo ou vetá-lo.' if any(e['papel'] == 'SANCTION_VETO' for e in self.proprias) else ''
            return f'O {nome} tem meios institucionais para promover a medida, mas ela não se realiza por ato unilateral: exige {inome}. {papel_inicio} {etapas} {sancao} {base}'.replace('  ', ' ')
        if classe == 'CONSTITUTIONAL_AMENDMENT_REQUIRED':
            return f'A medida altera a Constituição Federal e, por isso, exige {inome} ({instr["nome_curto"]}). {papel_inicio} {etapas} {base}'.replace('  ', ' ')
        if classe in NIVEL_DEP.values():
            t = f'A matéria é de competência {DO_ENTE[nivel_alvo]}, e não do cargo de {nome}. {base} A medida depende de {inome}. {etapas}'
            if inicia == 'DEPENDS':
                via = next((c for _, c in ctx.poderes.get(cargo['id'], []) if c.get('instrumento_id') == instr['id']), None)
                if via:
                    t += f' O {nome} só participa de forma coletiva, por meio {de(I[via["autoridade_id"]])} ({rot(via["regra_id"])}).'
            return t.replace('  ', ' ').strip()
        if classe == 'OTHER_BRANCH_DEPENDENCY':
            t = f'A execução da medida cabe {a(I[executor["instituicao_id"]])}, não ao {nome}. {base}'
            if self.alts:
                t += ' O cargo pode contribuir por outro instrumento, indicado abaixo, mas não realiza a medida por conta própria.'
            return t
        if classe == 'OUTSIDE_OFFICE_COMPETENCE':
            dono = executor or next((d[0] for d in deps), None)
            t = f'A medida, na forma proposta ({inome}), é ato {de(I[dono["instituicao_id"]]) if dono else "de outro órgão"}, do qual o {nome} não participa. {base}'
            if self.alts:
                t += ' Há outro caminho em que o cargo atua, indicado abaixo.'
            return t
        if classe == 'SHARED_COMPETENCE':
            niveis = sorted({c['nivel'] for c in ctx.comp_por_materia.get(m['id'], [])}, key=ORDEM_NIVEL.get)
            entes = _lista([{'FEDERAL': 'a União', 'STATE': 'os Estados', 'MUNICIPAL': 'os Municípios'}[n] for n in niveis])
            tit = 'concorrente' if comp.get('titularidade') == 'CONCURRENT' else 'comum'
            t = f'A matéria é de competência {tit}: dela participam {entes}. {base}'
            if obrig:
                t += f' No âmbito {DO_ENTE[cargo["esfera"]]}, a medida exige {inome}. {papel_inicio} {etapas}'
            else:
                t += f' No âmbito {DO_ENTE[cargo["esfera"]]}, o {nome} pode atuar diretamente, por {inome}, sem excluir a atuação dos demais entes.'
            return t.replace('  ', ' ').strip()
        return base
