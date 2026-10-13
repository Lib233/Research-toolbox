"""Regenerate complete Chinese README/reference from the editable  guidance files.

Run: python generate_reference_docs.py
No network or GUI window needed. The generated README is ordinary Markdown and may
also be freely edited by the user after generation.
"""
from __future__ import annotations
import inspect
from pathlib import Path
import desktop
from ui_guidance import MODULE_HELP,F,OPTIONS,FILES,field_text, module_text
from ui_explanations_v6 import MODULE_STORIES,COLUMN_HELP,FILE_COLUMNS,RESULT_NAMES,STATUS_TRANSLATIONS

ROOT=Path(__file__).resolve().parent
V7_PREFIX=(ROOT/'docs'/'README_V7_首页.md').read_text(encoding='utf-8')
ORDER=('数据质检','批量力学','力学分析','高级统计','轨迹人工修正','视频追踪','显微图像','信号处理','多源同步','独立样本统计','曲线拟合','公式优化','实验数据优化','分析结果整理','论文绘图')
INTRO='''# Research Toolbox ｜中文科研工具箱完整使用说明与源码编辑指南

> **这是一份可以直接修改的 README 文档。** 它既给初次使用软件的实验研究人员阅读，也给以后自己修改 Python 说明文字的人使用。本文基于历史 、 版本和  的实际修改；示例使用软体机器人/黏附足垫/生物材料等假设实验，不代表已确认具体课题组当前正在做这些实验。

## 一、30 秒理解它是什么

这是 Windows 上运行的本地 Tk/ttk 科研数据辅助程序。它不是自动“做科研”、自动验证机理或自动让数据变好的程序，而是把已有的实验表格、视频、图片和数值公式整理成**可复查的实验指标、统计表、拟合/优化结果和论文图草稿**。

**重要的使用原则：不是每项研究都需要 15 个模块。** 每个模块都先回答“什么时候需要，什么时候根本不需要”，再介绍输入、算法、输出和风险。不能因为软件有某个功能就强迫研究人员使用它。

### 启动与保存

1. 解压完整文件夹到你想放的位置，例如 `D:\\ResearchToolbox_v6.0`；**不要在 ZIP 预览窗口里运行**。
2. 安装 64 位 Python 3.11 或 3.12（原项目的支持范围）；首次双击 `一键启动_Windows.bat` 会尝试通过清华 PyPI 镜像安装 Python 依赖。
3. 在左侧选择功能。输入面板可以上下滚动，顶部先显示精简的用途、适用与不适用场景；点击展开后按小节查看详细实验案例，参数旁边有“？”按钮；右键也能查看详细说明。
4. 点击“使用演示数据”先熟悉格式，核对读入列名、单位、分组、试样身份后再点击“开始分析”。
5. 结果默认保存到程序目录中的 `分析结果/本次运行子文件夹`；可在各模块底部另选结果保存位置。完整 CSV 与 Excel 工作簿继续保留。
6. 结果摘要默认显示三项关键指标与简明文字结论，全部指标折叠，需要时展开再逐项查看中文名称和“？”详细解释，在“结果表格”页直接查看 CSV 前 60 行；到 Excel 汇总工作簿查看完整数据以及**结果字段中文释义**工作表。高清图片页可滚动，按钮不再必须挤在固定窗口高度内。

### 15 个模块一览

| 编号 | 模块 | 一句话含义 |
|---|---|---|
| 01 | 数据质检 | 在分析前检查表格空值、格式、整行重复及可疑读数，不删原始数据 |
| 02 | 批量力学 | 同一实验规程下，一次分析很多份拉离过程拉伸力—位移记录并按试样/组汇总 |
| 03 | 力学分析 | 仔细检查一份表里的拉离峰值、机械功与处理后曲线 |
| 04 | 高级统计 | 根据真实实验设计进行配对、多组、混合模型或不确定度合成 |
| 05 | 轨迹人工修正 | 校正视频追踪算法认错的坐标（计划后续整体重做，本版不改算法） |
| 06 | 视频追踪 | 从简单二维实验视频提取目标位置和有限差分运动速度（本版不改算法） |
| 07 | 显微图像 | 从符合物理成像依据的明/暗区域估计面积、覆盖率和灰度 |
| 08 | 信号处理 | 对传感器时间序列滤波、寻找峰值事件、观察频谱 |
| 09 | 多源同步 | 不同设备采样时刻不同时，按经过核对的时间关系对齐数据 |
| 10 | 独立样本统计 | 同一试样重复测量先合并，再比较独立实验组的统计表现 |
| 11 | 曲线拟合 | 给已有 X–Y 实测点拟合函数，查看预测与残差 |
| 12 | 公式优化 | 已知数学公式时，在变量边界和约束下搜索候选方案 |
| 13 | 实验数据优化 | 不知道准确公式但有历史实验时，建近似模型推荐下一轮参数 |
| 14 | 分析结果整理 | 把已经完成的一次分析的参数与结果整理成 Word/Markdown 草稿 |
| 15 | 论文绘图 | 将经核对的实验数值绘制为 PNG/TIFF/PDF/SVG 并支持后续排版 |

### 什么时候几个模块要配合使用？

- **已有一批黏附/拉离测试：** 数据质检 → 批量力学 → 独立样本统计（必要时）→ 论文绘图 → 分析结果整理。
- **只有一次新的仪器拉力曲线：** 数据质检 → 力学分析，先核对零点、力方向与拉离过程分析时间窗，不必运行所有统计和优化功能。
- **已有显微图：** 显微图像 → 人工检查分割掩膜 → 独立样本统计（前提是存在真正独立样本）。
- **不同仪器同时记录运动与力：** 必要时用多源同步建立统一时间轴。若只是已知恒定时间平移且采样时间点对应，直接用 Excel 完全可以。
- **根据历史实验规划下一轮：** 数据质检 → 实验数据优化 → 新实验验证；预测不等于真实最优。
- **已经有理论公式：** 公式优化，不需要把一个能直接计算的理论问题硬塞进实验数据代理模型。

## 二、所有模块的详细解释、输入参数与用法

下列内容直接来自 `ui_explanations_v6.py` 与 `ui_guidance.py`。你可以编辑这些 Python 文件来同时改变软件界面帮助。本文保留术语及对应英文列名，方便对照程序。
'''

def line(path,pattern):
    p=ROOT/path
    if not p.exists():return '文件不存在'
    for i,t in enumerate(p.read_text(encoding='utf-8').splitlines(),start=1):
        if pattern in t:return str(i)
    return '未找到'

parts=[INTRO]
for idx,name in enumerate(ORDER,1):
    spec=desktop.SPECS[name]
    parts.extend([f'\n### {idx:02d}｜{name}', '',module_text(name),'','#### 逐个输入框的具体含义、填写示例与常见误解',''])
    fields=list(spec['fields']) + (list(desktop.FIGURE_FIELDS) if name not in desktop.NO_FIGURE else [])
    for key,label,kind,default in fields:
        try: explanation=field_text(name,key,label,kind)
        except KeyError:explanation='当前没有可核实的字段专用解释，请在 ui_guidance.py 中补充。'
                                                                             
        parts.extend([f'**{label}**（参数键：`{key}`；默认值：`{default}`）','',explanation,''])
    parts.append('运行后建议先查看 Excel 汇总工作簿中的实际输出表，以及“结果字段中文释义”工作表；数据科学含义仍需按本模块实际实验设计复核。\n')
parts.extend(['\n## 三、软件导出文件分别是干什么的？\n',
 '每次分析默认保留原始字段命名的 CSV，以便 MATLAB/Origin/Excel 使用；**不会把数字悄悄换成中文文本**。另生成中文释义表和结果页关键指标。\n',
 '| 文件名 / 类型 | 具体阅读意义 |','|---|---|'])
for name,help in FILES.items():
    parts.append(f'| `{name}` | {help.replace(chr(10),"；").replace("|","/")} |')
parts.extend(['\n## 四、所有常见英文输出字段的中文释义（可编辑词典）\n',
'运行时会按每次实际生成的表头写出 `结果字段中文释义.csv`、`结果字段逐列说明.md`，并纳入 `analysis_tables.xlsx`。遇到词典未定义的字段，会明确显示“尚未有可靠定义”，避免凭名称编造计算公式。\n',
'| 英文字段 | 中文名称 | 详细定义、单位与误解提醒 |','|---|---|---|'])
for k,(name,description) in sorted(COLUMN_HELP.items()):
    parts.append(f'| `{k}` | {name} | {description.replace("|","/").replace(chr(10),"；")} |')
parts.extend(['\n### 同名 `status` 不能混淆','',
 '`column_quality.csv` 的 status 只是“只标记不删除”；`import_manifest.csv` 的 status 表示文件导入是否成功；优化器的 status 表示候选搜索状态。不同文件使用不同解释，不能见到 OK 就宣称实验证实。','',
 '### 各种状态值的中文说明',''])
for k,v in STATUS_TRANSLATIONS.items():parts.append(f'- `{k}`：{v}')

EDIT_GUIDE='''
## 五、自己改文字、改界面，分别打开哪个 Python 文件？

**最常修改的两个文件，不需要碰任何数学算法：**

- `ui_explanations_v6.py`：`MODULE_STORIES` 是界面顶部大段“真实实验案例、适用情况、什么时候不用”的完整文字；`COLUMN_HELP` 是每个导出列的中文名及解释；`FILE_COLUMNS` 解决不同结果文件中同名字段（特别是 status）含义不同；`RESULT_NAMES` 是结果页中文指标名；`STATUS_TRANSLATIONS` 是英文状态值的中文说明；`write_column_dictionary()` 负责运行后自动生成独立字段词典。
- `ui_guidance.py`：`F` 是每个参数“这是什么、怎么填写、要小心什么”的三段式解释；`OVERRIDES` 是同一个参数键在不同模块的特殊解释；`OPTIONS` 是下拉框每个选项的说明；`FILES` 是输出文件的阅读解释；`field_text()` 负责拼出参数弹窗，`module_text()` 负责模块整段帮助；`files_guide()` 负责结果文件阅读助手。

**如果要调整软件布局，而不是文字：**

- `desktop.py` 的 `SPECS`：改模块名称、每个参数标签、控件类型及默认值。改控件键名时还必须同步核对 `core/workflows.py` 的读取逻辑；切勿只改键名。
- `desktop.py` 的 `FIGURE_FIELDS`：改论文图片共用的尺寸、配色、坐标标题等输入。
- `desktop.py` 的 `_layout()`：主窗口、导航、结果页和图页容器。
- `desktop.py` 的 `switch()`：切换模块时生成帮助文字、各输入框和旁边的 `？`。
- `desktop.py` 的 `_make_graph_view()`：右侧“高清图片”页的**可滚动布局**，包含 SVG 另存、其他格式、放大和重新绘图按钮；`_show_figure()` 控制缩略图尺寸，`_wheel()` 控制鼠标滚动。
- `desktop.py` 的 `_render_result_metrics()`：右侧全部关键结果中文标签/数值/`？` 帮助；`_done()` 把计算摘要显示到结果页。
- `desktop.py` 的 `_make_detail_view()`、`_load_detail_table()`：界面“结果表格”页直接展示 CSV 前 60 行的中文字段名。
- `desktop.py` 的 `open_result_guide()`：输出文件阅读助手与逐列释义。

**如果需要修改实际计算，一定同时增加数值基准测试：**

- `core/common.py` 的 `clean_report()`：逐列数据质检；`locate_quality_issues()`：定位问题具体数据行；`read_table()`：仪器 Excel/CSV 表头与数据读取；`export_result_workbook()`：把 CSV 汇总到 Excel。
- `core/adhesion_protocol.py` 的 `_baseline()`、`analyze_adhesion_protocol()`：拉力零点、拉离过程分析时间窗、峰值和力—位移积分的核心计算。
- `core/batch_force.py` 的 `load_force_folder()`、`specimen_force_summary()`：批量导入单位与独立试样汇总。
- `core/storyboard.py` 的 `force_storyboard()`、`_sample_points()`：力学图中曲线、独立试样点、置信区间以及 a/b/c/d 标题。** 特别修复的统计层级就在这里。**
- `core/stats.py`：独立样本平均、Welch 检验、SD/SEM/CI 与 Bootstrap。
- `core/advanced_stats.py`：配对、多组、混合模型和不确定度（本次保持主要数值算法不变）。
- `core/signals.py`：传感器滤波/峰值/频谱；`core/synchronization.py`、`core/auto_sync.py`：时序插值和时间偏移估计。
- `core/imaging.py`、`core/image_native.py`：图像前景面积与强度。
- `core/fitting.py`、`core/fit_diagnostics.py`：拟合与模型比较。
- `core/optimization.py`、`core/safeexpr.py`：公式优化与安全数学表达式。
- `core/bayesian_design.py`：实验数据代理模型及推荐候选。
- `core/figure_engine.py`、`core/plots.py`：图片外观与导出。修改前核对物理量单位。
- `core/writing.py`：基于 `run_metadata.json` 和 `result_summary.json` 自动生成分析记录草稿；这是**分析结果整理**，不是能自动证明机制的论文写作 AI。
- `core/workflows.py` 的 `run_module()`：15 个模块如何调用数值计算、保存 CSV/Excel/图片、生成本次字段词典。**算法连接流程和输出生成都在这里。**

**这次刻意没改的两个算法：** `core/video.py`（自动视频追踪）与 `core/trajectory_edit.py`（人工轨迹修正），并保留 `core/track_validation.py`。这三份文件可在你以后提出新的追踪方案时整体替换。

### 当前源码行号速查（以本次 ZIP 内源码为准）

| 文件 | 定位关键词/函数 | 起始行号 |
|---|---|---:|
'''
locators=[
 ('ui_explanations_v6.py','MODULE_STORIES='),('ui_explanations_v6.py','COLUMN_HELP='),('ui_explanations_v6.py','FILE_COLUMNS='),('ui_explanations_v6.py','RESULT_NAMES='),('ui_explanations_v6.py','def write_column_dictionary('),
 ('ui_guidance.py','MODULE_HELP='),('ui_guidance.py','F='),('ui_guidance.py','OVERRIDES='),('ui_guidance.py','OPTIONS='),('ui_guidance.py','FILES='),
 ('desktop.py','SPECS='),('desktop.py','FIGURE_FIELDS='),('desktop.py','def _layout('),('desktop.py','def switch('),('desktop.py','def _make_graph_view('),('desktop.py','def _render_result_metrics('),('desktop.py','def _make_detail_view('),('desktop.py','def open_result_guide('),('desktop.py','def _done('),
 ('core/common.py','def clean_report('),('core/common.py','def locate_quality_issues('),('core/common.py','def export_result_workbook('),
 ('core/adhesion_protocol.py','def _baseline('),('core/adhesion_protocol.py','def analyze_adhesion_protocol('),
 ('core/batch_force.py','def load_force_folder('),('core/batch_force.py','def specimen_force_summary('),('core/storyboard.py','def force_storyboard('),
 ('core/workflows.py','def run_module('),('core/writing.py','def generate_draft('),('core/bayesian_design.py','def optimize_bayesian('),('core/design_validation.py','def design_groups('),('core/design_validation.py','def restrict_design_bounds('),
]
for f,needle in locators:EDIT_GUIDE+=f'| `{f}` | `{needle.strip()}` | {line(f,needle)} |\n'
EDIT_GUIDE+='''
### 改完文字怎样看到效果？

修改 `ui_explanations_v6.py` 中某个模块的说明、或 `ui_guidance.py` 中参数解释后：保存文件 → 完全关闭软件 → 再双击 `一键启动_Windows.bat`。**不需要重新 ZIP 打包，也不需要重新安装 Python 依赖。** 如果修改的是独立 README 而不是 Python 字典，软件界面不会自动随之改变。

如果希望按当前字典重新生成这份完整 README，执行：

```bat
.venv\\Scripts\\python.exe generate_reference_docs.py
```

## 六、计算结果到底可不可信？ 基础检查及  新增模型核验

- **在明确公式、单位、实验阶段与独立样本定义下**，峰值、梯形力—位移积分、名义应力、试样平均、Welch 检验等可以用已知答案或 SciPy 的标准函数交叉验证。
- ** 修复了图表与数据层级不一致的问题：** 力学 a 图标注为“每轮测试、基线校正后”；力学 b、c 的点/均值/95% CI 改为按每个独立试样先合并重复循环后计算；d 图改为每块独立试样一个点，名称对应真实数据层级。逐循环 CSV 仍保持原来计算方式，避免破坏可追溯性。
- 数据质检增加了可疑内容的**数据行序号、原始列名、原始内容和检查理由**，但只是提示。不根据 IQR 自动删数。
- 批量导入清单增加 `sample_origin`、`condition_origin`，明确哪些分组来自文件夹名、哪些试样号来自文件名；发现猜测来源时加入提醒，降低伪重复风险。
- **质量审查不能覆盖真实实验现场**。测量装置的刚度、传感器校准、组织表面反光、实际负载路径、统计独立性、仪器数据结构、随机效应模型前提以及代理模型的真实预测能力仍需要实验人员验证。
- 视频追踪、轨迹人工修正算法未作本次大升级；高级统计保留现有四类数值模型，帮助说明改得更明确，但不声称已经完成全部统计假设诊断或自动模型选择。
- 表达限制：分离阶段的力—位移积分可能包括材料形变和耗散，不能直接命名为材料本征断裂能；名义应力依赖所填几何面积；图像亮度不能直接当真实接触面积或荧光物质浓度；模型推荐点不是下一次实验的保证结果。

**本项目交付的测试只代表覆盖过的计算路径表现，与实验室独立验收不是同一概念。** 软件在 Linux 虚拟显示器下检查过界面，尚不能保证所有实际 Windows 配置或仪器文件无需调整。数值测试细节另见 `docs/12_V6.0_数值测试与局限.md`。

## 七、这次版本的修改边界与后续建议

- 对视频追踪和轨迹人工修正：只在说明中保留现有实际用途和限制，核心算法保持不变；以后适合新增逐帧播放、点击目标标注、多个机器人部位的跟踪、反光和形变鲁棒性等，但本版**没有声称已经实现**。
- 多源同步若仅仅是已知常数的时间平移，Excel 足够；同步模块的价值在于采样时间网格、插值空缺和与真实事件对照，而不是把简单操作包装成新理论。
- 分析结果整理比原“写作辅助”更准确：它只是读取真实运行记录并生成可编辑的 Word/Markdown 方法与图注草稿，**不能自动推导机制或撰写完整论文**。
- 以后若取得经过许可的真实仪器数据，优先做与独立参考计算（例如实验室现有 MATLAB/Origin 工作流）的逐点和逐试样对照，这比继续增加未验证的新算法更重要。

---

本 README 的主要实验情境与术语组织参考了本项目附件中多轮中文对话的解释风格；与源代码不一致之处以核对过的源码和测试为准。文中的情境和数据例子是解释概念，并不表示某个真实课题的数据或已验证的科学发现。
'''
parts.append(EDIT_GUIDE)
README='\n'.join(parts)
(ROOT/'README.md').write_text(V7_PREFIX+README,encoding='utf-8')
(ROOT/'docs'/'11_V6.0_说明词典与源码位置.md').write_text('##  原有使用与维护说明\n\n完整说明请先打开项目根目录 README.md。\n\n'+EDIT_GUIDE,encoding='utf-8')
print('generated',len(README),'characters;',len(ORDER),'modules;',len(COLUMN_HELP),'result keys')
