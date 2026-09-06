# AI-HR-System

## 启动
```powershell
python -m pip install -r requirements.txt
python server.py
```
访问 `http://127.0.0.1:8787`。

## 功能
批量上传 PDF、DOCX、TXT、MD 简历；后端抽取文本并返回候选人结构化字段、匹配分数、风险与建议追问。

接口：`GET /api/health`；`POST /api/resumes/upload`（multipart 字段 `files`）。
