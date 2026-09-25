"""Download e extração de artigos da legislação compilada do Planalto.

Cada artigo vira {r, h, l, rev, hash}: rótulo, hierarquia (Livro › Título ›
Capítulo › Seção), linhas [texto, nota de alteração] e flag de revogação.
O texto riscado (<strike>) da compilação, que é redação revogada, é descartado.
"""
import hashlib, html, re, subprocess, time

UA = "Mozilla/5.0"

NOTE = re.compile(r'\((?:Artigo incluído|Artigo acrescentado|Parágrafo incluído|Redação dada|Incluíd[oa]|Revogad[oa]|Vide|Acrescentad[oa]|Renumerad[oa]|Produção de efeito|Vigência|Regulamento|Redação\s)[^()]*(?:\([^()]*\)[^()]*)*\)')
ART = re.compile(r'^Art\.\s*(\d+(?:\.\d+)?)(?:-([A-Z])(?=[\.\s]))?(?:º|°|o)?[\.\s\-]', re.M)
HEAD = re.compile(r'^(LIVRO|TÍTULO|CAPÍTULO|SEÇÃO|Seção|Subseção)\b[^\n]*(?:\n(?!Art\.)[^\n]{2,120})?', re.M)
NIVEIS = ['livro', 'titulo', 'capitulo', 'secao', 'subsecao']


def baixar(url, destino, tentativas=15, timeout=170):
    """Baixa com retomada (a conexão do Planalto costuma cair em arquivos grandes).

    O arquivo está completo quando o curl termina sem erro e a página contém </html>;
    o Planalto acrescenta um script depois dessa marca, por isso o arquivo inteiro é lido.
    """
    for _ in range(tentativas):
        r = subprocess.run(['curl', '-sSL', '--fail', '--max-time', str(timeout), '-C', '-', '-A', UA, '-o', destino, url], capture_output=True)
        try:
            dados = open(destino, 'rb').read()
        except FileNotFoundError:
            dados = b''
        if r.returncode in (0, 33) and len(dados) > 2000 and b'</html>' in dados.lower():
            return True
        time.sleep(2)
    return False


def cabecalho(url):
    """ETag e data de modificação da página (sem baixar o conteúdo)."""
    r = subprocess.run(['curl', '-sI', '--max-time', '40', '-A', UA, url], capture_output=True)
    h = {}
    for linha in r.stdout.decode('latin-1').splitlines():
        if ':' in linha:
            k, v = linha.split(':', 1)
            h[k.strip().lower()] = v.strip()
    return {'etag': h.get('etag'), 'modificado': h.get('last-modified')} if r.returncode == 0 and h else None


def carregar(caminho):
    raw = open(caminho, 'rb').read()
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp1252')


def limpar(t):
    t = re.sub(r'(?is)<(script|style|head).*?</\1>', '', t)
    t = re.sub(r'(?is)<(strike|s|del)\b.*?</\1>', '', t)
    t = t.replace('\r', ' ').replace('\n', ' ')
    t = re.sub(r'(?i)<br\s*/?>|</p>|</h\d>|</div>|</tr>', '\n', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = html.unescape(t).replace('\xa0', ' ')
    t = re.sub(r'[ \t]+', ' ', t)
    t = '\n'.join(l.strip() for l in t.split('\n'))
    return re.sub(r'\n+', '\n', t)


def rotulo(n):
    base, _, suf = n.partition('-')
    b = int(base)
    lab = f'{b:,}'.replace(',', '.') if b >= 1000 else str(b)
    return f'Art. {lab}' + ('º' if b < 10 else '') + (f'-{suf}' if suf else '')


def artigos(t, so_numericos=False):
    ms = list(ART.finditer(t))
    heads = [(h.start(), h.group(1).upper(), h.group(0)) for h in HEAD.finditer(t)]
    out = {}
    for i, m in enumerate(ms):
        num = m.group(1).replace('.', '') + ('-' + m.group(2) if m.group(2) else '')
        if num in out or (so_numericos and '-' in num):
            continue
        corpo = t[m.start(): ms[i + 1].start() if i + 1 < len(ms) else len(t)]
        keep = []
        for l in corpo.split('\n'):
            if re.match(r'^(LIVRO|TÍTULO|CAPÍTULO|Seção|SEÇÃO|Subseção|DISPOSIÇÕES|Disposições|ATO DAS DISPOSIÇÕES)\b', l):
                break
            keep.append(l)
        corpo = '\n'.join(keep).strip()
        hier = {}
        for pos, kind, txt in heads:
            if pos > m.start():
                break
            k = {'LIVRO': 'livro', 'TÍTULO': 'titulo', 'CAPÍTULO': 'capitulo', 'SEÇÃO': 'secao', 'SUBSEÇÃO': 'subsecao'}.get(kind, 'secao')
            hier[k] = re.sub(r'\s+', ' ', NOTE.sub('', txt)).strip()
            for lower in NIVEIS[NIVEIS.index(k) + 1:]:
                hier.pop(lower, None)
        linhas = []
        for l in corpo.split('\n'):
            ns = [re.sub(r'\s+', ' ', n).strip('() ') for n in NOTE.findall(l)]
            lt = re.sub(r'\s{2,}', ' ', NOTE.sub('', l)).strip()
            if lt or ns:
                linhas.append([lt, '; '.join(ns)])
        texto = '\n'.join(x[0] for x in linhas)
        rev = bool(re.match(r'^Art\.[^\n]{0,20}\(?\s*Revogad', corpo)) or (len(texto) < 40 and any('Revogad' in x[1] for x in linhas))
        out[num] = {'r': rotulo(num), 'h': ' › '.join(hier[k] for k in NIVEIS if k in hier), 'l': linhas, 'rev': rev,
                    'hash': hashlib.sha1(texto.encode()).hexdigest()[:12]}
    return out


def extrair(caminho, fonte):
    """Aplica os recortes definidos no cadastro da fonte (fontes.py)."""
    t = limpar(carregar(caminho))
    corte = fonte.get('corte')
    if corte:
        ini, fim = corte
        a = t.find(ini) if ini else 0
        b = t.find(fim, a + 1) if fim else len(t)
        t = t[a if a >= 0 else 0: b if b > 0 else len(t)]
    arts = artigos(t, so_numericos=fonte.get('so_numericos', False))
    if fonte.get('sel'):
        arts = {k: arts[k] for k in fonte['sel'] if k in arts}
    return arts
