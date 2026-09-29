"""Hook PostToolUse: confere cada JSON de conteudo/ logo depois de uma edição.

Recusa JSON inválido e travessão (em dash), a mesma regra que coletor/relacionar.py
aplica às relações. Em conteudo/eleicoes/, roda também a validação de integridade do
Mapa Eleitoral (chaves, enumerações, isolamento das fixtures) e confere os fundamentos
contra a redação vigente do Mapa Normativo. Saída com código 2 devolve a mensagem ao
Claude para correção.
"""
import json, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    evento = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
caminho = (evento.get('tool_input') or {}).get('file_path') or ''
rel = os.path.relpath(os.path.abspath(caminho), RAIZ) if caminho else ''
if not (rel.startswith('conteudo' + os.sep) and rel.endswith('.json')) or not os.path.exists(caminho):
    sys.exit(0)

texto = open(caminho, encoding='utf-8').read()
try:
    json.loads(texto)
except ValueError as e:
    print('%s: JSON inválido (%s). Corrija antes de seguir.' % (rel, e), file=sys.stderr)
    sys.exit(2)

linhas = [str(i) for i, l in enumerate(texto.splitlines(), 1) if '—' in l]
if linhas:
    print('%s: travessão nas linhas %s. Substitua por vírgula ou parênteses.' % (rel, ', '.join(linhas[:10])), file=sys.stderr)
    sys.exit(2)

if rel.startswith(os.path.join('conteudo', 'eleicoes') + os.sep):
    sys.path.insert(0, os.path.join(RAIZ, 'coletor', 'eleicoes'))
    import repositorio, normativo  # noqa: E402
    banco = repositorio.carregar(RAIZ)
    erros, _ = banco.validar()
    erros += normativo.conferir_todas(banco.tabelas['regras'])[0]
    if erros:
        print('%s: o Mapa Eleitoral ficou inconsistente:\n- %s' % (rel, '\n- '.join(erros[:15])), file=sys.stderr)
        sys.exit(2)
