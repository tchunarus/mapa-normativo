# Mapa Normativo

Mapa jurídico do Guedes Pinto Advogados: textos legais oficiais atualizados e relações
entre dispositivos de diplomas diferentes, publicados como site estático (`docs/`,
GitHub Pages). Estrutura e comandos no `README.md`; passo a passo das rotinas na nuvem
no `ROTINA.md`.

## Fontes

- Prioridade para fontes públicas, oficiais e primárias: Planalto, DOU, Senado, Câmara,
  portais dos tribunais, SEF/SC, Câmara Municipal de Florianópolis.
- Jusratio é complementar: localiza precedentes, nunca é fonte principal. Todo registro
  leva o link da fonte oficial.
- Nunca reproduzir texto legal de memória. O texto vem sempre da compilação oficial em
  `.cache/`, e a redação vigente é a de `docs/data/diplomas/<id>.json`.
- Diploma sem texto consolidado oficial não entra (caso de São José, em
  `coletor/fontes_municipais.py`): publicar texto original como vigente é proibido.
- Jurisprudência em matéria penal: apenas STF e STJ.

## Dados gerados

`docs/data/`, `estado/hashes.json`, `estado/changelog.json` e `estado/etags.json` só
mudam pelos scripts (`coletor/atualizar.py`, `registrar.py`, `relacionar.py`). Edição
manual rompe a trilha de auditoria por hash. Depois de mudar `conteudo/` ou `coletor/`,
rodar `python3 coletor/atualizar.py --sem-rede` para regenerar `docs/data/`.

## Redação

- Português formal, com acentuação correta.
- Sem travessões (em dash); usar vírgulas ou parênteses. Meia-risca é permitida.
- Nunca chamar o escritório de "GPA": usar "escritório", "Guedes Pinto" ou
  "Guedes Pinto Advogados".
- Relações entre dispositivos seguem os critérios do passo 2 do `ROTINA.md` (tipos,
  graus, `confundivel_com`, `aplica_subsidiariamente` versus `complementa`).

## Git e credenciais

- Execução local: preparar o commit; a usuária roda `git push`. Nunca usar credencial,
  token ou keychain deste computador.
- Rotinas na nuvem fazem commit e push em `main` pelo app Claude do GitHub.
- Código compatível com Python 3.9, sem dependências além de `pypdf`.

## Automações do projeto

- `.claude/hooks/`: validação dos JSON de `conteudo/` e bloqueio de edição manual dos
  dados gerados.
- `.claude/skills/incluir-diploma/`: fluxo para cadastrar um diploma novo (`/incluir-diploma`).
- `.claude/agents/revisor-relacoes.md`: segunda conferência, independente, das relações
  gravadas.
