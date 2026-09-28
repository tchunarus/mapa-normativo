"""Diplomas municipais.

Ao contrário do Planalto e da SEF/SC, os portais municipais testados até agora não
publicam um HTML plano por diploma: o texto consolidado do Código Tributário de
Florianópolis é um anexo em .DOC no sistema legislativo da própria Câmara Municipal
(fonte oficial: cmf.sc.gov.br), atualizado por último em 26/05/2026 pela Diretoria
Legislativa da Câmara. Por isso este diploma tem um extrator próprio, em vez de
reaproveitar planalto.extrair.

São José ainda não entrou: a Câmara de São José só disponibiliza o texto original de
2005 da Lei Complementar nº 21/2005 (Código Tributário Municipal), sem a versão
consolidada com as alterações posteriores encontradas na pesquisa (pelo menos três,
incluindo mudança no art. 326). Publicar o texto de 2005 como se fosse vigente seria
apresentar dispositivo revogado ou alterado como texto atual, o que a base não faz.
Assim que se localizar uma fonte oficial com o texto consolidado, ou um documento
fornecido pelo escritório, o diploma entra do mesmo jeito que os demais.
"""
import re, subprocess, sys, os

sys.path.insert(0, os.path.dirname(__file__))
import planalto

CMF = 'https://www.cmf.sc.gov.br/'

DIPLOMAS_MUNICIPAIS = [
  dict(id='floripa_ctm', sigla='CTM Florianópolis', nome='Código Tributário do Município de Florianópolis',
       norma='Lei Complementar nº 007, de 6 de janeiro de 1997 (consolidada com as alterações posteriores)',
       area='trib', jurisdicao='municipal', ente='SC/Florianópolis',
       url='https://www.cmf.sc.gov.br/proposicoes/Leis-Complementares/1997/1/0/75248', cache='floripa_ctm',
       urn='urn:lex:br:sc:florianopolis:lei.complementar:1997-01-06;7', onda=5, automatico=False,
       fonte='Câmara Municipal de Florianópolis', verificado_manual='2026-09-28T13:59:00+00:00',  # download do .doc oficial
       extrator='floripa_ctm', fonte_doc='https://www.cloudsoftcam.com.br/SC/FLORIANOPOLIS/upload/2026/05/202605271405241779901524235c80.DOC'),
]

# Padrão de campo de hiperlink do Word preservado pelo conversor de .doc para texto
# ("HYPERLINK \"url\" \\t \"_blank\"texto visível"): remove o código, mantém o texto.
_HYPERLINK = re.compile(r'HYPERLINK\s+"[^"]*"(?:\s*\\\w+\s*"[^"]*")*')


def baixar_floripa_ctm(destino):
    """Baixa o .doc oficial da Câmara de Florianópolis. `destino` é o caminho do .doc
    em cache; o .doc convertido para texto fica ao lado, com o mesmo nome e .txt."""
    f = next(d for d in DIPLOMAS_MUNICIPAIS if d['id'] == 'floripa_ctm')
    r = subprocess.run(['curl', '-sSL', '--fail', '--max-time', '120', '-A', planalto.UA, '-o', destino, f['fonte_doc']])
    return r.returncode == 0 and os.path.exists(destino) and os.path.getsize(destino) > 100_000


def extrair_floripa_ctm(caminho_doc, _diploma):
    """.doc (formato binário antigo do Word) -> texto -> artigos, via textutil (macOS)."""
    txt = caminho_doc.rsplit('.', 1)[0] + '.txt'
    subprocess.run(['textutil', '-convert', 'txt', caminho_doc, '-output', txt], check=True)
    t = open(txt, encoding='utf-8').read()
    t = _HYPERLINK.sub('', t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n[ \t]*\n+', '\n', t)
    t = '\n'.join(l.strip() for l in t.split('\n') if l.strip())
    return planalto.artigos(t)


EXTRATORES = {'floripa_ctm': extrair_floripa_ctm}
BAIXADORES = {'floripa_ctm': baixar_floripa_ctm}
