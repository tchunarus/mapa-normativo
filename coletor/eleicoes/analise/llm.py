"""AnalisadorLLM: previsto, não implementado nesta fase.

Quando for implementado, deve rodar no pipeline (nunca na página), com estas garantias:

- entrada: a proposta, o cargo e o mesmo Contexto usado pelo AnalisadorPorRegras;
- saída: um Resultado com a mesma estrutura, status AUTO_GENERATED e confiança
  declarada; a classificação precisa pertencer à enumeração do esquema;
- só pode citar regras já cadastradas em `regras` (conferidas contra o Mapa Normativo);
  qualquer citação fora da tabela invalida o resultado;
- o resultado passa pelo mesmo validador do repositório antes de ser gravado, e a
  divergência com o AnalisadorPorRegras vai para o painel como item de revisão.
"""
from . import AnalisadorProposta


class AnalisadorLLM(AnalisadorProposta):
    nome = 'LLMProposalAnalyzer'
    versao = 'nao-implementado'

    def analisar(self, proposta, cargo, ctx):
        raise NotImplementedError('AnalisadorLLM ainda não implementado; use AnalisadorPorRegras.')
