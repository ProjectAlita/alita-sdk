import os
from md2pdf import md2pdf

curdir = os.path.dirname(os.path.abspath(__file__))
css_path = os.path.join(curdir, "markdown.css")

def md_to_pdf(md_text: str, pdf_file_path: str):
    md2pdf(pdf_file_path, md_text, css_file_path=css_path)
