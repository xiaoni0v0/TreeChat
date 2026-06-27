#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TreeChat - 树状 AI 对话
-----------------------
一个零依赖（仅用 Python 标准库）的本地服务器，作为浏览器与 DeepSeek API 之间的代理：
  - 浏览器只跟 localhost 通信，避免 CORS 问题；
  - API key 保存在服务端内存，不进前端代码；
  - 支持流式（SSE）输出。

用法：
  1) 设置环境变量 DEEPSEEK_API_KEY（可选，也可在网页里填）：
        Windows PowerShell:  $env:DEEPSEEK_API_KEY="sk-xxxx"
        bash:                export DEEPSEEK_API_KEY=sk-xxxx
  2) python app.py
  3) 浏览器自动打开 http://127.0.0.1:8000
"""

import os
import sys
import json
import threading
import webbrowser
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
API_URL = "https://api.deepseek.com/chat/completions"

# 服务端持有的状态（不写盘）。key 可由环境变量或网页设置。
STATE = {"api_key": os.environ.get("DEEPSEEK_API_KEY", "").strip()}


def read_index():
    path = os.path.join(HERE, "index.html")
    with open(path, "rb") as f:
        return f.read()


class Handler(BaseHTTPRequestHandler):
    # 安静一点的日志
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    # ---------- GET ----------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                self._send(200, read_index(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, {"error": "index.html not found next to app.py"})
        elif self.path == "/api/status":
            self._send(200, {"hasKey": bool(STATE["api_key"])})
        elif self.path.startswith("/lib/"):
            self._serve_static(self.path)
        else:
            self._send(404, {"error": "not found"})

    # 托管本地静态资源（Markdown / MathJax 库等），仅限 lib/ 目录，防目录穿越
    def _serve_static(self, path):
        rel = path.split("?", 1)[0].lstrip("/")
        full = os.path.normpath(os.path.join(HERE, rel))
        libdir = os.path.normpath(os.path.join(HERE, "lib"))
        if not full.startswith(libdir + os.sep) or not os.path.isfile(full):
            return self._send(404, {"error": "not found"})
        ext = os.path.splitext(full)[1].lower()
        ctype = {
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
            ".json": "application/json; charset=utf-8",
        }.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    # ---------- POST ----------
    def do_POST(self):
        if self.path == "/api/key":
            try:
                data = self._read_json()
            except Exception as e:
                return self._send(400, {"error": "bad json: %s" % e})
            key = (data.get("key") or "").strip()
            STATE["api_key"] = key
            return self._send(200, {"hasKey": bool(key)})

        if self.path == "/api/chat":
            return self._proxy_chat()

        self._send(404, {"error": "not found"})

    # ---------- DeepSeek 流式代理 ----------
    def _proxy_chat(self):
        try:
            data = self._read_json()
        except Exception as e:
            return self._send(400, {"error": "bad json: %s" % e})

        if not STATE["api_key"]:
            return self._send(401, {"error": "未设置 API key。请在网页右上角填写，或设置环境变量 DEEPSEEK_API_KEY。"})

        payload = {
            "model": data.get("model", "deepseek-chat"),
            "messages": data.get("messages", []),
            "stream": True,
        }
        if "temperature" in data and data["temperature"] is not None:
            payload["temperature"] = data["temperature"]

        req = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + STATE["api_key"],
                "Accept": "text/event-stream",
            },
            method="POST",
        )

        try:
            upstream = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            # 把上游错误体透传给前端（仍以 SSE 形式，方便前端统一处理）
            try:
                err_body = e.read().decode("utf-8", "replace")
            except Exception:
                err_body = str(e)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            msg = {"error": {"status": e.code, "body": _safe_json(err_body)}}
            self._sse_write("data: " + json.dumps(msg, ensure_ascii=False) + "\n\n")
            return
        except Exception as e:
            return self._send(502, {"error": "无法连接 DeepSeek: %s" % e})

        # 成功：把上游 SSE 字节流原样转发给浏览器
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                chunk = upstream.read(1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # 浏览器断开（例如用户停止），正常结束
        finally:
            try:
                upstream.close()
            except Exception:
                pass

    def _sse_write(self, text):
        try:
            self.wfile.write(text.encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def _safe_json(s):
    try:
        return json.loads(s)
    except Exception:
        return s


PORT = 8000


def main():
    import socket
    # 尝试绑定端口，失败说明端口已被占用（可能是本程序已在运行）
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", PORT))
    except OSError:
        url = "http://127.0.0.1:%d" % PORT
        print("TreeChat already running at %s — opening browser." % url)
        webbrowser.open(url)
        return
    finally:
        probe.close()

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d" % PORT
    print("TreeChat running at %s" % url)
    print("  API key from env: %s" % ("yes" if STATE["api_key"] else "no (set in web UI)"))
    print("  Press Ctrl+C to stop.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
        server.shutdown()


if __name__ == "__main__":
    main()
