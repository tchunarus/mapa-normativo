---
name: incluir-diploma
description: Cadastra um diploma novo (lei, decreto, código, regulamento) no Mapa Normativo, federal, estadual ou municipal, a partir da fonte oficial consolidada, e confere o resultado publicado.
disable-model-invocation: true
argument-hint: "[nome ou número do diploma]"
---

# Incluir diploma no Mapa Normativo

Diploma pedido: $ARGUMENTS

Siga os passos na ordem. Pare e informe a usuária se algum critério do passo 1 falhar.

## 1. Fonte oficial

- Localize o texto **consolidado e vigente** na fonte oficial: Planalto (federal),
  SEF/SC (estadual), Câmara Municipal (municipal). Confirme com `curl -sI` que a URL
  responde.
- Se só houver o texto original, sem as alterações posteriores, **não inclua**: registre
  a pendência no docstring do módulo, como foi feito com São José em
  `coletor/fontes_municipais.py`.
- Confira em `coletor/fontes*.py` que o diploma ainda não está cadastrado.

## 2. Cadastro

Escolha o módulo pela jurisdição:

| Jurisdição | Arquivo | Observações |
|---|---|---|
| Federal | `coletor/fontes.py`, lista `DIPLOMAS` | `jurisdicao`/`ente` ficam no padrão; o marcador do DOU é gerado a partir de `norma` |
| Estadual | `coletor/fontes_estaduais.py` | declarar `jurisdicao='estadual'` e `ente` (ex.: `'SC'`) |
| Municipal | `coletor/fontes_municipais.py` | declarar `jurisdicao='municipal'` e `ente='UF/Município'`; formato fora do padrão exige `extrator` próprio em `EXTRATORES`/`BAIXADORES` |

Campos da entrada (siga o formato das vizinhas):

- `id`: minúsculo e **sem ponto** (o roteamento da página separa `diploma.artigo` pelo
  primeiro ponto). Ex.: `l9492`, `lcp123`, `sc_icms_lei`.
- `sigla`, `nome`, `norma` (nome oficial completo, "Lei nº X, de D de mês de AAAA").
- `area`: um código existente (`base`, `trib`, `ef`, `pc`, `civ`, `cons`, `emp`, `adm`,
  `trab`, `pen`, `rt`), conferido em `conteudo/taxonomia.json`.
- `url`: a versão compilada (`...compilado.htm` ou `...cons.htm` no Planalto, quando
  existir).
- `cache`: normalmente igual ao `id`.
- `urn`: URN LexML (`urn:lex:br:federal:lei:AAAA-MM-DD;numero`).
- `onda`: a onda do bloco onde a entrada for inserida.
- Opcionais: `corte=(inicio, fim)` para recortar parte do documento; `so_numericos=True`
  para emendas.

Se o ente não existir em `ENTES` (`coletor/fontes.py`), acrescente-o.

## 3. Coleta

```bash
python3 coletor/atualizar.py
```

Use o tempo máximo do Bash (600000 ms). O script baixa só o que mudou, grava
`docs/data/diplomas/<id>.json` e registra a inclusão em `estado/changelog.json`.

## 4. Conferência

- `docs/data/diplomas/<id>.json` existe; `n` (número de artigos) é compatível com o
  diploma; `completo` é `true`.
- Compare o primeiro, um intermediário e o último artigo com a página oficial:
  numeração, caput e presença de parágrafos. Artigos revogados aparecem com
  `rev: true`.
- Diploma federal: confira que `MARCADORES_DOU` passou a incluir o número da norma
  (`python3 -c "import sys; sys.path.insert(0,'coletor'); from fontes import MARCADORES_DOU as M; print(M['<id>'])"`).
- Abra a página no preview (`mapa-normativo` em `.claude/launch.json`) e confira que o
  diploma aparece na lista e abre sem erro no console.

## 5. Commit

Commit local com mensagem descritiva em português (o que entrou, a fonte e qualquer
limitação, como anexos não incluídos). A usuária faz o `git push`; não use credenciais
deste computador.

Termine com um resumo: diploma, fonte, número de artigos e pendências.
