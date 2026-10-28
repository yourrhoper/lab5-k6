"""Сборка отчёта ЛР5 на основе титульного листа и стилей примера отчёта."""
import json, os, re, shutil, subprocess, sys, zipfile
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from docxlib import p, h1, h2, bullets, caption_table, caption_fig, table, code, image

EX_DIR = sys.argv[1]          # распакованный пример
RES = sys.argv[2]             # results/
OUT = sys.argv[3]             # итоговый .docx
BUL = 12                      # маркированный список из примера
W = 10106                     # ширина набора: 11906 - 2*900

A = json.load(open(os.path.join(RES, 'analysis.json'), encoding='utf8'))
S = {k: json.load(open(os.path.join(RES, f'{k}-summary.json'), encoding='utf8')) for k in ('load', 'stress', 'spike', 'stress-async')
     if os.path.exists(os.path.join(RES, f'{k}-summary.json'))}
from content import body  # noqa: E402  (текст отчёта)

# ---------- подготовка пакета ----------
work = OUT + '.d'
shutil.rmtree(work, ignore_errors=True)
shutil.copytree(EX_DIR, work)
doc_path = os.path.join(work, 'word', 'document.xml')
d = open(doc_path, encoding='utf8').read()

# титульный лист: всё до абзаца «Красноярск 2026» включительно (с разрывом страницы)
i = d.find('Красноярск 2026')
end_title = d.find('</w:p>', i) + len('</w:p>')
title = d[:end_title]
sect = d[d.rfind('<w:sectPr'):]

title = title.replace('РАБОТЕ №2', 'РАБОТЕ №5')
title = title.replace('Форма подачи достижения по культурно-творческой деятельности в личном ',
                      'Нагрузочное тестирование формы подачи культурно-творческого ')
title = title.replace('кабинете студента университета Решетнёва', 'достижения в личном кабинете студента университета Решетнёва')

# ---------- картинки ----------
media = os.path.join(work, 'word', 'media'); os.makedirs(media, exist_ok=True)
rels_path = os.path.join(work, 'word', '_rels', 'document.xml.rels')
rels = open(rels_path, encoding='utf8').read()
images = {}
IMG_DIR = os.path.join(os.path.dirname(__file__), 'img')
for n, name in enumerate(['load-chart.png', 'stress-chart.png', 'spike-chart.png', 'stress-async-chart.png', 'load-dashboard.png', 'form-list.png', 'form-top.png', 'form-bottom.png'], start=1):
    src = os.path.join(RES, name) if os.path.exists(os.path.join(RES, name)) else os.path.join(IMG_DIR, name)
    if not os.path.exists(src):
        continue
    shutil.copy(src, os.path.join(media, f'lab5_{name}'))
    rid = f'rIdLab5Img{n}'
    rels = rels.replace('</Relationships>', f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/lab5_{name}"/></Relationships>')
    w, h = Image.open(src).size
    width_in = {'form-list.png': 6.6, 'form-top.png': 5.2, 'form-bottom.png': 5.2, 'load-dashboard.png': 6.6}.get(name, 6.3)
    cx = int(width_in * 914400)
    images[name] = (rid, cx, int(cx * h / w), 900 + n, name)
open(rels_path, 'w', encoding='utf8').write(rels)
ct_path = os.path.join(work, '[Content_Types].xml')
ct = open(ct_path, encoding='utf8').read()
if 'Extension="png"' not in ct:
    ct = ct.replace('<Default Extension="xml"', '<Default Extension="png" ContentType="image/png"/><Default Extension="xml"')
open(ct_path, 'w', encoding='utf8').write(ct)

def img(name):
    return image(*images[name]) if name in images else ''

xml = title + body(A, S, img, W, BUL) + sect
# убедиться, что пространства имён для рисунков объявлены в корне
for ns, uri in (('wp', 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'), ('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')):
    assert f'xmlns:{ns}="{uri}"' in xml[:5000], ns
open(doc_path, 'w', encoding='utf8').write(xml)

if os.path.exists(OUT): os.remove(OUT)
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    ct_first = '[Content_Types].xml'
    z.write(os.path.join(work, ct_first), ct_first)
    for root, _, files in os.walk(work):
        for f in files:
            full = os.path.join(root, f); arc = os.path.relpath(full, work)
            if arc != ct_first: z.write(full, arc)
shutil.rmtree(work)
print('OK', OUT)
