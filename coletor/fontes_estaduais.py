"""Diplomas estaduais. Reaproveitam o extrator de planalto.py: os portais estaduais
testados até agora publicam a mesma estrutura de texto plano com "Art. N" que o
Planalto, então nenhum extrator especial é necessário aqui.

Fonte: legislação tributária da Secretaria de Estado da Fazenda de Santa Catarina
(SEF/SC), que mantém o texto consolidado da lei e do regulamento do ICMS. O rodapé
do próprio portal adverte que o texto não tem caráter oficial e não substitui o
publicado no Diário Oficial do Estado; por isso cada dispositivo mantém o link
direto para essa fonte e a data da última conferência, no mesmo padrão usado para
os diplomas federais.
"""

SEF = 'https://legislacao.sef.sc.gov.br/'

DIPLOMAS_ESTADUAIS = [
  # Os ids não usam ponto: o roteamento da página lê "diploma.artigo" pelo primeiro
  # ponto do endereço, então um id de diploma com ponto quebra essa separação.
  dict(id='sc_icms_lei', sigla='Lei 10.297/96-SC', nome='Lei do ICMS de Santa Catarina', norma='Lei nº 10.297, de 26 de dezembro de 1996',
       area='trib', jurisdicao='estadual', ente='SC', url=SEF + 'html/leis/1996/Lei_96_10297.htm', cache='sc_icms_lei',
       urn='urn:lex:br:sc:estadual:lei:1996-12-26;10297', onda=4),
  dict(id='sc_ricms', sigla='RICMS-SC', nome='Regulamento do ICMS de Santa Catarina', norma='Decreto nº 2.870, de 27 de agosto de 2001 (corpo principal, sem os Anexos)',
       area='trib', jurisdicao='estadual', ente='SC', url=SEF + 'HTML/REGULAMENTOS/ICMS/RICMS_01_00.htm', cache='sc_ricms',
       urn='urn:lex:br:sc:estadual:decreto:2001-08-27;2870', onda=4),
]
