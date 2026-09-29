"""Monta docs/index.html a partir das peças versionadas em web/.

Uso: python3 coletor/paginar.py

Peças:
  web/head.html      metatags e título, até o link do Google Fonts (fixo)
  web/app_css.html   estilo do app (a <style> completa)
  web/app_body.html  corpo da página, com o script embutido
  web/logo.txt       logo do escritório em data URI, colado onde %%LOGO%% aparece em app_body.html
  web/eleicoes_css.html   estilo do Mapa Eleitoral
  web/eleicoes_filtros.js funções puras de rota, filtro e paginação do Mapa Eleitoral (testadas em testes/js/)
  web/eleicoes.js         interface do Mapa Eleitoral, registrada como módulo do app

Não editar docs/index.html diretamente: ele é gerado. Editar as peças em web/ e rodar este script.
"""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, 'web')
OUT = os.path.join(RAIZ, 'docs', 'index.html')

RESET = ('<style>:root{box-sizing:border-box}body{margin:0;padding:0;'
         'padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
         'img{max-width:100%}[hidden]{display:none!important}</style>')


def ler(nome):
    return open(os.path.join(WEB, nome), encoding='utf-8').read()


def montar():
    head = ler('head.html')
    css = ler('app_css.html')
    body = ler('app_body.html')
    logo = ler('logo.txt').strip()
    body = body.replace('%%LOGO%%', logo)
    css += '\n' + ler('eleicoes_css.html')
    modulos = ''.join(f'<script>\n{ler(n)}\n</script>\n' for n in ('eleicoes_filtros.js', 'eleicoes.js'))
    pagina = f"{head}\n{RESET}\n{css}\n</head><body>\n{body}\n{modulos}</body></html>"
    if '—' in pagina:
        raise SystemExit('Travessão encontrado na página montada; corrija antes de publicar.')
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(pagina)
    return len(pagina)


if __name__ == '__main__':
    n = montar()
    print(f'docs/index.html montado ({n} bytes) a partir de web/')
