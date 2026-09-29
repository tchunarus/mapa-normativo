"""Hook PreToolUse: impede edição manual dos dados gerados pelos scripts.

docs/data/ e os arquivos de auditoria de estado/ só mudam por coletor/*.py; editar à
mão rompe a comparação por hash e o histórico de mudanças. O mesmo vale para
estado/eleicoes/ (candidaturas do TSE, snapshots, análises e log de ingestão), que só
muda por coletor/eleicoes/. Os scripts rodam pelo Bash e não passam por este hook.
"""
import json, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTAS = ('docs/data/', 'estado/eleicoes/')
ARQUIVOS = ('estado/hashes.json', 'estado/changelog.json', 'estado/etags.json')

try:
    evento = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
caminho = (evento.get('tool_input') or {}).get('file_path') or ''
if not caminho:
    sys.exit(0)
rel = os.path.relpath(os.path.abspath(caminho), RAIZ).replace(os.sep, '/')
if rel.startswith(PASTAS) or rel in ARQUIVOS:
    dica = ('Altere conteudo/eleicoes/ ou coletor/eleicoes/ e rode python3 coletor/eleicoes/analisar.py e '
            'python3 coletor/eleicoes/publicar.py.' if 'eleicoes' in rel else
            'Altere conteudo/ ou coletor/ e rode python3 coletor/atualizar.py --sem-rede.')
    print('%s é gerado pelos scripts e não pode ser editado à mão. %s' % (rel, dica), file=sys.stderr)
    sys.exit(2)
