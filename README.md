# AI-HR-System

AI 招聘全流程助手，包含 JD 结构化、简历筛选、面试题生成与面试评价。

## 功能
- 批量上传并解析 PDF、Word（DOCX）、TXT、Markdown 简历。
- 自动提取姓名、学校、学历、技能、经历，并生成可解释的匹配分数、潜在风险和建议追问。
- Python 标准库 HTTP 服务，`pypdf` 和 `python-docx` 负责文档文本解析。

## 启动
```powershell
python -m pip install -r requirements.txt
python server.py
```
访问 `http://127.0.0.1:8787`。

## API
- `GET /api/health`
- `POST /api/resumes/upload`：multipart 字段 `files`，支持多个文件。

评分为可解释的关键词规则基线，后续可在 `parse` 内替换为 LLM 提取器而不改变接口。
