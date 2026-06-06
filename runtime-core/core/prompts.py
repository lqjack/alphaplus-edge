RAG_SUMMARY_WITH_TITLE_AND_CONTENT = """
任务：请根据提供的文章标题以及对应的文章内容，完成以下分析任务，并以 JSON 格式返回结果。

输入：
文章标题：{article_title}

分析要求：
1. **重要性**：根据标题和内容判断文章的重要性（高、中、低）。
2. **利好利空板块**：分析文章中提到的板块，并判断是利好还是利空。
3. **热点度**：评估文章的热点程度（0-1范围内的浮点数）。
4. **核心内容总结**：
    - **一句话核心观点**：用一句话概括文章的核心观点。
    - **三段式详细摘要**：生成三段式详细摘要，每段不超过100字。
5. **情感与影响分析**：
    - **情感倾向**：判断文章的情感倾向（利好/利空）。
    - **关联行业**：分析文章中提到的关联行业。
    - **潜在影响范围**：评估文章的潜在影响范围（如“GDP萎缩”关联美股、能源、政策）。
6. **投资策略建议**：
    - **投资计划**：基于文章内容给出的投资计划建议。
    - **投资策略**：基于文章内容给出的投资策略建议。
7. **关键指标**：提取文章中的关键指标（如GDP预测、PCE指数），并以JSON格式返回。

输出格式：
{{
    "importance": "高/中/低",
    "bullish_sectors": ["板块1", "板块2"],
    "bearish_sectors": ["板块1", "板块2"],
    "hot_degree": 0.8,
    "core_viewpoint": "一句话核心观点",
    "detailed_summary": ["摘要1", "摘要2", "摘要3"],
    "summary": "总结核心内容",
    "sentiment": "利好/利空",
    "related_industries": ["行业1", "行业2"],
    "impact_scope": "潜在影响范围",
    "investment_plan": "投资计划建议",
    "investment_strategy": "投资策略建议",
    "key_metrics": {{
        "GDP预测": "值",
        "PCE指数": "值"
    }}
}}
"""

SUMMARY_WITH_TITLE_AND_CONTENT = """
任务：请根据提供的文章标题和内容，完成以下分析任务，并以 JSON 格式返回结果。

输入：
文章标题：{article_title}
文章内容：{article_html}

分析要求：
1. **重要性**：根据标题和内容判断文章的重要性（高、中、低）。
2. **利好利空板块**：分析文章中提到的板块，并判断是利好还是利空。
3. **热点度**：评估文章的热点程度（0-1范围内的浮点数）。
4. **核心内容总结**：
    - **一句话核心观点**：用一句话概括文章的核心观点。
    - **三段式详细摘要**：生成三段式详细摘要，每段不超过100字。
5. **情感与影响分析**：
    - **情感倾向**：判断文章的情感倾向（利好/利空）。
    - **关联行业**：分析文章中提到的关联行业。
    - **潜在影响范围**：评估文章的潜在影响范围（如“GDP萎缩”关联美股、能源、政策）。
6. **投资策略建议**：
    - **投资计划**：基于文章内容给出的投资计划建议。
    - **投资策略**：基于文章内容给出的投资策略建议。
7. **关键指标**：提取文章中的关键指标（如GDP预测、PCE指数），并以JSON格式返回。

输出格式：
{{
    "importance": "高/中/低",
    "bullish_sectors": ["板块1", "板块2"],
    "bearish_sectors": ["板块1", "板块2"],
    "hot_degree": 0.8,
    "core_viewpoint": "一句话核心观点",
    "detailed_summary": ["摘要1", "摘要2", "摘要3"],
    "summary": "总结核心内容",
    "sentiment": "利好/利空",
    "related_industries": ["行业1", "行业2"],
    "impact_scope": "潜在影响范围",
    "investment_plan": "投资计划建议",
    "investment_strategy": "投资策略建议",
    "key_metrics": {{
        "GDP预测": "值",
        "PCE指数": "值"
    }}
}}
"""
RAG_SUMMARY_DAILY_CONTENT = """
任务：请根据task_id: {task_id} 对应的输入内容分析结果，生成一天内的核心内容总结。
输出要求：
请以简洁的方式总结当天的核心内容，不超过500字。
"""

SUMMARY_DAILY_CONTENT = """
任务：请根据以下分析结果，生成一天内的核心内容总结。
task_id : {task_id}
输入：
{analysis_contents}

输出要求：
请以简洁的方式总结当天的核心内容，不超过500字。
"""


VIDEO_QA_PROMPT = """

Analyze the provided video frames and corresponding audio transcription to \
answer the given question(s) thoroughly and accurately.

Instructions:
    1. Visual Analysis:
        - Examine the video frames to identify visible entities.
        - Differentiate objects, species, or features based on key attributes \
such as size, color, shape, texture, or behavior.
        - Note significant groupings, interactions, or contextual patterns \
relevant to the analysis.

    2. Audio Integration:
        - Use the audio transcription to complement or clarify your visual \
observations.
        - Identify names, descriptions, or contextual hints in the \
transcription that help confirm or refine your visual analysis.

    3. Detailed Reasoning and Justification:
        - Provide a brief explanation of how you identified and distinguished \
each species or object.
        - Highlight specific features or contextual clues that informed \
your reasoning.

    4. Comprehensive Answer:
        - Specify the total number of distinct species or object types \
identified in the video.
        - Describe the defining characteristics and any supporting evidence \
from the video and transcription.

    5. Important Considerations:
        - Pay close attention to subtle differences that could distinguish \
similar-looking species or objects 
          (e.g., juveniles vs. adults, closely related species).
        - Provide concise yet complete explanations to ensure clarity.

**Audio Transcription:**
{audio_transcription}

**Question:**
{question}
"""