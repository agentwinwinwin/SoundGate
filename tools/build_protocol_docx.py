from pathlib import Path
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs' / 'SoundGate终端平台MQTT通信协议.md'
OUTPUT = ROOT / 'docs' / 'SoundGate终端平台MQTT通信协议V1.0.docx'

NAVY = '17365D'
BLUE = '246BCE'
PALE = 'EAF2FB'
LIGHT = 'F5F7FA'
GRID = 'CBD5E1'
MUTED = RGBColor(82, 96, 115)
CN_FONT = 'PingFang SC'


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd')
        tc_pr.append(shd)
    shd.set(qn('w:fill'), fill)


def cell_margins(cell, top=70, start=90, bottom=70, end=90):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in('w:tcMar')
    if tc_mar is None:
        tc_mar = OxmlElement('w:tcMar')
        tc_pr.append(tc_mar)
    for m, v in [('top', top), ('start', start), ('bottom', bottom), ('end', end)]:
        node = tc_mar.find(qn(f'w:{m}'))
        if node is None:
            node = OxmlElement(f'w:{m}')
            tc_mar.append(node)
        node.set(qn('w:w'), str(v))
        node.set(qn('w:type'), 'dxa')


def set_repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement('w:tblHeader')
    tbl_header.set(qn('w:val'), 'true')
    tr_pr.append(tbl_header)


def prevent_row_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement('w:cantSplit')
    tr_pr.append(cant_split)


def set_cell_text(cell, text, bold=False, color=None, size=8.5):
    cell.text = ''
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(text.strip())
    r.bold = bold
    r.font.name = CN_FONT
    r._element.rPr.rFonts.set(qn('w:eastAsia'), CN_FONT)
    r.font.size = Pt(size)
    if color:
        r.font.color.rgb = RGBColor.from_string(color)


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.add_run('第 ')
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    paragraph._p.append(fld)
    paragraph.add_run(' 页')


def add_inline(paragraph, text, bold=False):
    parts = re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith('`') and part.endswith('`'):
            run = paragraph.add_run(part[1:-1])
            run.font.name = 'Menlo'
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor.from_string(BLUE)
        elif part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            run = paragraph.add_run(part)
            run.bold = bold


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Inches(8.5)
    sec.page_height = Inches(11)
    sec.top_margin = Inches(0.68)
    sec.bottom_margin = Inches(0.65)
    sec.left_margin = Inches(0.72)
    sec.right_margin = Inches(0.72)

    styles = doc.styles
    normal = styles['Normal']
    normal.font.name = CN_FONT
    normal._element.rPr.rFonts.set(qn('w:eastAsia'), CN_FONT)
    normal.font.size = Pt(10.2)
    normal.font.color.rgb = RGBColor(31, 41, 55)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.18

    for name, size, color in [('Title', 26, NAVY), ('Heading 1', 17, NAVY), ('Heading 2', 13, BLUE), ('Heading 3', 11, NAVY)]:
        st = styles[name]
        st.font.name = CN_FONT
        st._element.rPr.rFonts.set(qn('w:eastAsia'), CN_FONT)
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor.from_string(color)
        st.paragraph_format.keep_with_next = True
        st.paragraph_format.space_before = Pt(10 if name != 'Title' else 0)
        st.paragraph_format.space_after = Pt(5)

    header = sec.header.paragraphs[0]
    header.text = 'SoundGate 终端与平台 MQTT 通信协议    |    V1.0'
    header.style = styles['Normal']
    header.runs[0].font.size = Pt(8.5)
    header.runs[0].font.color.rgb = MUTED
    footer = sec.footer.paragraphs[0]
    footer.style = styles['Normal']
    footer.runs.clear()
    add_page_number(footer)
    for r in footer.runs:
        r.font.size = Pt(8)
        r.font.color.rgb = MUTED

    # Cover
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(54)
    r = p.add_run('SoundGate')
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = RGBColor.from_string(BLUE)
    p = doc.add_paragraph(style='Title')
    p.add_run('终端与平台 MQTT 通信协议')
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(30)
    r = p.add_run('面向单片机终端、4G 模块、OneNET 平台与 SoundGate 后端的联调规范')
    r.font.size = Pt(12)
    r.font.color.rgb = MUTED

    meta = doc.add_table(rows=4, cols=2)
    meta.autofit = False
    meta.columns[0].width = Inches(1.35)
    meta.columns[1].width = Inches(5.4)
    for i, (k, v) in enumerate([
        ('文档版本', 'V1.0'), ('发布日期', '2026 年 9 月 23 日'),
        ('单帧限制', 'MQTT Payload ≤ 200 字节（UTF-8 实际字节数）'),
        ('适用人员', '终端固件、通信模块、平台后端、前端与联调测试人员'),
    ]):
        shade(meta.cell(i, 0), PALE)
        set_cell_text(meta.cell(i, 0), k, True, NAVY, 10)
        set_cell_text(meta.cell(i, 1), v, False, None, 10)
        for c in meta.rows[i].cells:
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell_margins(c, 110, 110, 110, 110)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(28)
    r = p.add_run('文档状态：联调基线')
    r.bold = True
    r.font.color.rgb = RGBColor.from_string(NAVY)
    p = doc.add_paragraph('本协议把已通过真实终端验证的能力与待固件确认的能力分开标注。任何“待确认”项在双方确认前不得作为量产验收依据。')
    p.paragraph_format.space_after = Pt(0)
    doc.add_page_break()

    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    # Skip source title and metadata already represented by cover.
    i = 5
    in_code = False
    code_lines = []
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            if not in_code:
                in_code = True
                code_lines = []
            else:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.18)
                p.paragraph_format.right_indent = Inches(0.18)
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(7)
                pPr = p._p.get_or_add_pPr()
                shd = OxmlElement('w:shd')
                shd.set(qn('w:fill'), LIGHT)
                pPr.append(shd)
                r = p.add_run('\n'.join(code_lines))
                r.font.name = 'Menlo'
                r.font.size = Pt(8.2)
                r.font.color.rgb = RGBColor(31, 41, 55)
                in_code = False
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-{3,}:?', c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                tbl = doc.add_table(rows=len(rows), cols=len(rows[0]))
                tbl.style = 'Table Grid'
                tbl.autofit = True
                set_repeat_header(tbl.rows[0])
                for ri, row in enumerate(rows):
                    prevent_row_split(tbl.rows[ri])
                    for ci, val in enumerate(row):
                        cell = tbl.cell(ri, ci)
                        set_cell_text(cell, val, ri == 0, 'FFFFFF' if ri == 0 else None, 7.7 if len(rows[0]) >= 6 else 8.5)
                        shade(cell, NAVY if ri == 0 else (PALE if ri % 2 == 0 else 'FFFFFF'))
                        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                        cell_margins(cell)
                doc.add_paragraph().paragraph_format.space_after = Pt(1)
            continue
        if line.startswith('# '):
            i += 1
            continue
        if line.startswith('## '):
            doc.add_heading(line[3:].strip(), level=1)
        elif line.startswith('### '):
            doc.add_heading(line[4:].strip(), level=2)
        elif re.match(r'^\d+\. ', line):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.first_line_indent = Inches(-0.25)
            p.paragraph_format.space_after = Pt(3)
            add_inline(p, line)
        elif line.startswith('- '):
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_after = Pt(3)
            add_inline(p, line[2:])
        else:
            p = doc.add_paragraph()
            add_inline(p, line)
        i += 1

    # Core properties should start together where possible.
    for table in doc.tables:
        table.rows[0]._tr.get_or_add_trPr()

    core = doc.core_properties
    core.title = 'SoundGate终端与平台MQTT通信协议'
    core.subject = '终端控制参数、状态上报、文件传输和后端接口规范'
    core.author = 'SoundGate 项目组'
    core.keywords = 'SoundGate, MQTT, OneNET, 单片机, 通信协议, 文件传输'
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == '__main__':
    build()
