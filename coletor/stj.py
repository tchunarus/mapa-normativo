"""Temas repetitivos do STJ, lidos da página oficial de Precedentes Qualificados."""
import html, re, subprocess

URL = 'https://processo.stj.jus.br/repetitivos/temas_repetitivos/pesquisa.jsp?novaConsulta=true&tipo_pesquisa=T&cod_tema_inicial={n}&cod_tema_final={n}'


def _texto(n):
    r = subprocess.run(['curl', '-sL', '--max-time', '60', '-A', 'Mozilla/5.0', URL.format(n=n)], capture_output=True)
    t = r.stdout.decode('latin-1')
    t = re.sub(r'(?is)<(script|style).*?</\1>', '', t)
    t = re.sub(r'<[^>]+>', '\n', t)
    t = html.unescape(t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t)
    i = t.find('Tema Repetitivo')
    return t[i:t.find('Última atualização')] if i >= 0 else ''


def tema(n):
    """Devolve o tema como dicionário, ou None se a página não o trouxer."""
    t = _texto(n)
    if not t:
        return None

    def campo(a, b):
        m = re.search(re.escape(a) + r'\s*\n(.*?)\n\s*(?:' + b + r')', t, re.S)
        return re.sub(r'\s+', ' ', m.group(1)).strip() if m else None

    procs = []
    for m in re.finditer(r'\n((?:REsp|RE|AREsp|EREsp|Pet|ProAfR) \d+/[A-Z]{2})\n(.*?)(?=\n(?:REsp|RE|AREsp|EREsp|Pet|ProAfR) \d+/|\Z)', t, re.S):
        blk = m.group(2)
        g = lambda k: ((re.search(re.escape(k) + r'\s*\n\s*([^\n]+)', blk) or [None, None])[1] or '').strip() or None
        jul, pub = g('Julgado em'), g('Acórdão publicado em')
        procs.append({'numero': m.group(1), 'origem': g('Tribunal de Origem'), 'relator': (g('Relator') or '').title() or None,
                      'julgado': None if jul in (None, '-') else jul, 'publicado': None if pub in (None, '-') else pub})
    orgao = campo('Órgão julgador', 'Ramo do direito')
    return {'numero': str(n), 'situacao': campo('Situação', 'Órgão julgador'), 'orgao': orgao.title() if orgao else None,
            'ramo': campo('Ramo do direito', 'Questão'),
            'questao': campo('Questão submetida a julgamento', 'Tese Firmada|Anotações|Informações|Referência|REsp'),
            'tese': campo('Tese Firmada', 'Anotações|Informações|Referência|REsp|Delimitação') or None,
            'processos': procs, 'url': URL.format(n=n)}
