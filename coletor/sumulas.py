"""Súmulas do STJ a partir do PDF oficial de verbetes."""
import re, subprocess

URL = 'https://www.stj.jus.br/docs_internet/VerbetesSTJ_asc.pdf'


def todas(destino):
    subprocess.run(['curl', '-sL', '--max-time', '120', '-A', 'Mozilla/5.0', '-o', destino, URL])
    from pypdf import PdfReader
    t = '\n'.join(p.extract_text() for p in PdfReader(destino).pages)
    partes = re.split(r'\n?\s*Súmula (\d+)\s*\n', t)
    out = {}
    for i in range(1, len(partes) - 1, 2):
        corpo = re.sub(r'\s+', ' ', partes[i + 1]).strip()
        corpo = re.sub(r'\s*Súmulas do Superior Tribunal de Justiça Página \d+ de \d+\s*$', '', corpo).strip()
        out[partes[i]] = corpo
    return out
