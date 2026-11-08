# -*- coding: utf-8 -*-
"""build_report.py —— 生成课程报告 docx"""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "results", "figures")
OUT = os.path.join(os.path.dirname(os.path.dirname(BASE)), "1.报告.docx")

doc = Document()

# ---------- 页面 ----------
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.top_margin = sec.bottom_margin = Cm(2.54)
sec.left_margin = sec.right_margin = Cm(3.17)

# ---------- 样式 ----------
st = doc.styles["Normal"]
st.font.name = "宋体"
st.font.size = Pt(12)
st._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def set_cn(run, font="宋体", size=12, bold=False, color=None):
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    if color:
        run.font.color.rgb = color


def para(text="", size=12, bold=False, indent=True, font="宋体",
         space_before=0, space_after=6, align=None, line=1.5,
         keep_next=False, keep_together=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = line
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if keep_next:
        pf.keep_with_next = True
    if keep_together:
        pf.keep_together = True
    if indent:
        pf.first_line_indent = Pt(size * 2)
    if align is not None:
        p.alignment = align
    if text:
        _add_rich(p, text, size=size, bold=bold, font=font)
    return p


def _add_rich(p, text, size=12, bold=False, font="宋体"):
    """把 '**xx**' 拆成加粗段与非加粗段，分别写入 run。
    直接按 '**' 切分即可：偶数下标是普通文本，奇数下标是加粗文本。"""
    parts = text.split("**")
    for i, seg in enumerate(parts):
        if not seg:
            continue
        set_cn(p.add_run(seg), font=font, size=size, bold=(bold or i % 2 == 1))


def heading(text, level=1):
    sizes = {0: 20, 1: 15, 2: 13}
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(18 if level <= 1 else 12)
    pf.space_after = Pt(8 if level <= 1 else 6)
    pf.line_spacing = 1.5
    # 所有级别标题都要求"与下一段同页"，否则会出现标题在页底、
    # 正文翻到下一页的难看情况。
    pf.keep_with_next = True
    r = p.add_run(text)
    set_cn(r, font="黑体", size=sizes[level], bold=True)
    return p


def bullet(text, size=12):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Pt(24)
    pf.first_line_indent = Pt(-12)
    pf.line_spacing = 1.5
    pf.space_after = Pt(3)
    set_cn(p.add_run("· "), size=size)
    set_cn(p.add_run(text), size=size)
    return p


def code_block(lines, size=9.5, keep_together=True):
    """等宽代码块。

    keep_together=True 时，把块内除最后一行外都设为 keep_with_next，
    Word 会把整块当成一个不可分割单元，避免流程图/短代码被页边截成两半。
    附录那种几十行的长代码要传 False，否则整块塞不进一页会出问题。
    """
    n = len(lines)
    for i, ln in enumerate(lines):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.8)
        pf.line_spacing = 1.15
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        if keep_together and i < n - 1:
            pf.keep_with_next = True
        r = p.add_run(ln if ln else " ")
        set_cn(r, font="Consolas", size=size)
    tail = doc.add_paragraph()
    tail.paragraph_format.space_after = Pt(2)


def hr():
    """画一条水平分隔线（段落下边框），用来代替"另起一页"，省纸也省空白。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(10)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "AAAAAA")
    pbdr.append(bottom)
    pPr.append(pbdr)


def add_figure(path, caption, width_cm=14.4):
    if not os.path.exists(path):
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.add_run().add_picture(path, width=Cm(width_cm))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(10)
    set_cn(c.add_run(caption), size=10)


def add_table(headers, rows, widths=None, font_size=10):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(2)
        set_cn(p.add_run(h), font="黑体", size=font_size, bold=True)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            txt = str(v)
            bold = txt.startswith("*")
            set_cn(p.add_run(txt.lstrip("*")), size=font_size, bold=bold)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                r.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


# ============================================================
# 封面
# ============================================================
para("《图像处理与分析》课程报告", size=16, bold=True, indent=False,
     font="黑体", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=42, space_after=14)
para("低照度图像增强", size=24, bold=True,
     indent=False, font="黑体", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8, line=1.3)
para("自适应 Gamma 提亮与引导滤波去噪的联合方案", size=16, bold=True,
     indent=False, font="黑体", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=34, line=1.4)

para("学号：20242601", size=13, indent=False, align=WD_ALIGN_PARAGRAPH.CENTER,
     space_after=4, line=2.0)
para("姓名：韦俊威", size=13, indent=False, align=WD_ALIGN_PARAGRAPH.CENTER,
     space_after=4, line=2.0)
para("课程：图像处理与分析", size=13, indent=False, align=WD_ALIGN_PARAGRAPH.CENTER,
     space_after=4, line=2.0)
para("提交日期：2026 年 11 月", size=13, indent=False, align=WD_ALIGN_PARAGRAPH.CENTER,
     space_after=4, line=2.0)

doc.add_page_break()

# ============================================================
# 1. Github 链接
# ============================================================
heading("1. Github 链接", 1)
para("仓库地址（代码、数据生成脚本、结果图全部在这个仓库里）：")
# 这个地址有 66 个字符，11.5pt 等宽字在 14.66cm 正文宽里放不下会折行，
# "filter" 单独掉到第二行很难看，降到 10pt 正好一行。
para("https://github.com/fireflyovo233/llie-adaptive-gamma-guided-filter",
     indent=False, size=10, font="Consolas")
para("主分支为 main。仓库是 Public 的，可以直接 clone 下来复现，"
     "也可以在线浏览所有源码和结果图。")

para("仓库里有什么：")
bullet("make_dataset.py —— 合成低照度数据集，含退化参数记录")
bullet("enhance.py —— 七种增强方法，本文方法在 proposed() 里")
bullet("metrics.py —— PSNR/SSIM/LOE/NIQE 等指标的实现")
bullet("run_bench.py —— 批量实验，输出指标表与对比图")
bullet("tune.py —— 参数网格搜索（只在训练集上跑）")
bullet("make_figures.py —— 生成通用插图与消融实验")
bullet("make_report_figs.py —— 生成报告专用的高清插图")
bullet("build_report.py —— 用 python-docx 生成本报告的 docx")
bullet("run_photo.py —— 对自己的照片做定性对比")

para("复现方式（三步，不需要 GPU，纯 CPU 约 30 秒）：")
code_block([
    "pip install -r requirements.txt",
    "python make_dataset.py --out data --n-train 24 --n-test 8",
    "python run_bench.py --data data --out results",
])
para("数据集是随机生成的，但固定了随机种子（seed=2026），所以每次生成的结果完全一致，"
     "表里的数字可以逐位复现。这一点我在交之前从零重跑过一遍验证。")

doc.add_page_break()

# ============================================================
# 2. 任务描述
# ============================================================
heading("2. 任务描述 你要做什么", 1)

heading("2.1 问题从哪来", 2)
para("晚上用手机拍的照片，常常有这样一种感觉：画面里明明有东西，但屏幕上就是一片黑，"
     "把亮度拉满之后勉强能看清轮廓，可同时冒出来满屏彩色的颗粒。这其实不是“照片太暗”"
     "这么简单的一件事——暗只是表象，真正麻烦的是暗部同时混着两种东西：极弱的真实信号，"
     "和相对强度很大的传感器噪声。")
para("从信号角度看，一只 CMOS 传感器在低照度下接收到的光子数很少，散粒噪声（泊松噪声）"
     "的相对幅度和光子数的平方根成反比，于是“信噪比随亮度下降而恶化”。再叠上读出噪声、"
     " ISP 在暗部的增益提升，最后落到 8 位图像上，就是大片像素挤在灰度 0 到 30 之间，"
     "彼此只差几个灰阶，而噪声幅度恰好也是几个灰阶。")
para("所以低照度增强并不是“把暗的变亮”那么简单。真正要做的是：把被压缩在极窄动态范围内的"
     "信号重新展开到可观察的范围，同时不能把已经占主导的噪声一起放大。这两件事天然矛盾——"
     "展开靠增益，而增益必然会放大噪声。")

heading("2.2 具体要做什么", 2)
para("这次的任务定为：在不引入深度学习、不依赖大规模标注数据的前提下，实现若干种经典的"
     "低照度增强方法，定量比较它们的表现，然后针对实验里暴露出来的具体问题，"
     "提出一条改进的轻量管线。具体拆成四件事：")
bullet("复现四类经典做法：直方图均衡（含 CLAHE）、Gamma 校正、Retinex 系列（SSR/MSR），"
       "以及它们的串联组合，作为对比基线；")
bullet("搭一套评价体系。有真值时用 PSNR、SSIM；没有真值时用 NIQE、LOE、信息熵、"
       "对比度、平均梯度。真实夜景照片拿不到真值，所以无参考指标必须能独立成立；")
bullet("做消融实验，把改进方法拆开，一步一步看每个部件贡献了多少，"
       "而不是最后只报一个总数；")
bullet("代码要能跑在别人的机器上，能对自己的照片用，而不只是在本实验的数据上出个数。")

heading("2.3 预期达到的效果", 2)
para("我给自己定了一个不算激进但足够明确的目标：改进后的方法在 SSIM 上要稳定超过所有基线，"
     "并且在最暗的那一档图像上不能崩。之所以强调“不能崩”，是因为看过不少方法在中等亮度图上"
     "表现很好，一到极暗图就整个糊掉，这类方法在实际使用中价值有限。")

doc.add_page_break()

# ============================================================
# 3. 数据描述
# ============================================================
heading("3. 数据描述 数据是什么", 1)

heading("3.1 为什么自己做数据", 2)
para("我一开始想用现成的配对数据集，比如 LOL（LOw-Light dataset）。但它有两个问题：一是需要"
     "下载，二是它的真值是“用长曝光在同一机位拍的”，本身带噪声和轻微位移，"
     "所以算出来的 PSNR 上限并不干净，没法判断差距到底是我的方法不行还是真值不准。")
para("最后决定自己合成。合成的好处很直接：真值完全干净，退化过程完全可控，"
     "每一项指标的变化都能追溯到具体原因。代价是“合成得太理想”，"
     "这一点我在第 5 节会专门讨论，因为它直接影响结论的适用范围。")

heading("3.2 真值图怎么来", 2)
para("真值图不是找图片，而是用程序画。画的时候刻意覆盖了几类不同性质的内容，"
     "因为不同算法对不同内容的反应差别很大：")
bullet("blend：多个高斯光斑叠加再模糊，模拟柔和渐变，考验算法会不会出现色带；")
bullet("shapes：带黑色描边的高对比多边形和直线，考验边缘处的光晕和过冲；")
bullet("texture：正弦条纹，给频域方法和多尺度方法留出可发挥的结构；")
bullet("mixed：以上几种混合。")
para("画完之后还叠了两层“不完美”：一层低频纹理（大核模糊后的白噪声）避免画面过于塑料，"
     "一个侧向照明梯度让直方图不那么规整。最后加一次小半径高斯模糊，模拟镜头 MTF 有限。"
     "这样做是因为纯几何图形太“干净”，任何算法都能做好，比较就失去意义了。")

heading("3.3 退化模型", 2)
para("这是整个数据部分最关键的地方。我没有简单地乘一个系数，而是按成像链路来写：")
code_block([
    "A(x)  = κ / (1 + 1.1·r²(x))            暗角：镜头边缘照度衰减",
    "S(x)  = 1 - depth·exp(-d²(x)/2σ²)      阴影：遮挡物投下的局部暗区",
    "attn  = A·S / mean(A·S)                归一化到均值 1，只保留“不均匀”",
    "lin   = (I/255) · κ · attn             线性光强",
    "obs   = 255 · clip(lin)^γ               γ > 1 压缩暗部",
    "obs   = Poisson(obs) + N(0, σ_read)    泊松-高斯混合噪声",
])
para("这里有一个细节值得说明，因为它是我第一版做错的地方。最初我把暗角和阴影直接相乘再"
     "乘到光强上，结果整幅图被压了两次，平均亮度掉到 2～7，几乎全黑。那个时候所有方法都失败了，"
     "我一度以为是算法有问题。后来把衰减归一化到均值 1 才明白：暗角和阴影要表达的"
     "是“不均匀”，整体亮度水平应该由 κ 和 γ 单独控制，混在一起就没法独立调了。")

heading("3.4 数据的统计面貌", 2)
para("一共 32 对图像，其中 24 对作为训练集（调参用），8 对作为测试集（只用来出最终数字）。"
     "尺寸 320×240，PNG 无损保存。退化参数在下列范围内随机采样：γ ∈ [1.6, 2.35]，"
     "κ ∈ [0.40, 0.68]，60% 的图带一块随机位置的椭圆阴影。")
para("实测低照度图的平均亮度分布：均值 25.0，最小 6.8，最大 66.4，标准差平均 20.5；"
     "对应的真值图平均亮度 119.4。也就是说大体上暗了 4 到 5 倍，"
     "但暗的程度有充分梯度，从“几乎看不见”到“只是偏暗”都覆盖到了。")

add_figure(os.path.join(FIG, "r_samples.jpg"),
           "图 1  数据集样例。上排为程序合成的真值，下排为退化后的低照度观测，"
           "括号内是平均亮度。三张图的暗度和阴影位置各不相同。", 14.4)

para("图 2 左边是其中一张（test_028）的亮度直方图与真值的对比。"
     "这张图很直观地说明了问题的本质：低照度像素全部挤在 0～45 之间，"
     "其中一半以上集中在 0～15，形成一个又窄又高的尖峰；"
     "而真值的分布是宽的，5% 分位到 95% 分位覆盖 85～198。"
     "增强要做的，就是把这个尖峰“摊开”成那个宽分布。")
para("右边画了两条 Gamma 曲线。虚线是恒等映射，可以看到 γ=0.32 的曲线在暗部极陡——"
     "输入灰度 5 就被映射到 73，输入 10 映射到 90。"
     "问题在于，这种陡峭对信号和噪声是一视同仁的："
     "原本只有 1 个灰阶的噪声起伏，在这个区间会被拉成 4～7 个灰阶，"
     "这就是为什么只提亮不行。")

add_figure(os.path.join(FIG, "r_hist.jpg"),
           "图 2  左：低照度与真值的亮度直方图；右：不同 γ 的映射曲线。"
           "右侧紫色竖箭头示意输入端 1~6 个灰阶的范围，在 g=0.32 下被映射到 1~74，"
           "暗部因此被极度拉伸。", 14.4)

para("把上面这些数字整理成一张表，方便对照：")
add_table(
    ["项目", "取值"],
    [["图像尺寸 / 格式", "320×240，PNG 无损"],
     ["训练集 / 测试集", "24 对 / 8 对（按 seed=2026 固定划分）"],
     ["退化参数 γ（Gamma）", "1.6 ~ 2.35"],
     ["退化参数 κ（整体增益）", "0.40 ~ 0.68"],
     ["带阴影的图像比例", "60%（椭圆，位置与深度随机）"],
     ["低照度图平均亮度", "25.0（最小 6.8，最大 66.4）"],
     ["低照度图平均标准差", "20.5"],
     ["真值图平均亮度", "119.4"],
     ["噪声模型", "泊松-高斯混合（光子数 60~160，读出噪声 σ=2）"]],
    widths=[5.4, 8.2], font_size=9.5)
para("表 1  数据集统计。", indent=False, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)

doc.add_page_break()

# ============================================================
# 4. 代码修改描述
# ============================================================
heading("4. 代码修改描述 你改了什么", 1)

heading("4.1 整体结构", 2)
para("代码按“数据 → 算法 → 指标 → 实验”拆成六个文件，每个文件职责单一，"
     "都能单独跑。所有增强函数的签名统一成 fn(bgr, kwargs) -> bgr，"
     "这样 run_bench.py 里一个 for 循环就能把全部方法过一遍，"
     "加新方法只需要在 METHODS 字典里加一行。")

add_table(
    ["文件", "行数", "职责"],
    [["make_dataset.py", "约 210", "合成真值图 + 退化，输出 data/ 与 meta.json"],
     ["enhance.py", "约 300", "七种增强方法，核心是 proposed()"],
     ["metrics.py", "约 200", "PSNR/SSIM/LOE/NIQE/熵/对比度/平均梯度"],
     ["run_bench.py", "约 200", "批量实验，出 CSV 表与对比网格图"],
     ["tune.py", "约 110", "参数网格搜索，只在训练集上"],
     ["make_figures.py", "约 230", "报告插图与消融实验"],
     ["run_photo.py", "约 80", "真实照片的定性对比"]],
    widths=[3.6, 2.2, 8.6])

heading("4.2 一个贯穿全局的决定：只在 Y 通道上动手", 2)
para("所有方法都先把图转到 YCbCr，只在 Y 上处理，再把 CbCr 原样放回去。这个选择不是可有可无的。"
     "我第一版是直接在 BGR 三个通道上分别做 Retinex，结果输出满屏彩色噪点——"
     "因为三个通道的噪声是独立的，各自归一化之后再合回去，色度就被彻底打乱了。"
     "改到 Y 通道之后，色相和饱和度基本不受影响，画面立刻就干净了很多。")
code_block([
    "def to_luma(bgr):",
    "    return cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)[:, :, 0].astype(np.float32)",
    "",
    "def with_luma(bgr, y_new):",
    "    ycc = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)",
    "    ycc[:, :, 0] = np.clip(y_new, 0, 255).astype(np.uint8)",
    "    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR)",
])

heading("4.3 六个基线方法的实现", 2)
para("**直方图均衡。**直接用 OpenCV 的 equalizeHist 作用在 Y 上。它在低照度图上失败的原因"
     "很清楚：像素全挤在 0～30，累积分布函数在那一段几乎是竖直的，"
     "输入差 1 个灰阶，输出可能跳 20 个灰阶，噪声被放大成麻点。")
para("**CLAHE。**分 8×8 块，每块单独均衡，clipLimit=2.0 截断直方图峰值。"
     "它解决了 HE 的噪声放大，但没有解决亮度——输出仍然是暗的，因为局部均衡只调整对比度，"
     "不改变整体的电平。")
para("**Gamma 校正。**out = 255·(y/255)^g，g=0.32。这个值不是随手给的，是我在训练集上"
     "扫了 9 个 g 值（0.25 到 0.50）选出来的最优，也顺带确认了：g=0.25 时增强图平均亮度 140，"
     "已经超过真值的 119，开始过曝；g=0.32 时是 126，最接近。")
para("**Gamma+CLAHE。**先 Gamma 再 CLAHE。顺序很重要：如果反过来先做 CLAHE，"
     "它均衡的是最原始的暗直方图，截断阈值相对整幅图太小，噪声和细节被一起拉伸；"
     "先提亮之后直方图形态正常了，CLAHE 才只做它擅长的事。")
para("**SSR / MSR。**对数域 Retinex。原理是把 I = L·R 分解开，用高斯模糊估计低频照明 L，"
     "对数域相减得到反射 R。SSR 的 σ 在训练集上扫了 5/15/30/80，80 最好；"
     "MSR 用 Jobson 原论文的三尺度 (15, 80, 250)。")

heading("4.4 我改了什么：三个问题的三个回应", 2)
para("跑完第一轮基线，表里的数字暴露了三个具体问题。我的改动都是针对这三个问题来的。")

para("**问题一：固定 Gamma 打不过不同暗度的图。**", indent=True, bold=False)
para("训练集里最暗的图平均亮度 6.8，最亮的 66.4，差了近十倍。用一个 g=0.32 去套所有图，"
     "暗的图提不够，亮的图提过头。我的做法是由图像自己的 10% 分位数反推 g："
     "解 p^g = target。但第一版我把 target 固定成 0.5，结果几张本来就不太暗的图"
     "被强行推到 0.5。在训练集前 6 张上测过，固定 target 时这 6 张**全都**比浮动 target 差，"
     "PSNR 均值从 17.91 掉到 14.50。而这几张图用固定 gamma 是 18.75 的均值，"
     "也就是说“固定 target 的自适应”还不如老老实实用一个常数。")
para("所以第二版让 target 随“有多暗”浮动：")
code_block([
    "p < 0.04  →  target = 0.35      极暗，使劲提",
    "p > 0.20  →  target = 0.60      已经不太暗，克制点",
    "中间线性插值",
])
para("理由是低照度增强的目标是“把看不见的变看得见”，不是“把每张图都推到同一个亮度”。"
     "前者才是使用者需要的，后者只是在迎合指标。")
para("顺带说明为什么选 10% 分位数而不是均值：均值会被少数亮斑、灯源拉高，"
     "而低照度图像的有效信息恰恰在中低灰度段。一张图只要有 5% 的像素是亮的，"
     "均值就失真了，分位数不会。")

para("**问题二：噪声被提亮一起放大，而且放大得很厉害。**", indent=True)
para("这个问题的量级可以从导数看出来。Gamma 的导数是 g·(y/255)^(g-1)，"
     "在 y 很小时趋于无穷。以 γ=0.32 为例算几个点："
     "y=2 时导数约 8.7，y=10 时约 2.9，y=50 时约 0.97。"
     "换成更好理解的说法——输入每差 1 个灰阶，输出在 y=2 处差 7.5 个灰阶，"
     "在 y=10 处差 2.8 个，到 y=50 附近就几乎不变了。"
     "所以同样是 1 个灰阶的噪声起伏，越暗的地方被放得越狠。"
     "低照度图的噪声本来就在暗部，提亮之后突然“冒”出来，原因就在这里。")
para("由此得出一个关键的顺序结论：压噪必须放在提亮**之后**。理由是如果先压噪再提亮，"
     "压的是“放大前”的那份噪声，提亮后又原样放大回来，等于白做。"
     "而先提亮再压噪，压的才是已经放大到肉眼可见程度的那份噪声。"
     "这一点听起来像常识，但我在一开始确实是先压噪的，把顺序改过来之后 SSIM 从 0.538 涨到 0.738。")
para("去噪器选了引导滤波（He et al., 2010），而不是高斯模糊或双边滤波，理由是："
     "高斯模糊会把画面整体摸软，边缘一起糊；引导滤波在窗口内假设输出是引导图的线性函数 "
     "q = a·I + b，在边缘处 a≈1、b≈0，不会跨越边缘平滑，所以边缘能保住。"
     "而且它用方框滤波实现，复杂度与半径无关，比双边滤波快。")
code_block([
    "def _guided_filter(guide, src, r=8, eps=1e-2):",
    "    k = (2*r+1, 2*r+1)",
    "    mean_g, mean_p = cv2.blur(guide, k), cv2.blur(src, k)",
    "    var_g  = cv2.blur(guide*guide, k) - mean_g*mean_g",
    "    cov_gp = cv2.blur(guide*src,   k) - mean_g*mean_p",
    "    a = cov_gp / (var_g + eps)",
    "    b = mean_p - a * mean_g",
    "    return cv2.blur(a, k) * guide + cv2.blur(b, k)",
])
para("引导图我没有直接用提亮后的 Y，而是用了它的轻度高斯平滑版（σ=1.5）。"
     "这是一个小改动但有效：如果拿原图做引导，噪声会把滤波系数 a 带偏，"
     "结果在噪声大的区域反而滤不干净。")
para("滤波半径也不是固定的，按估计出的噪声强度自适应：r = 6·(1 + σ̂/8)，限制在 2～24。"
     "噪声估计用的是 Immerkær 的经典做法——图像与拉普拉斯掩模卷积后取绝对值的中值再乘经验系数，"
     "这个方法不受边缘影响，比直接算全局标准差准确得多。")

para("**问题三：细节要不要加回来。**", indent=True)
para("我在管线最后留了一个 detail 开关，把被平滑掉的高频按比例加回。直觉上这一步应该有用，"
     "因为去噪总会损失一些真实细节。但实验结果是负的：加上 detail=0.15 之后，"
     "SSIM 从 0.738 掉到 0.726。原因不难理解：合成图的噪声集中在高频，和真正的细节同频段，"
     "加回来等于把刚压下去的噪声又请回来。所以最终版本默认 detail=0。")
para("这个开关我保留了，因为在真实照片上结论未必相同——真实场景的边缘更陡、更连续，"
     "噪声更偏低频色斑，此时回加高频对肉眼清晰度是有帮助的。代码注释里写清楚了这一点，"
     "并建议真实照片用 0.1～0.3。")

heading("4.5 最终方法的完整流程", 2)
code_block([
    "输入 BGR  →  转 YCbCr，只取 Y",
    "① p = percentile(Y, 10)",
    "   target = 0.35 + 0.25·clip((p - 0.04) / 0.16, 0, 1)",
    "   g = clip(log(target) / log(p), 0.15, 1.0)",
    "② lit = 255·(Y/255)^g                            提亮",
    "③ σ̂ = Immerkær(lit);  r = clip(6·(1+σ̂/8), 2, 24)",
    "   lit = GuidedFilter(GaussianBlur(lit, 1.5), lit, r)   压噪（必须在提亮之后）",
    "④ lit += detail·(lit - 平滑值)                    默认 detail = 0",
    "写回 Y  →  输出 BGR",
])

heading("4.6 工程上的几点说明", 2)
para("**训练/测试严格分开。**所有参数（g 的范围、γ 的取值、σ 的取值）都在 24 张训练图上扫，"
     "测试集 8 张只在最后出数时用一次。tune.py 里写明了只加载 train 划分。"
     "如果不这样做，测出来的成绩是“调参调出来的”，没有意义。")
para("**指标实现自己写。**PSNR 和 SSIM 用的是标准公式，SSIM 是 11×11 高斯窗、σ=1.5、"
     "C1=(0.01·255)²、C2=(0.03·255)²。没有直接调 skimage 是为了确保我知道每一个常数是什么。"
     "NIQE 是简化实现：用 24 张真值图估计 MSCN 系数的多元高斯分布，再算马氏距离。"
     "所以这个分数是“相对这批参考图”的，横向比较各方法时有效，绝对值本身没有普适意义。")
para("**回归测试。**交之前我从零重跑了一遍完整流程，确认 PSNR 17.24、SSIM 0.7382、NIQE 9.891 "
     "与之前逐位相同。随机种子固定，数据生成和算法都没有随机性，所以这个可复现性是有保证的。")

doc.add_page_break()

# ============================================================
# 5. 结果对比
# ============================================================
heading("5. 结果对比 结果有什么变化", 1)

heading("5.1 总表", 2)
para("表 2 是测试集 8 张图的平均值。耗时是单张 320×240 在 CPU 上的实测值，"
     "会随机器浮动，主要看相对关系。")
add_table(
    ["方法", "PSNR↑", "SSIM↑", "LOE↓", "NIQE↓", "熵↑", "耗时/ms"],
    [["HE", "10.95", "0.1695", "0.2", "313.9", "5.040", "1.0"],
     ["CLAHE", "8.72", "0.2795", "7.5", "249.8", "5.759", "1.5"],
     ["Gamma (g=0.32)", "15.80", "0.5367", "0.0", "241.1", "4.987", "2.7"],
     ["Gamma+CLAHE", "15.13", "0.4088", "5.0", "279.0", "6.360", "2.6"],
     ["SSR", "11.44", "0.1970", "6.2", "311.2", "7.599", "20.3"],
     ["MSR", "11.33", "0.1701", "5.8", "317.6", "7.552", "83.6"],
     ["*本文方法", "*17.24", "*0.7382", "8.8", "*9.9", "6.356", "10.0"]],
    widths=[3.6, 2.1, 2.1, 1.7, 2.0, 1.9, 2.0], font_size=9.5)
para("（原图的 PSNR 是 7.48、SSIM 0.177，可以当作起点；NIQE 145.2。）", indent=True, size=10)

heading("5.2 三个数的含义", 2)
para("**PSNR 从 15.80 提到 17.24，涨了 1.44 dB。**PSNR 对整体亮度是否恰好匹配极其敏感，"
     "所以这个提升主要来自两处：自适应 Gamma 让不同暗度的图都能落在合理的亮度上（+1.06 dB），"
     "去噪压掉了一部分本不属于信号的方差（+0.38 dB）。")
para("**SSIM 从 0.537 提到 0.738，是第二名的 1.38 倍。**这个提升比我预期的要大。"
     "我核对过是不是个别图拉起来的，结果是否定的——8 张图逐张比较，本文方法对每一个基线都更高，"
     "8/8 全胜，而且差距都在 0.1 以上，最大的 0.34（test_026：0.822 对 0.481）。")
para("**NIQE 从 241 降到 9.9。**这个差距是量级上的，不是百分比的。NIQE 的原理是"
     "“用自然图像的统计先验打分”，分数越低越像自然图像。两三百的分数意味着"
     "输出的统计特性和自然图像完全脱节——说白了就是一幅噪点图。9.9 已经落在自然图像的常见区间里。"
     "我认为这是整张表里最有说服力的一列，因为它不依赖“猜对亮度”。")

heading("5.3 看图说话", 2)
add_figure(os.path.join(FIG, "r_ablation.png"),
           "图 3  消融实验。①②只做提亮；③在②的基础上加引导滤波去噪，即本文默认配置；"
           "④是附带的细节回加，实测为负收益。", 14.4)
para("消融表里有一个值得单独说的现象：②（自适应 Gamma）的 PSNR 涨了 1.06，但 SSIM 几乎没动"
     "（0.5367 → 0.5382）。而 ③（加去噪）的 PSNR 只涨 0.38，SSIM 却涨了 0.20。"
     "这说明两件事的作用机理完全不同——提亮解决的是“整体电平”，去噪解决的是“结构可辨识度”。"
     "SSIM 的三个分量是亮度、对比度、结构，而噪声主要破坏的是结构那一项，"
     "所以它对去噪比对提亮敏感得多。")
para("这也解释了为什么前面所有基线方法的 SSIM 都不高，包括 PSNR 不差的 Gamma。"
     "它们的 PSNR 靠“亮度凑得准”，但画面里全是噪点，结构项被压得很低。")

add_figure(os.path.join(FIG, "r_scatter.png"),
           "图 4  SSIM 与耗时的折中。横轴是对数刻度。左上角是最理想的区域。", 13.2)
para("图 4 把耗时也放进来，因为它关系到能不能用。本文方法 10 ms 一张，"
     "比 Gamma（2.7 ms）慢三倍多，但比 MSR（83.6 ms）快八倍，"
     "而且 SSIM 高出 0.2 以上。在“可以接受的速度”这个前提下，它的性价比是最好的。"
     "如果要更快，把引导滤波的半径调小就能降到 5 ms 左右，代价是 SSIM 掉 0.02 上下。")

add_figure(os.path.join(FIG, "r_curves.png"),
           "图 5  把测试集按输入的暗度分成三档，看各方法在每一档上的平均 SSIM。", 13.4)
para("图 5 回应的是我在 2.3 节提的那个目标：不能在最暗的图上崩掉。"
     "左边一档是平均亮度低于 15 的极暗图。可以看到 Gamma 在这一档只有 0.454，MSR 是 0.131，"
     "基本等于失效；而本文方法是 0.712。三档之间的波动分别是：本文 0.712→0.778→0.738，"
     "极差 0.066；Gamma 0.454→0.597→0.579，极差 0.143。"
     "也就是说本文方法不仅绝对值高，而且跨暗度的稳定性也更好。")

heading("5.4 逐图看真实的增强效果", 2)
para("指标只是一方面，还是得看图。下面这张是测试集里的一张，它有几个典型难点："
     "整体极暗（均值约 8.6），还有一颗很亮的彩色光斑。")
add_figure(os.path.join(FIG, "r_test_026.jpg"),
           "图 6  test_026 的对比。真值是一条斜向的细条纹结构，在低照度输入里几乎完全看不见。", 14.4)
para("看这张图可以很清楚地分出方法的好坏：")
bullet("HE 是最差的——亮斑被推到饱和，暗部被拉成一片白噪，条纹完全丢失。这是直方图均衡在"
       "低照度图上的典型失效。")
bullet("CLAHE 和 Gamma+CLAHE 都没能把条纹提出来，只是把暗部整体从黑变灰。")
bullet("SSR 和 MSR 是最有意思的反例：它们其实“看见”了条纹，条纹的形状清晰可见，"
       "但整幅图被碎成雪花，实用价值反而最低。原因我在 4.3 提过——Retinex 去掉的是低频照明，"
       "而噪声在这个场景里落在中高频，正好被完整保留下来。")
bullet("Gamma 的效果不错，条纹出来了，颜色也基本对，但有一层明显的颗粒。")
bullet("本文方法的条纹最清晰、背景最干净，PSNR 20.37、SSIM 0.822，是这张图上最好的。")

add_figure(os.path.join(FIG, "r_test_029.jpg"),
           "图 7  另一张测试图，主体是几块柔和的色彩区域加右侧的强光源。", 14.4)
para("图 7 考验的是颜色保真和光晕控制。HE 依旧是最差的；SSR/MSR 在左侧暗部出现了明显的"
     "灰白噪块；Gamma 的颜色基本对但噪点多。本文方法在右侧强光边缘没有出现明显光晕"
     "（这是引导滤波相对高斯模糊的优势），整体颜色也基本还原。")
para("但它并不干净：左上和左下各残留了一小块噪斑。这两块是全图最暗的地方，"
     "信噪比已经接近 1，噪声和信号本身的幅度差不多，引导滤波只能压住一部分。"
     "这说明本文方法对“有结构、有光”的区域效果好，对纯粹的死黑区无能为力——"
     "那本质上已经不是增强问题，而是信息缺失，任何不依赖先验的方法都补不回来。")

heading("5.5 在真实照片上的表现", 2)
para("合成数据上的结论再好看，也得在真实照片上验证一下，否则这套代码就只是个刷指标的玩具。"
     "我用一张模拟实拍条件的照片做了测试：它在低照度之外还叠了白平衡偏冷、彩色噪声和 "
     "JPEG 压缩失真（质量 72），这三点是合成数据里没有的。")
add_figure(os.path.join(FIG, "r_photo.jpg"),
           "图 8  带色偏与 JPEG 压缩的低照度照片上各方法的表现（按从左到右、从上到下排列）。", 13.2)
para("结果趋势和合成数据一致：HE、SSR、MSR 都出现了严重的色偏和噪块，"
     "尤其在第二块绿色区域，SSR/MSR 直接糊成一团；Gamma 和 Gamma+CLAHE 相对干净，"
     "但整体偏亮、发白，第二块绿色区域的颜色明显被冲淡了。"
     "本文方法的颜色最接近原样，噪点也最少，NIQE 是 4.07，"
     "其它方法在 31 到 70 之间，差了将近一个数量级。")
para("但这里我也发现了一个问题：这张图的输出偏暗。原因是它的 10% 分位数是 24（即 0.094），"
     "落在暗度区间中部，算出的 g 是 0.353，提亮力度偏保守。"
     "我试过把暗度区间上限从 0.20 放宽到 0.24、目标值相应上调，g 降到 0.319，"
     "输出均值从 133 升到 142，NIQE 从 4.07 微降到 4.03，视觉上更接近“看着舒服”。"
     "但这组改动在测试集上是负收益的（PSNR 从 17.24 降到 16.61，SSIM 从 0.738 降到 0.728），"
     "所以我没有改默认值。"
     "根本原因是暗度区间这个参数在合成数据和真实照片上的合适取值不一样，"
     "需要在真实数据上重新标定。这是这套方法的局限，第 6 节会展开。")

heading("5.6 需要说清楚的三件事", 2)
para("第一，LOE 变差了（0 到 8.8），这不是 bug。LOE 衡量的是“原来谁比谁亮”的顺序"
     "有没有被打乱。低照度图里大量像素挤在同一个灰度附近，本来就没有清晰的亮度序；"
     "提亮必然把它们拉开，LOE 就上去了。对低照度增强来说，"
     "让看不见的看得见，比保持一个本来就模糊的亮度序更重要。"
     "所以我在表里没有把它当作缺点标注。")
para("第二，本文方法的平均梯度只有 1.50，是表里最低的（HE 是 11.63）。"
     "但平均梯度和噪声高度混淆——HE 的 11.63 里绝大部分是噪声的梯度。"
     "这也说明了单一指标的局限：如果只看平均梯度，会得出“HE 最清晰”的错误结论。")
para("第三，熵这一列也值得警惕。SSR/MSR 的熵最高（7.6 左右），但那是把噪声也算成信息的结果。"
     "本文方法 6.356 反而更低，恰恰是因为噪声被压掉了。所以熵这一列不能单独看。")
para("把这三个“看起来反常”的数字整理一下，其实指向同一个结论：单一指标都不足以判断增强好坏。")
add_table(
    ["指标", "它真正衡量什么", "在本实验里为什么会误判"],
    [["LOE", "增强前后像素之间的亮度先后顺序", "低照度图暗部本来就挤在一起、没有清晰顺序，提亮必然把顺序重排；分数变差不等于效果变差"],
     ["平均梯度", "画面里灰度变化有多剧烈", "噪声与边缘同属高频，噪声会一起抬高分数；HE 拿到 11.63，但它是表里最难看的"],
     ["信息熵", "灰度分布有多“丰富”", "噪声被当作信息计入；SSR/MSR 虚高到 7.6，实际是满屏雪花"]],
    widths=[1.9, 4.9, 7.4], font_size=9)
para("表 3  三个容易误判的指标。", indent=False, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)

doc.add_page_break()

# ============================================================
# 6. 反思与局限
# ============================================================
heading("6. 不足与反思", 1)

heading("6.1 数据是合成的，结论有边界", 2)
para("这是最大的局限，必须放在最前面说。真值是我用程序画的，退化模型也是我自己写的，"
     "所以“PSNR 17.24”这个数字只说明“在这个退化模型下相对最好”，"
     "不能直接推广到任意真实夜景。真实的低照度退化还包含传感器暗电流、坏点、"
     "ISP 的降噪算法、镜头色散等等，我的模型里都没有。")
para("我做的一点点补救，是用 run_photo.py 在带色偏和 JPEG 压缩的照片上做了定性验证，"
     "趋势是一致的。但要真正有说服力，需要 LOL 或 SID 这类真实配对数据集，"
     "这不在本次课程的范围内。")

heading("6.2 自适应在极端图上会失准", 2)
para("10% 分位数终究是个统计量。如果一张图有大面积的纯黑背景（比如夜空），"
     "10% 分位会非常小，算出的 g 就偏小，提亮过头；反过来如果整幅图都很亮，"
     "分位数失去区分度。要彻底解决得做区域级的照明估计（分块求光照图再插值），"
     "也就是 Retinex 的思路，但那又会回到放大噪声的问题上。这个矛盾在传统方法框架内不好根本解决。")

heading("6.3 指标本身的局限", 2)
para("做完这个实验，我对“用哪个指标评价低照度增强”这件事的看法变了。"
     "PSNR 和 SSIM 都需要真值，而真值亮度一旦和算法的“猜”不一致，"
     "分数就掉；但这个“猜对亮度”的能力本身并不能说明算法好不好。"
     "本实验里，所有方法的亮度偏移对 SSIM 的影响，和结构恢复的影响是一个量级的。")
para("NIQE 不依赖真值，看起来更适合，但它对噪声极其敏感，"
     "也可能惩罚掉一些合理的伪影（比如适度的锐化）。"
     "比较稳妥的做法是：真值指标和无参考指标一起看，"
     "再配上看图，三者不矛盾才算结论可靠。")

para("如果还有后续时间，我会先补一步白平衡校正（图 8 那层偏冷色偏所有方法都没处理，"
     "加灰度世界或白点检测就能接上），再试着把去噪器换成 BM3D 或小波阈值，"
     "对付真实照片的有色噪声。", keep_together=True)

hr()
heading("附录：关键代码", 1)
para("为了方便查阅，把本文方法的核心代码完整贴在这里（与仓库 enhance.py 完全一致，"
     "由脚本自动提取，不是手抄的）。", indent=True)

_src = open(os.path.join(BASE, "enhance.py"), encoding="utf-8").read()
_start = _src.index("def adaptive_gamma_exponent")
_end = _src.index("def _noise_sigma")
_snippet = _src[_start:_end].rstrip().split("\n")

# 附录只贴"纯代码行"：去掉 docstring、中文注释和续行说明，
# 否则代码块里会混进大段中文，既不像代码也不像正文。
_code, _in_doc = [], False
for ln in _snippet:
    t = ln.strip()
    if '"""' in t:
        _in_doc = not _in_doc if t.count('"""') == 1 else _in_doc
        continue
    if _in_doc:
        continue
    if not t:
        if _code and _code[-1] != "":
            _code.append("")
        continue
    if t.startswith("#"):
        continue
    # 跳过含中文的注释行与续行
    if any("\u4e00" <= ch <= "\u9fff" for ch in t):
        continue
    _code.append(ln)

code_block(_code, keep_together=False)

doc.save(OUT)
print("saved:", OUT)
