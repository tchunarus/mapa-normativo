# Mapa Normativo

Mapa jurídico do Guedes Pinto Advogados que relaciona dispositivos de diferentes diplomas,
institutos jurídicos e precedentes, com atualização automática a partir de fontes públicas.

## Como funciona

- **Fontes oficiais (principais).** Legislação compilada do Planalto, Diário Oficial da
  União (seção 1 e edição extra), Senado Federal (normas publicadas), Câmara dos Deputados
  (proposições que alteram diplomas acompanhados) e portais dos tribunais.
- **Fonte complementar.** Jusratio, apenas para localizar precedentes; todo registro
  exige link para a fonte oficial.
- **Atualização.** Rotinas na nuvem executam `ROTINA.md` de hora em hora nos dias úteis.
  Cada execução compara cada artigo pelo hash do texto e registra toda mudança em
  `estado/changelog.json`. Um ato publicado no DOU que cite um diploma acompanhado
  gera o aviso "alteração publicada, compilação oficial pendente" até o Planalto
  consolidar o texto.
- **Página.** `docs/index.html` lê `docs/data/` e funciona como site estático
  (GitHub Pages), incorporado como página oculta no site do escritório.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `coletor/` | Coleta e geração dos dados (Python, sem dependências além de `pypdf`) |
| `coletor/fontes.py` | Cadastro dos diplomas acompanhados: incluir um diploma é acrescentar uma entrada |
| `conteudo/` | Camada analítica: institutos, relações, alertas e comparações |
| `estado/` | Precedentes, hashes, publicações do DOU, pendências e histórico de mudanças |
| `docs/` | Página pública e dados publicados |

## Mapa Eleitoral

Módulo do mesmo site (aba **Eleições**, rota `#eleicoes`) que responde, para cada proposta
de candidatura: o que foi proposto, se o cargo tem competência para realizar a medida e,
se não puder fazê-lo sozinho, de quem depende. Os fundamentos apontam para os artigos
já publicados pelo Mapa Normativo (não há segunda base normativa).

| Pasta | Conteúdo |
|---|---|
| `coletor/eleicoes/esquema.py` | Esquema das tabelas (campos, enumerações, chaves, unicidade) |
| `coletor/eleicoes/repositorio.py` | Carga, validação de integridade e gravação (faz as vezes de banco) |
| `coletor/eleicoes/tse/` | Integração com o TSE: cliente, parser, normalizador, sincronização |
| `coletor/eleicoes/analise/` | Interface do analisador e `AnalisadorPorRegras` |
| `coletor/eleicoes/publicar.py` | Gera `docs/data/eleicoes/` (arquivos por cargo, candidatura e proposta) |
| `conteudo/eleicoes/` | Conteúdo curado: cargos, competências, fundamentos, instrumentos, temas, propostas |
| `conteudo/eleicoes/fixtures/` | Dados fictícios de demonstração (DEVELOPMENT_FIXTURE), isolados dos reais |
| `estado/eleicoes/` | Dados gerados: candidaturas do TSE, snapshots, análises, log de ingestão |
| `web/eleicoes*.{js,html}` | Interface, montada em `docs/index.html` por `coletor/paginar.py` |

```
python3 coletor/eleicoes/migrar.py                         # aplica migrações do esquema
python3 coletor/eleicoes/tse/sincronizar.py                # TSE (http); --transporte snapshot reprocessa sem rede
python3 coletor/eleicoes/tse/importar_captura.py <arquivo>  # importa captura feita no navegador
python3 coletor/eleicoes/legislativo.py                    # vagas do Senado em disputa
python3 coletor/eleicoes/analisar.py                       # análise de competência das propostas
python3 coletor/eleicoes/publicar.py                       # publica docs/data/eleicoes/
python3 coletor/eleicoes/repositorio.py                    # só valida a integridade
python3 -m unittest discover -s testes && node --test testes/js/
```

`coletor/atualizar.py` roda essas etapas ao final de cada execução (o TSE e o Senado uma
vez por dia); uma falha nelas fica no status e no log de ingestão sem interromper o Mapa
Normativo.

## Comandos

```
pip install pypdf
python3 coletor/atualizar.py            # coleta completa e geração dos dados
python3 coletor/atualizar.py --diario   # inclui busca de temas novos e súmulas
python3 coletor/atualizar.py --sem-rede # só regenera docs/data
```

Os textos legais são reprodução das fontes oficiais. O conteúdo analítico é conferido
automaticamente contra essas fontes e não constitui parecer jurídico.
