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

## Comandos

```
pip install pypdf
python3 coletor/atualizar.py            # coleta completa e geração dos dados
python3 coletor/atualizar.py --diario   # inclui busca de temas novos e súmulas
python3 coletor/atualizar.py --sem-rede # só regenera docs/data
```

Os textos legais são reprodução das fontes oficiais. O conteúdo analítico é conferido
automaticamente contra essas fontes e não constitui parecer jurídico.
