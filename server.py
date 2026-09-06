from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import json
import re
import shutil
import uuid

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
ALLOWED = {".pdf", ".docx", ".txt", ".md"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

def extract_text(path):
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
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

def parse_multipart(handler):
    content_type = handler.headers.get("Content-Type", "")
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type, re.I)
    if not match:
        raise ValueError("Missing multipart boundary")
    boundary = (match.group(1) or match.group(2)).strip().encode("utf-8")
    length = int(handler.headers.get("Content-Length", "0"))
    if length > MAX_UPLOAD_BYTES * 10:
        raise ValueError("Request is too large")
    body = handler.rfile.read(length)
    fields = []
    for part in body.split(b"--" + boundary):
        part = part.strip(b"\r\n-")
        if not part or b"\r\n\r\n" not in part:
            continue
        raw_headers, content = part.split(b"\r\n\r\n", 1)
        headers = raw_headers.decode("utf-8", errors="ignore")
        disposition = re.search(r'Content-Disposition:.*?name="([^"]+)"(?:;\s*filename="([^"]*)")?', headers, re.I)
        if disposition:
            fields.append({"name": disposition.group(1), "filename": disposition.group(2), "content": content.rstrip(b"\r\n")})
    return fields

def find_name(text, filename):
    compact = re.sub(r"\s+", " ", text)
    patterns = [r"(?:??|name)\s*[:?]\s*([\u4e00-\u9fa5A-Za-z? ]{2,30})", r"^([\u4e00-\u9fa5]{2,4})\s"]
    for pattern in patterns:
        found = re.search(pattern, compact, re.I)
        if found:
            return found.group(1).strip()
    return Path(filename).stem

def parse_resume(text, filename):
    compact = re.sub(r"\s+", " ", text)
    skill_map = {"SQL": r"sql", "Python": r"python", "Excel": r"excel", "Axure": r"axure", "\u7528\u6237\u7814\u7a76": r"\u7528\u6237\u7814\u7a76|\u7528\u6237\u8c03\u7814", "\u6570\u636e\u5206\u6790": r"\u6570\u636e\u5206\u6790|\u6307\u6807|\u6f0f\u6597", "\u4ea7\u54c1\u8bbe\u8ba1": r"\u4ea7\u54c1\u8bbe\u8ba1|\u9700\u6c42\u5206\u6790|\u539f\u578b", "\u9879\u76ee\u7ba1\u7406": r"\u9879\u76ee\u7ba1\u7406|\u534f\u4f5c"}
    skills = [label for label, pattern in skill_map.items() if re.search(pattern, text, re.I)]
    school_match = re.search(r"([\u4e00-\u9fa5A-Za-z]{2,24}(?:\u5927\u5b66|\u5b66\u9662))", compact)
    weights = [(r"\u672c\u79d1|\u7855\u58eb|\u7814\u7a76\u751f", 12), (r"\u5b9e\u4e60|\u5de5\u4f5c\u7ecf\u5386|\u5de5\u4f5c\u7ecf\u9a8c", 14), (r"sql", 18), (r"\u7528\u6237\u7814\u7a76|\u7528\u6237\u8c03\u7814", 14), (r"\u6570\u636e\u5206\u6790", 14), (r"\u4ea7\u54c1|\u9700\u6c42\u5206\u6790", 14), (r"\u9879\u76ee", 6)]
    score = min(98, 35 + sum(weight for pattern, weight in weights if re.search(pattern, text, re.I)))
    name_match = re.search(r"(?:\u59d3\u540d|name)\s*[:?]\s*([\u4e00-\u9fa5A-Za-z? ]{2,30})", compact, re.I)
    return {"id": uuid.uuid4().hex[:8], "name": name_match.group(1).strip() if name_match else Path(filename).stem, "school": school_match.group(1) if school_match else "\u672a\u8bc6\u522b", "education": "\u672c\u79d1\u53ca\u4ee5\u4e0a" if re.search(r"\u672c\u79d1|\u7855\u58eb|\u7814\u7a76\u751f", text) else "\u672a\u8bc6\u522b", "skills": skills, "experience": "\u5df2\u8bc6\u522b" if re.search(r"\u5b9e\u4e60|\u5de5\u4f5c\u7ecf\u5386|\u9879\u76ee", text) else "\u672a\u8bc6\u522b", "score": score, "status": "\u5f3a\u5339\u914d" if score >= 75 else "\u5f85\u590d\u6838", "filename": filename, "text_preview": compact[:600], "risks": ["\u5efa\u8bae\u9a8c\u8bc1\u6280\u80fd\u6df1\u5ea6" if skills else "\u6280\u80fd\u4fe1\u606f\u4e0d\u8db3", "\u5230\u5c97\u65f6\u95f4\u9700\u9762\u8bd5\u786e\u8ba4"], "questions": ["\u8bf7\u7528 STAR \u6cd5\u5219\u8bf4\u660e\u4e00\u6b21\u4f60\u89e3\u51b3\u590d\u6742\u95ee\u9898\u7684\u7ecf\u5386\u3002", "\u8bf7\u5177\u4f53\u8bf4\u660e\u4f60\u7684\u9879\u76ee\u7ed3\u679c\u548c\u8861\u91cf\u6307\u6807\u3002"]}

def jd_analysis(jd):
    dimensions = [("\u5c97\u4f4d\u804c\u8d23", "\u6838\u5fc3\u5de5\u4f5c", r"\u8d1f\u8d23|\u534f\u52a9|\u63a8\u52a8|\u642d\u5efa|\u7ef4\u62a4|\u4f18\u5316|\u5206\u6790|\u8bbe\u8ba1|\u7ba1\u7406", "\u6839\u636e\u52a8\u8bcd\u8bc6\u522b\u4e3b\u8981\u5de5\u4f5c\u4efb\u52a1"), ("\u5b66\u5386\u80cc\u666f", "\u5b66\u5386\u4e0e\u4e13\u4e1a", r"\u672c\u79d1|\u7855\u58eb|\u7814\u7a76\u751f|\u5b66\u5386|\u4e13\u4e1a", "\u4f18\u5148\u6838\u9a8c\u5b66\u5386\u548c\u4e13\u4e1a\u5339\u914d"), ("\u5de5\u4f5c\u7ecf\u9a8c", "\u7ecf\u9a8c\u5e74\u9650\u4e0e\u7c7b\u578b", r"\d+\u5e74|\u5b9e\u4e60|\u5de5\u4f5c\u7ecf\u9a8c|\u76f8\u5173\u7ecf\u9a8c|\u884c\u4e1a\u7ecf\u9a8c", "\u786e\u8ba4\u7ecf\u9a8c\u5e74\u9650\u3001\u884c\u4e1a\u548c\u5c97\u4f4d\u76f8\u5173\u6027"), ("\u4e13\u4e1a\u6280\u80fd", "\u5de5\u5177\u4e0e\u6280\u672f", r"SQL|Python|Excel|Axure|Figma|Java|\u6570\u636e\u5206\u6790|\u7528\u6237\u7814\u7a76|\u9879\u76ee\u7ba1\u7406", "\u6838\u9a8c\u5de5\u5177\u719f\u7ec3\u5ea6\u548c\u771f\u5b9e\u4ea7\u51fa"), ("\u4e1a\u52a1\u573a\u666f", "\u4e1a\u52a1\u4e0e\u4ea7\u54c1\u9886\u57df", r"B\u7aef|C\u7aef|\u7535\u5546|\u91d1\u878d|\u6559\u80b2|SaaS|\u589e\u957f|\u8fd0\u8425|\u4ea7\u54c1", "\u4e86\u89e3\u5019\u9009\u4eba\u662f\u5426\u719f\u6089\u4e1a\u52a1\u8bed\u5883"), ("\u80fd\u529b\u6a21\u578b", "\u901a\u7528\u4e0e\u5c97\u4f4d\u80fd\u529b", r"\u6c9f\u901a|\u534f\u4f5c|\u903b\u8f91|\u521b\u65b0|\u6297\u538b|\u5b66\u4e60|\u89e3\u51b3\u95ee\u9898|\u7ed3\u6784\u5316", "\u901a\u8fc7\u884c\u4e3a\u9762\u8bd5\u9a8c\u8bc1\u80fd\u529b\u8868\u73b0"), ("\u7ee9\u6548\u76ee\u6807", "\u7ed3\u679c\u4e0e\u6307\u6807", r"\u6307\u6807|\u76ee\u6807|\u8f6c\u5316|\u589e\u957f|\u7559\u5b58|\u6536\u5165|\u6548\u7387|\u590d\u76d8|\u7ed3\u679c", "\u8981\u6c42\u5019\u9009\u4eba\u63d0\u4f9b\u91cf\u5316\u7ed3\u679c"), ("\u5de5\u4f5c\u65b9\u5f0f", "\u534f\u4f5c\u4e0e\u4ea4\u4ed8", r"\u8de8\u90e8\u95e8|\u7814\u53d1|\u8bbe\u8ba1|\u8fdc\u7a0b|\u5230\u5c97|\u6bcf\u5468|\u51fa\u5dee|\u52a0\u73ed", "\u786e\u8ba4\u534f\u4f5c\u5bf9\u8c61\u3001\u8282\u594f\u548c\u5230\u5c97\u7ea6\u675f"), ("\u85aa\u916c\u798f\u5229", "\u85aa\u916c\u4e0e\u798f\u5229", r"\u85aa\u8d44|\u85aa\u916c|\u6708\u85aa|\u5e74\u85aa|\u5956\u91d1|\u80a1\u7968|\u4e94\u9669|\u798f\u5229", "\u9762\u8bd5\u524d\u786e\u8ba4\u85aa\u916c\u533a\u95f4\u548c\u798f\u5229"), ("\u5730\u70b9\u5b89\u6392", "\u57ce\u5e02\u4e0e\u529e\u516c", r"\u5317\u4eac|\u4e0a\u6d77|\u6df1\u5733|\u5e7f\u5dde|\u676d\u5dde|\u5730\u70b9|\u529e\u516c|\u9a7b\u573a", "\u786e\u8ba4\u57ce\u5e02\u3001\u529e\u516c\u6a21\u5f0f\u548c\u901a\u52e4\u8981\u6c42")]
    result=[]
    for name,value,pattern,action in dimensions:
        matches=re.findall(pattern,jd,re.I)
        result.append({"name": name, "value": value, "matched": bool(matches), "evidence": "?".join(dict.fromkeys(matches))[:80] if matches else "???", "action": action, "hard": name in {"????", "????", "????", "????", "????"}})
    return result

def reply(handler, payload, status=200):
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    handler.send_response(status); handler.send_header("Content-Type","application/json; charset=utf-8"); handler.send_header("Content-Length",str(len(data))); handler.end_headers(); handler.wfile.write(data)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/api/health": return reply(self,{"ok":True,"service":"AI-HR-System","python":"3.13+"})
        target=ROOT/("index.html" if path=="/" else path.lstrip("/"))
        if target.is_file() and ROOT in target.resolve().parents:
            data=target.read_bytes(); suffix=target.suffix.lower(); content_type={".html":"text/html",".js":"application/javascript",".css":"text/css"}.get(suffix,"application/octet-stream")+"; charset=utf-8"; self.send_response(200); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        self.send_error(404)
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            if path=="/api/jd/parse":
                length=int(self.headers.get("Content-Length","0")); jd=json.loads(self.rfile.read(length)).get("jd","").strip()
                if not jd: raise ValueError("JD ????")
                requirements=jd_analysis(jd); return reply(self,{"requirements":requirements,"dimension_count":len(requirements),"matched_count":sum(x["matched"] for x in requirements)})
            if path=="/api/interview/generate":
                length=int(self.headers.get("Content-Length","0")); jd=json.loads(self.rfile.read(length)).get("jd","").strip()
                if not jd: raise ValueError("JD ????")
                questions=[("???????","?????????????????????"),("????","????????????????????"),("????","????????????????????"),("????","??????????????????????????"),("??????","?????????????????????????"),("????","??????????????????????")]
                return reply(self,{"count":len(questions),"questions":[{"dimension":a,"question":b,"followups":["????????","?????????","????????","??????????"]} for a,b in questions]})
            if path!="/api/resumes/upload": return reply(self,{"error":"Not found"},404)
            items=[x for x in parse_multipart(self) if x["name"]=="files"]
            if not items: raise ValueError("???????")
            results=[]
            for item in items:
                filename=Path(item["filename"] or "").name
                if not filename: raise ValueError("?????")
                if Path(filename).suffix.lower() not in ALLOWED: raise ValueError("Unsupported file type: "+filename)
                if len(item["content"])>MAX_UPLOAD_BYTES: raise ValueError("File is too large: "+filename)
                saved=UPLOADS/(uuid.uuid4().hex+"_"+filename); saved.write_bytes(item["content"])
                try: results.append(parse_resume(extract_text(saved),filename))
                finally: saved.unlink(missing_ok=True)
            return reply(self,{"count":len(results),"candidates":results})
        except Exception as exc:
            return reply(self,{"error":str(exc)},400)

if __name__=="__main__": ThreadingHTTPServer(("127.0.0.1",8787),Handler).serve_forever()
