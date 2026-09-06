from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import cgi
import json
import re
import shutil
import uuid

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
ALLOWED = {".pdf", ".docx", ".txt", ".md"}

def extract_text(path):
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if suffix == ".docx":
        from docx import Document
        doc = Document(str(path))
        paragraphs = "\n".join(p.text for p in doc.paragraphs)
        tables = "\n".join(" ".join(cell.text for cell in row.cells) for table in doc.tables for row in table.rows)
        return paragraphs + "\n" + tables
    raise ValueError("Unsupported file type")

def parse_resume(text, filename):
    compact = re.sub(r"\s+", " ", text)
    skill_names = ["sql", "\u7528\u6237\u7814\u7a76", "\u6570\u636e\u5206\u6790", "\u4ea7\u54c1", "Excel", "Axure", "Python", "\u9879\u76ee\u7ba1\u7406"]
    skills = [name.upper() if name == "sql" else name for name in skill_names if re.search(name, text, re.I)]
    weights = {"sql": 22, "\u7528\u6237\u7814\u7a76": 18, "\u4ea7\u54c1": 18, "\u6570\u636e\u5206\u6790": 16, "\u672c\u79d1": 12, "\u5b9e\u4e60": 14}
    score = min(98, 45 + sum(value for key, value in weights.items() if re.search(key, text, re.I)))
    name_match = re.search(r"\u59d3\u540d[:： ]+([\u4e00-\u9fa5]{2,4})", compact)
    school_match = re.search(r"([\u4e00-\u9fa5]{2,20}(?:\u5927\u5b66|\u5b66\u9662))", compact)
    return {"id": uuid.uuid4().hex[:8], "name": name_match.group(1) if name_match else Path(filename).stem, "school": school_match.group(1) if school_match else "\u672a\u8bc6\u522b", "education": "\u672c\u79d1\u53ca\u4ee5\u4e0a" if re.search(r"\u672c\u79d1|\u7855\u58eb|\u7814\u7a76\u751f", text) else "\u672a\u8bc6\u522b", "skills": skills, "score": score, "status": "\u5f3a\u5339\u914d" if score >= 78 else "\u5f85\u590d\u6838", "filename": filename, "text_preview": compact[:500], "risks": ["\u5efa\u8bae\u9a8c\u8bc1 SQL \u5b9e\u6218\u6df1\u5ea6" if "sql" in compact.lower() else "\u672a\u8bc6\u522b\u5230 SQL", "\u5230\u5c97\u65f6\u95f4\u9700\u9762\u8bd5\u786e\u8ba4"], "questions": ["\u8bf7\u7528 STAR \u6cd5\u5219\u8bf4\u660e\u4f60\u5982\u4f55\u901a\u8fc7\u6570\u636e\u63a8\u52a8\u4e00\u6b21\u4ea7\u54c1\u6539\u8fdb\uff1f", "\u8bf7\u5177\u4f53\u4ecb\u7ecd\u4e00\u6bb5\u7528\u6237\u7814\u7a76\u6216\u9700\u6c42\u5206\u6790\u7ecf\u5386\u3002"]}

def reply(handler, payload, status=200):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return reply(self, {"ok": True, "service": "AI-HR-System"})
        target = ROOT / ("index.html" if path == "/" else path.lstrip("/"))
        if target.is_file() and ROOT in target.resolve().parents:
            data = target.read_bytes()
            content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "application/javascript; charset=utf-8" if target.suffix == ".js" else "text/css; charset=utf-8"
            self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        self.send_error(404)
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/jd/parse":
                length = int(self.headers.get("Content-Length", "0")); jd = json.loads(self.rfile.read(length)).get("jd", "").strip()
                if not jd: raise ValueError("JD 不能为空")
                patterns = [("学历背景", "本科及以上", bool(re.search(r"本科|硕士|学历", jd))), ("产品相关经验", "产品/用户研究经验", bool(re.search(r"产品|用户研究|需求分析|实习", jd))), ("数据分析能力", "SQL / 数据分析", bool(re.search(r"SQL|数据分析|指标", jd, re.I))), ("到岗稳定性", "到岗时间待确认", bool(re.search(r"到岗|每周|实习", jd))), ("加分项", "B端 / 竞品分析 / 项目经验", False)]
                return reply(self, {"requirements": [{"name": n, "value": v, "hard": h} for n, v, h in patterns]})
            if path == "/api/interview/generate":
                length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length))
                if not payload.get("jd", "").strip(): raise ValueError("JD 不能为空")
                questions = [("01 / 用户洞察", "请分享一个你通过用户反馈推动产品或方案改进的经历。", ["当时的具体情境是什么？", "你负责哪一部分？", "最终用什么指标证明结果？"]), ("02 / 数据分析", "在一个熟悉的项目中，你如何使用数据发现问题并做出判断？", ["你选择了哪些数据？", "数据与直觉冲突时如何处理？", "结论如何影响决策？"]), ("03 / 产品思维", "如果让你优化一个校园二手交易平台，你会从哪里开始？", ["如何定义核心用户？", "第一步验证什么假设？", "资源有限时会放弃什么？"])]
                return reply(self, {"count": len(questions), "questions": [{"dimension": a, "question": b, "followups": c} for a, b, c in questions]})
            if path != "/api/resumes/upload": return reply(self, {"error": "Not found"}, 404)
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")})
            items = form["files"] if "files" in form else []; items = items if isinstance(items, list) else [items]; results = []
            for item in items:
                filename = Path(item.filename or "").name
                if Path(filename).suffix.lower() not in ALLOWED: raise ValueError("Unsupported file type")
                saved = UPLOADS / f"{uuid.uuid4().hex}_{filename}"; item.file.seek(0)
                with saved.open("wb") as output: shutil.copyfileobj(item.file, output)
                try: results.append(parse_resume(extract_text(saved), filename))
                finally: saved.unlink(missing_ok=True)
            return reply(self, {"count": len(results), "candidates": results})
        except Exception as exc:
            return reply(self, {"error": str(exc)}, 400)

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8787), Handler).serve_forever()
