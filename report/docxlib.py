"""Минимальный генератор WordprocessingML в стиле примера отчёта (TNR 14, отступ 1,25 см, по ширине)."""
from xml.sax.saxutils import escape

FONT = '<w:rFonts w:ascii="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'


def _rpr(size=28, bold=False, italic=False, mono=False, color=None):
    f = '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>' if mono else FONT
    return ('<w:rPr>' + f + ('<w:b/><w:bCs/>' if bold else '') + ('<w:i/><w:iCs/>' if italic else '')
            + (f'<w:color w:val="{color}"/>' if color else '')
            + f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/><w:lang w:val="ru-RU" w:eastAsia="ru-RU"/></w:rPr>')


def runs(text, size=28, mono=False, italic=False):
    """Текст с **жирными** фрагментами."""
    out = []
    parts = text.split('**')
    for i, part in enumerate(parts):
        if not part:
            continue
        out.append(f'<w:r>{_rpr(size, bold=(i % 2 == 1), italic=italic, mono=mono)}<w:t xml:space="preserve">{escape(part)}</w:t></w:r>')
    return ''.join(out)


def p(text, jc='both', first=709, size=28, before=0, after=0, italic=False, keep=False, page_break_before=False):
    ppr = (f'<w:pPr>{"<w:keepNext/>" if keep else ""}{"<w:pageBreakBefore/>" if page_break_before else ""}'
           f'<w:suppressAutoHyphens w:val="0"/><w:spacing w:before="{before}" w:after="{after}" w:line="240" w:lineRule="auto"/>'
           f'<w:ind w:firstLine="{first}"/><w:jc w:val="{jc}"/></w:pPr>')
    return f'<w:p>{ppr}{runs(text, size, italic=italic)}</w:p>'


def h1(text, page_break=False):
    """Заголовок раздела: жирный, с outline-уровнем (как в примере)."""
    ppr = (f'<w:pPr><w:keepNext/>{"<w:pageBreakBefore/>" if page_break else ""}<w:suppressAutoHyphens w:val="0"/>'
           '<w:spacing w:before="240" w:after="120" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="709"/><w:jc w:val="both"/>'
           '<w:outlineLvl w:val="0"/></w:pPr>')
    return f'<w:p>{ppr}<w:r>{_rpr(28, bold=True)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def h2(text):
    ppr = ('<w:pPr><w:keepNext/><w:suppressAutoHyphens w:val="0"/><w:spacing w:before="120" w:after="60" w:line="240" w:lineRule="auto"/>'
           '<w:ind w:firstLine="709"/><w:jc w:val="both"/><w:outlineLvl w:val="1"/></w:pPr>')
    return f'<w:p>{ppr}<w:r>{_rpr(28, bold=True)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def bullets(items, num_id):
    out = []
    for it in items:
        out.append(f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr>'
                   '<w:tabs><w:tab w:val="left" w:pos="993"/></w:tabs><w:suppressAutoHyphens w:val="0"/>'
                   '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:left="0" w:firstLine="709"/><w:jc w:val="both"/></w:pPr>'
                   f'{runs(it)}</w:p>')
    return ''.join(out)


def caption_table(text):
    return (f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="120" w:after="60"/><w:ind w:firstLine="0"/><w:jc w:val="left"/></w:pPr>'
            f'{runs(text)}</w:p>')


def caption_fig(text):
    return (f'<w:p><w:pPr><w:spacing w:before="60" w:after="160"/><w:ind w:firstLine="0"/><w:jc w:val="center"/></w:pPr>'
            f'{runs(text)}</w:p>')


def table(header, rows, widths, size=24, align=None, bold_first_col=False):
    """widths в DXA; align — список 'left'/'center' по колонкам."""
    align = align or ['left'] * len(widths)
    total = sum(widths)
    grid = ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths)

    def cell(txt, w, jc, bold=False, shade=None):
        sh = f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>' if shade else ''
        paras = ''
        for line in str(txt).split('\n'):
            t = f'**{line}**' if bold and line else line
            paras += (f'<w:p><w:pPr><w:keepNext/><w:suppressAutoHyphens w:val="0"/><w:spacing w:before="0" w:after="0"/><w:ind w:firstLine="0"/>'
                      f'<w:jc w:val="{jc}"/></w:pPr>{runs(t, size)}</w:p>')
        return f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{sh}<w:vAlign w:val="center"/></w:tcPr>{paras}</w:tc>'

    trs = ['<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>' + ''.join(cell(h, w, 'center', True, 'F2F2F2') for h, w in zip(header, widths)) + '</w:tr>']
    for r in rows:
        trs.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + ''.join(
            cell(v, w, a, bold=(bold_first_col and i == 0)) for i, (v, w, a) in enumerate(zip(r, widths, align))) + '</w:tr>')
    return (f'<w:tbl><w:tblPr><w:tblStyle w:val="af6"/><w:tblW w:w="{total}" w:type="dxa"/><w:jc w:val="center"/>'
            '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
            f'<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
            f'<w:tblGrid>{grid}</w:tblGrid>{"".join(trs)}</w:tbl>' + '<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr></w:p>')


def code(lines, size=18):
    """Листинг: моноширинный шрифт, серый фон, одинарный интервал."""
    out = []
    for i, ln in enumerate(lines):
        keep = '<w:keepNext/>' if i < len(lines) - 1 else ''
        out.append(f'<w:p><w:pPr>{keep}<w:shd w:val="clear" w:color="auto" w:fill="F4F4F2"/><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
                   f'<w:ind w:left="284" w:right="284" w:firstLine="0"/><w:jc w:val="left"/></w:pPr>'
                   f'<w:r>{_rpr(size, mono=True)}<w:t xml:space="preserve">{escape(ln) if ln else " "}</w:t></w:r></w:p>')
    return ''.join(out)


def image(rid, cx_emu, cy_emu, pid, name):
    return ('<w:p><w:pPr><w:keepNext/><w:spacing w:before="120" w:after="0"/><w:ind w:firstLine="0"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx_emu}" cy="{cy_emu}"/><wp:docPr id="{pid}" name="{name}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{pid}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
