"""Conservative evidence-based draft, explicitly using only verified run outputs."""
import json
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def generate_draft(meta,results,language='zh'):
    module=meta.get('module','未知'); params=meta.get('parameters',{})
    pair=results if isinstance(results,dict) else {}
    if language=='en':
        chunks=[f'# Draft evidence note — {module}',
          '\n## Reproducible processing methods (fill in missing study details)',
          'Data were processed using Research Toolbox v'+str(meta.get('version','?'))+'.',
          'The software workflow, user-selected parameters, and input-file SHA-256 fingerprints were archived.',
          'Parameter record:\n'+', '.join(f'{k} = {v}' for k,v in params.items()),
          '\n**TO CONFIRM:** instrument model, acquisition settings, calibration method, sample selection/exclusions, true experimental unit, sample size, and ethics approvals (if relevant).',
          '\n## Machine-computed observations (NOT inferential conclusions)',
          '\n'.join(f'- {k}: {v}' for k,v in pair.items() if k not in ('warning','warnings')),
          '\n## Figure-caption scaffold',f'Figure X. {module} analysis. Source: original experimental dataset. '+
          'Calibration, n (independent specimens), uncertainty definition and algorithm settings MUST be filled in.',
          '\n## Cautions','- This text is an editable draft, not a ready-to-submit manuscript.',
          '- No references or causal/mechanistic interpretations were generated.']
    else:
        chunks=[f'# 分析结果写作草稿 — {module}',
          '\n## 数据处理方法（实验信息）',
          '使用 Research Toolbox v'+str(meta.get('version','?'))+'处理数据。',
          '处理参数：'+ '；'.join(f'{k} = {v}' for k,v in params.items()),
          '\n**需要补充**：实验信息。',
          '\n## 计算结果摘录',
          '\n'.join(f'- {k}：{v}' for k,v in pair.items() if k not in ('warning','warnings'))]
    return '\n\n'.join(str(x) for x in chunks)

def export_docx(text,path):
    document=Document(); sec=document.sections[0]
    sec.top_margin=Inches(.75);sec.bottom_margin=Inches(.7)
    for style_name in ('Normal','Heading 1','Heading 2','List Bullet'):
        style=document.styles[style_name]
        style.font.name='Times New Roman'
        rpr=style.element.get_or_add_rPr()
        rfonts=rpr.rFonts
        if rfonts is None:
            rfonts=OxmlElement('w:rFonts')
            rpr.insert(0,rfonts)
        rfonts.set(qn('w:ascii'),'Times New Roman')
        rfonts.set(qn('w:hAnsi'),'Times New Roman')
        rfonts.set(qn('w:eastAsia'),'微软雅黑')
        rfonts.set(qn('w:cs'),'Times New Roman')
    document.styles['Normal'].font.size=Pt(10)
    for para in text.split('\n'):
        p=para.strip()
        if not p:continue
        if p.startswith('## '):document.add_heading(p[3:],level=2)
        elif p.startswith('# '):document.add_heading(p[2:],level=1)
        elif p.startswith('- '):document.add_paragraph(p[2:],style='List Bullet')
        else:document.add_paragraph(p.replace('**',''))
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            run.font.name='Times New Roman'
            rpr=run._element.get_or_add_rPr()
            rfonts=rpr.rFonts
            if rfonts is None:
                rfonts=OxmlElement('w:rFonts')
                rpr.insert(0,rfonts)
            rfonts.set(qn('w:ascii'),'Times New Roman')
            rfonts.set(qn('w:hAnsi'),'Times New Roman')
            rfonts.set(qn('w:eastAsia'),'微软雅黑')
            rfonts.set(qn('w:cs'),'Times New Roman')
    document.save(str(path))
