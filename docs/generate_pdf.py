"""
Converte GUIA_PARA_O_DONO.md para PDF com links clicáveis.
Uso: python docs/generate_pdf.py
"""
import os
import io
import markdown
from xhtml2pdf import pisa

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MD_FILE = os.path.join(BASE_DIR, 'GUIA_PARA_O_DONO.md')
PDF_FILE = os.path.join(BASE_DIR, 'GUIA_PARA_O_DONO.pdf')

with open(MD_FILE, encoding='utf-8') as f:
    md_content = f.read()

html_body = markdown.markdown(
    md_content,
    extensions=['tables', 'toc'],
)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<style>
  @page {{
    size: A4;
    margin: 2.2cm 2.5cm 2.2cm 2.5cm;
  }}
  body {{
    font-family: Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.65;
    color: #1a1a1a;
  }}
  h1 {{
    font-size: 20pt;
    color: #cc8800;
    border-bottom: 2px solid #cc8800;
    padding-bottom: 0.3em;
    margin-top: 0;
  }}
  h2 {{
    font-size: 14pt;
    color: #1a1a1a;
    border-bottom: 1px solid #dddddd;
    padding-bottom: 0.2em;
    margin-top: 1.8em;
  }}
  h3 {{
    font-size: 11.5pt;
    color: #333333;
    margin-top: 1.4em;
  }}
  blockquote {{
    border-left: 3px solid #cc8800;
    margin: 0.8em 0;
    padding: 0.4em 1em;
    background: #fffbf0;
    color: #555555;
  }}
  a {{
    color: #0066cc;
    text-decoration: underline;
  }}
  code {{
    background: #f5f5f5;
    font-family: Courier, monospace;
    font-size: 10pt;
    padding: 1px 4px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 10pt;
    margin: 1em 0;
  }}
  th {{
    background: #f0f0f0;
    border: 1px solid #cccccc;
    padding: 5px 8px;
    text-align: left;
    font-weight: bold;
  }}
  td {{
    border: 1px solid #dddddd;
    padding: 5px 8px;
    vertical-align: top;
  }}
  ul, ol {{
    padding-left: 1.5em;
    margin: 0.4em 0;
  }}
  li {{ margin-bottom: 0.2em; }}
  p {{ margin: 0.5em 0; }}
  hr {{
    border-top: 1px solid #e0e0e0;
    margin: 1.5em 0;
  }}
</style>
</head>
<body>
{body}
</body>
</html>"""

html_full = HTML_TEMPLATE.format(body=html_body)

print(f"Gerando PDF: {PDF_FILE}")
with open(PDF_FILE, 'wb') as pdf_out:
    result = pisa.CreatePDF(io.StringIO(html_full), dest=pdf_out)

if result.err:
    print(f"Erro ao gerar PDF: {result.err}")
else:
    size_kb = os.path.getsize(PDF_FILE) // 1024
    print(f"PDF gerado com sucesso! ({size_kb} KB)")
