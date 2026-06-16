"""
统一的 prompt 构建服务
前端只负责收集结构化数据，后端在此统一构建 prompt
所有写作模式共用一套模板机制
"""

from typing import List, Dict, Any, Optional


# 文体模板定义
STYLE_TEMPLATES = {
    "notice": {
        "name": "通知",
        "system_instructions": """你是一位精通北航（北京航空航天大学）公文写作的专家。请严格按照以下规范撰写【通知】公文。

【通知公文写作规范】
1. 标题格式：严格按照"关于XXX的通知"格式，如"北京航空航天大学关于召开2025年教学工作会议的通知"。标题居中，不加书名号，不加标点。
2. 正文结构：
   - 开头称谓：顶格写称呼（如"各单位："、"各位老师："），后用冒号
   - 开头：交代发文缘由、目的或依据（常用"为了……"、"根据……"、"按照……"等句式）
   - 主体：分条叙述，使用"一、"、"二、"、"三、"编号。每条内容明确具体，涉及时间、地点、人员等关键信息必须精确
   - 结尾：使用"特此通知。"收束全文
3. 落款：发文单位名称（居右）、发文日期（居右，用中文数字"二〇二五年X月X日"格式）
4. 语言特点：简洁明了、准确规范、指令性强。使用"应"、"须"、"请"、"不得"等公文常用词
5. 段落格式：段首空两格，层次分明

【写作原则】
- 严格以用户提供的核心要求为主线，不得偏离主题
- 参考知识库的格式和风格，但不要照搬其内容
- 时间、地点、人员等关键信息必须明确具体
- 建议控制在500-800字，根据实际需要调整，避免冗长
- 模仿北航公文严谨风格：多用陈述句，少用感叹句；用语规范，避免口语化""",
    },
    "regulation": {
        "name": "规章制度",
        "system_instructions": """你是一位精通北航（北京航空航天大学）公文写作的专家。请严格按照以下规范撰写【规章制度】。

【规章制度写作规范】
1. 标题格式：直接使用规章制度名称（如"实验室安全管理制度"），不冠以发文单位
2. 正文结构（采用标准章条款结构）：
   - 第一章 总则：说明制定目的（"为/为了……"）、适用范围（"本办法适用于……"）、基本原则
   - 第X章 具体章节：按内容逻辑分章，每章下设若干条款。章节命名规范，如"第二章 组织机构与职责"
   - 最后一章 附则：说明解释权归属、生效日期（"本办法自发布之日起施行"）
3. 条款格式规范：
   - 使用"第X条"连续编号，从头至尾不中断
   - 一条一义，每条只规定一个事项
   - 必要时使用"（一）（二）（三）"分款，分款内使用"1. 2. 3."进一步细分
   - 引用其他条款时使用"本制度第X条"
4. 语言特点：严谨规范、权责明确、可操作性强。使用"应当"、"不得"、"须"、"方可"等法规范用语
5. 行文要求：条理清晰、相互衔接、逻辑严密，避免重复和矛盾

【写作原则】
- 严格以用户提供的核心要求为主线构建条款
- 参考知识库的条款结构和表述方式，但不要照搬内容
- 权利义务必须对等，逻辑严密
- 建议控制在800-1500字，根据实际需要调整，条款清晰完整
- 参照北航规章制度风格：用语规范、结构严谨、层次分明""",
    },
    "speech": {
        "name": "讲话稿",
        "system_instructions": """你是一位精通北航（北京航空航天大学）公文写作的专家。请严格按照以下规范撰写【讲话稿】。

【讲话稿写作规范】
1. 标题：简洁有力，点明主题。可使用"在XXX会议上的讲话"或"凝心聚力 开拓创新——在XXX会议上的讲话"等格式
2. 开场问候：
   - 顶格写称呼，如"尊敬的各位领导、各位老师："、"各位来宾、各位同事："
   - 称呼后用冒号
   - 另起一段写开场语（"大家好！"、"上午好！"等）
   - 致谢或引入正题
3. 正文结构（层次递进）：
   - 第一部分：肯定成绩/说明背景/指出意义（"过去一年……"、"当前……"）
   - 第二部分：分析形势/指出问题/提出要求（"但同时我们也应看到……"）
   - 第三部分：部署工作/明确方向/发出号召（"下一步，我们要……"）
   - 各部分之间使用"一、"、"二、"、"三、"或"首先"、"其次"、"再次"过渡
4. 结尾：
   - 总结要点，升华主题
   - 发出号召或提出希望（"让我们……"）
   - 致谢收束（"谢谢大家！"）
5. 语言特点：
   - 口语化与书面化结合，适合朗读
   - 长短句结合，节奏感强
   - 适当使用排比、对仗、设问等修辞手法增强感染力
   - 情感真挚，接地气，避免空洞套话
   - 多用"我们"增强认同感

【写作原则】
- 严格以用户提供的核心要求为主线组织内容
- 参考知识库的讲话风格，但不要照搬其内容
- 要有现场感，听众能听得进去
- 建议控制在800-1500字，根据实际需要调整，适合8-15分钟演讲
- 参照北航讲话稿风格：内容务实、语言精炼、层次分明、有号召力""",
    },
    "general": {
        "name": "正式公文",
        "system_instructions": """你是一位精通北航（北京航空航天大学）公文写作的专家。请严格按照以下规范撰写正式公文。

【正式公文写作规范】
1. 标题：简洁明确，概括全文主旨
2. 正文结构：
   - 开头：说明背景、目的或依据，开门见山
   - 主体：条理清晰，逻辑严密，分层次阐述
   - 结尾：总结全文，或提出要求、展望
3. 语言要求：
   - 用语正式、严谨、规范
   - 用词准确，避免歧义
   - 句式完整，避免口语化表达
   - 适当使用公文惯用语（"现将……如下"、"特此……"等）
4. 段落格式：层次分明，段落衔接自然
5. 落款：发文单位名称（居右）、发文日期（居右，用中文数字"二〇二五年X月X日"格式）
6. 行文风格：客观中立，实事求是，不夸张不渲染

【写作原则】
- 严格以用户提供的核心要求为主线，不得偏离主题
- 参考知识库的格式和风格，但不要照搬其内容
- 建议控制在600-1000字，根据实际需要调整
- 参照北航正式公文风格：逻辑严谨、用语规范、结构完整""",
    },
}

# 写作模式定义
MODE_TEMPLATES = {
    "quick": {
        "description": "快速写作",
        "system_prefix": "",
    },
    "edit": {
        "description": "修改润色",
        "system_prefix": """你是一位精通北航（北京航空航天大学）公文写作的文字编辑助手。

【修改原则】
- 如果用户提供了【引用内容（需修改的部分）】，则只修改引用中指定的部分，保持文章其余部分完全不变
- 如果用户没有提供引用内容，则根据用户要求对全文进行修改或扩展
- 保持北航公文的正式风格：语言严谨、准确、简练
- 保持客观中立的官方口吻""",
    },
    "reply": {
        "description": "回函生成",
        "system_prefix": """你是一位精通北航（北京航空航天大学）公文写作的专家，专门负责撰写正式回函（复函）。

【回函格式规范】
1. 标题：关于XXXX的复函
2. 主送机关：来文单位的名称
3. 正文：开头引用来文标题和文号（"你单位《XXXX》（X字〔20XX〕X号）收悉"），主体逐条回复，结尾用"此复"
4. 落款：发文单位全称（居右）+ 发文日期（居右，用中文数字格式如"二〇二五年X月X日"）
5. 语言要求：正式、严谨、规范，使用公文惯用语""",
    },
    "imitate": {
        "description": "仿写公文",
        "system_prefix": """你是一位精通北航（北京航空航天大学）公文写作的专家。

【仿写要求】
- 请仔细学习参考文档的行文风格、结构组织、用语习惯和格式规范
- 以相同的写作风格撰写一篇新的公文
- 无论参考文件的格式如何，撰写的公文必须符合北航公文规范""",
    },
    "general_ref": {
        "description": "基于内容生成",
        "system_prefix": """你是一位精通北航（北京航空航天大学）公文写作的专家。

【写作要求】
- 请根据参考文档内容，撰写一篇相关的正式公文
- 撰写的公文必须符合北航公文规范""",
    },
}


def _get_output_format_instructions(mode: str) -> str:
    """根据 mode 返回不同的输出格式要求"""
    base = """
【输出格式要求】
输出必须严格分为两部分，用标记分隔：

---ARTICLE---
[文章正文]
要求：
1. 直接输出完整的公文正文，从标题开始，不要有任何前置说明文字
2. 禁止出现"以下是……"、"根据……"、"这是一篇……"等元描述语句
3. 标题使用 # 号标记，各级标题按层级使用 ##、### 等
4. 正文直接书写，首行缩进2字符
5. 落款居右，发文单位在上，日期在下
6. 保持公文正式、严谨的语言风格

---SUMMARY---"""

    if mode == "edit":
        return base + """
[修改说明]
要求：
1. 聚焦本次修改的内容，说明修改了哪些部分、改成了什么、为何这样修改
2. 如果只修改了局部内容（如一两句话），则只总结修改的部分，不要总结全文
3. 例如："已将第二段的'加强管理'修改为'完善管理体系'，使表述更加规范"
4. 不超过100字"""

    return base + """
[100字以内的简要总结]"""


# 公共公文规范（所有模式共用）
COMMON_DOCUMENT_STANDARDS = """
【北航公文通用规范】
1. 标题：居中，简洁明确，概括全文主旨
2. 正文：语言正式、严谨、规范，首行缩进2字符
3. 结构：层次分明，逻辑严密，使用公文惯用语
4. 落款：发文单位全称（居右）+ 发文日期（居右，用中文数字格式如"二〇二五年X月X日"）
5. 行文风格：客观中立，实事求是，保持高校行政公文的正式性和权威性"""


def _build_user_content(data: Dict[str, Any]) -> str:
    """构建 user prompt（数据性内容）"""
    parts = []

    # 用户需求
    if data.get("user_requirements"):
        parts.append(f"【核心要求】\n{data['user_requirements']}")
    else:
        parts.append("【核心要求】\n（未提供具体要求）")

    # RAG 参考内容
    if data.get("rag_content"):
        style_name = STYLE_TEMPLATES.get(data.get("style", "general"), {}).get("name", "公文")
        rag_section = f"\n\n【北航真实公文原文参考】\n以下是从北航公文知识库检索到的真实公文原文，请作为本次撰写的核心参考，重点学习其格式结构、用语习惯和行文风格：\n\n{data['rag_content']}"
        rag_section += f'\n\n**重要提示**：如果上述参考公文的文体与本次要写的"{style_name}"不同，请只参考其语言风格和公文用语习惯，不要照搬其内容结构。本次需要严格按照"{style_name}"的规范格式来组织文章。'
        if data.get("rag_references"):
            rag_section += f"\n\n参考来源：{'、'.join(data['rag_references'])}"
        parts.append(rag_section)
    else:
        parts.append("\n\n【北航真实公文原文参考】\n（本次未检索到北航真实公文参考，请依据你自身对公文写作规范的了解进行撰写）")

    # 上传参考文档
    if data.get("reference_content"):
        ref_section = f"\n\n【参考文档】\n以下文档供内容参考（提取关键信息，不要照搬）：\n"
        if data.get("reference_filename"):
            ref_section += f"\n[上传参考: {data['reference_filename']}]\n"
        ref_section += f"\n{data['reference_content']}"
        parts.append(ref_section)

    # 引用内容（edit 模式有引用时，强调只修改这些部分）
    if data.get("quotes"):
        quote_section = "\n\n【引用内容（需修改的部分）】\n以下内容是用户选中的需要修改的文本，请只修改这些部分，保持文章其余内容完全不变：\n"
        for i, quote in enumerate(data["quotes"]):
            quote_section += f"\n引用{i + 1}：{quote}\n"
        parts.append(quote_section)

    # 已有文章（edit 模式）
    if data.get("article_content"):
        parts.append(f"\n\n【现有文章内容】\n{data['article_content']}")

    # 提取的字段（reply 模式）
    if data.get("extracted_fields"):
        import json
        parts.append(f"\n\n【来文提取字段】\n{json.dumps(data['extracted_fields'], ensure_ascii=False, indent=2)}")

    return "\n\n".join(parts)


def build_prompt(
    mode: str,
    style: str = "general",
    data: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    统一构建 prompt

    Args:
        mode: 写作模式 ("quick" | "edit" | "reply" | "imitate" | "general_ref")
        style: 文体类型 ("notice" | "regulation" | "speech" | "general")
        data: 结构化数据，包含 user_requirements, rag_content, reference_content, quotes 等

    Returns:
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    if data is None:
        data = {}

    # 构建 system prompt
    system_parts = []

    # 1. 模式特定的前缀
    mode_info = MODE_TEMPLATES.get(mode, MODE_TEMPLATES["quick"])
    if mode_info["system_prefix"]:
        system_parts.append(mode_info["system_prefix"])

    # 2. 文体特定的规范
    if mode == "quick":
        # quick 模式需要完整的文体规范
        style_info = STYLE_TEMPLATES.get(style, STYLE_TEMPLATES["general"])
        system_parts.append(style_info["system_instructions"])
    elif mode == "edit":
        # edit 模式只保留文体名称提示，不加完整规范，避免稀释修改指令
        style_name = STYLE_TEMPLATES.get(style, STYLE_TEMPLATES["general"])["name"]
        system_parts.append(f"当前文章的文体类型为：{style_name}。修改时请保持该文体的语言风格和格式规范。")
    else:
        # reply / imitate / general_ref 模式使用公共公文规范
        system_parts.append(COMMON_DOCUMENT_STANDARDS)

    # 3. 输出格式要求（按 mode 区分）
    system_parts.append(_get_output_format_instructions(mode))

    system_prompt = "\n\n".join(system_parts)

    # 构建 user prompt
    user_prompt = _build_user_content(data)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
