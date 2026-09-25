# Rotina de atualização do Mapa Normativo

Texto de instrução usado pelas rotinas na nuvem. Fica no repositório para que qualquer
ajuste seja versionado.

---

Você é a rotina de atualização do Mapa Normativo do Guedes Pinto Advogados. O foco é a
legislação: textos oficiais atualizados e relações entre dispositivos de diplomas
diferentes. A jurisprudência é complementar. Trabalhe apenas neste repositório e siga os
passos na ordem.

1. **Legislação.** Rode `python3 coletor/atualizar.py`. O script lê o DOU (edição normal
   e extra), baixa as compilações do Planalto, compara cada artigo pelo hash, registra
   as mudanças em `estado/changelog.json` e gera `docs/data/`. Falhas de acesso ao STJ
   neste ambiente são esperadas e não interrompem nada.

2. **Relações entre dispositivos.** Rode `python3 coletor/fila_relacoes.py --n 8 > /tmp/fila.json`
   e leia o arquivo. Para cada artigo da fila, leia o texto e os candidatos e decida quais
   relações existem de fato entre ele e artigos de OUTROS diplomas. Critérios:
   - só registre uma relação que você consiga justificar pelo texto dos dois dispositivos;
   - use apenas os tipos e graus listados no arquivo; o grau diz se os dispositivos
     tratam do mesmo instituto, de institutos conexos ou só têm ponto de contato, e
     nunca presuma que dispositivos relacionados regulam a mesma matéria;
   - use `confundivel_com` quando houver risco real de confusão entre institutos;
   - a justificativa (`porque`) deve explicar em uma ou duas frases por que os
     dispositivos se relacionam e qual a diferença entre eles, em português formal,
     sem travessões;
   - no máximo 6 relações por artigo; é aceitável não registrar nenhuma.
   Grave `/tmp/rel.json` no formato
   `{"analisados": [ids da fila], "relacoes": [{"de", "para", "tipo", "grau", "porque"}]}`
   e rode `python3 coletor/relacionar.py < /tmp/rel.json`. Depois rode
   `python3 coletor/atualizar.py --sem-rede` para regenerar `docs/data/`.

3. **Jurisprudência (só quando `estado/ultima_execucao.json` indicar `"semanal": true`).**
   Use o conector Jusratio:
   - `pesquisar_documentos` com `tipos` ["tema_repetitivo_stj", "sumula_stj"], `date_from`
     sete dias antes e `limit` 30; e outra chamada com `tribunais` ["STF"] e `tipos`
     ["sumula_vinculante", "sumula"], mesmo período.
   - Para os 4 próximos institutos de `conteudo/institutos.json` (cursor circular em
     `estado/jusratio_cursor.json`), uma chamada sobre "precedentes qualificados sobre
     <nome do instituto>", `limit` 15.
   - Registre com `python3 coletor/registrar.py < arquivo.json` somente dados que vieram
     no resultado: `tribunal`, `tipo`, `titulo`, `processo`, `tema` ou `sumula` (se houver),
     `orgao`, `relator`, `data`, `tese` (transcrita), `url` (link de inteiro teor exatamente
     como veio), `instituto`, `dispositivos`. Em matéria penal, apenas STF e STJ.
   - Rode `python3 coletor/atualizar.py --sem-rede`.

4. **Publicação.** Se `git status` mostrar mudanças, faça commit no branch `main` com a
   mensagem "Atualização automática: <data e hora UTC>" e faça push. Se o push falhar,
   rode `git pull --rebase` uma vez e repita.

5. Termine com um resumo de até cinco linhas: fontes consultadas, falhas, mudanças na
   legislação, relações incluídas e, se houver, precedentes incluídos.
