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

PROVIDERS = {
    "deepseek": "https://api.deepseek.com/chat/completions",
    "openai":   "https://api.openai.com/v1/chat/completions",
    "groq":     "https://api.groq.com/openai/v1/chat/completions",
    "xai":      "https://api.x.ai/v1/chat/completions",
    "mistral":  "https://api.mistral.ai/v1/chat/completions",
    "kimi":     "https://api.moonshot.cn/v1/chat/completions",
    "zhipu":    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
}
_ENV_KEYS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai":   "OPENAI_API_KEY",
    "groq":     "GROQ_API_KEY",
    "xai":      "XAI_API_KEY",
    "mistral":  "MISTRAL_API_KEY",
    "kimi":     "KIMI_API_KEY",
    "zhipu":    "ZHIPU_API_KEY",
    "qwen":     "QWEN_API_KEY",
}
# 服务端持有的状态（不写盘）。key 可由环境变量或网页设置。
STATE = {"keys": {p: os.environ.get(e, "").strip() for p, e in _ENV_KEYS.items()}}


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
            self._send(200, {"keys": {p: bool(v) for p, v in STATE["keys"].items()}})
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
            provider = (data.get("provider") or "deepseek").strip()
            key = (data.get("key") or "").strip()
            if provider in STATE["keys"]:
                STATE["keys"][provider] = key
            return self._send(200, {"keys": {p: bool(v) for p, v in STATE["keys"].items()}})

        if self.path == "/api/test-key":
            return self._test_key()

        if self.path == "/api/chat":
            return self._proxy_chat()

        self._send(404, {"error": "not found"})

    # ---------- Key 验证（发一条最小非流式请求，只看状态码） ----------
    def _test_key(self):
        try:
            data = self._read_json()
        except Exception as e:
            return self._send(400, {"error": str(e)})
        provider = (data.get("provider") or "deepseek").strip()
        if provider not in PROVIDERS:
            return self._send(400, {"error": "未知提供商: " + provider})
        api_key = (data.get("key") or STATE["keys"].get(provider, "")).strip()
        if not api_key:
            return self._send(400, {"error": "Key 未设置"})
        model = (data.get("model") or "").strip()
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "max_tokens": 1,
        }).encode("utf-8")
        req = urllib.request.Request(
            PROVIDERS[provider], data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + api_key},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            resp.read()
            return self._send(200, {"ok": True})
        except urllib.error.HTTPError as e:
            try:
                body = _safe_json(e.read().decode("utf-8", "replace"))
            except Exception:
                body = str(e)
            return self._send(200, {"ok": False, "status": e.code, "body": body})
        except Exception as e:
            return self._send(200, {"ok": False, "body": str(e)})

    # ---------- 流式代理 ----------
    def _proxy_chat(self):
        try:
            data = self._read_json()
        except Exception as e:
            return self._send(400, {"error": "bad json: %s" % e})

        provider = (data.get("provider") or "deepseek").strip()
        if provider not in PROVIDERS:
            return self._send(400, {"error": "未知提供商: " + provider})
        # key 优先来自请求体（每用户独立），没有则降级到服务端环境变量
        api_key = (data.get("key") or STATE["keys"].get(provider, "")).strip()
        if not api_key:
            return self._send(401, {"error": "未设置 %s 的 API key，请在设置中填写。" % provider})

        # 透传前端 payload，去掉仅供路由用的字段
        payload = {k: v for k, v in data.items() if k not in ("provider", "key")}
        payload["stream"] = True
        payload.setdefault("model", "deepseek-chat")
        payload.setdefault("messages", [])

        req = urllib.request.Request(
            PROVIDERS[provider],
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + api_key,
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


def main():
    import socket
    import argparse

    parser = argparse.ArgumentParser(description="TreeChat local server")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000,
                        help="bind port (default: 8000)")
    parser.add_argument("--server", action="store_true",
                        help="shortcut for --host 0.0.0.0 (multi-user server mode)")
    args = parser.parse_args()

    host = "0.0.0.0" if args.server else args.host
    port = args.port

    # 尝试绑定端口，失败说明端口已被占用（可能是本程序已在运行）
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        url = "http://127.0.0.1:%d" % port
        print("TreeChat already running at %s — opening browser." % url)
        webbrowser.open(url)
        return
    finally:
        probe.close()

    server = ThreadingHTTPServer((host, port), Handler)
    url = "http://127.0.0.1:%d" % port

    if host == "0.0.0.0":
        # 服务器模式：找一个局域网/公网 IP 提示用户
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            s.close()
        except Exception:
            lan_ip = "<your-ip>"
        print("TreeChat running in SERVER mode")
        print("  Local:   http://127.0.0.1:%d" % port)
        print("  Network: http://%s:%d" % (lan_ip, port))
    else:
        print("TreeChat running at %s" % url)
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    loaded = [p for p, v in STATE["keys"].items() if v]
    print("  API keys from env: %s" % (", ".join(loaded) if loaded else "none (set in web UI)"))
    print("  Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
        server.shutdown()


if __name__ == "__main__":
    main()
