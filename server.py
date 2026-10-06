#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jev Studio 本地服务（Python 3 版）
------------------------------------------------------------
作用：
  1. 在本地托管 index.html 页面（默认 http://localhost:8722）
  2. 把浏览器发来的请求转发给 TypeSafe 官方接口

为什么需要它：
  TypeSafe 接口采用来源白名单，浏览器直接跨域调用会被 CORS 拦截。
  而“服务器到服务器”的请求不受 CORS 限制，所以由本脚本代为转发。
  浏览器只与本机 localhost 通信，属于同源，不会触发 CORS。

用法：
  1. 系统自带 Python 3（macOS / 多数 Linux 已预装；Windows 可从 python.org 安装）
  2. 在本文件夹执行： python3 server.py
  3. 浏览器会自动打开（默认 http://localhost:8722）
  4. 在页面里填写你自己的 TypeSafe API Key 即可使用

说明：
  - 默认零第三方依赖，仅使用 Python 标准库即可运行。
  - 若本机安装了 TypeSafe 官方 Python SDK（pip install typesafe-sdk），
    本脚本会自动优先使用它转发，从而获得官方的自动重试（429/529 指数退避）、
    请求校验与结构化错误；未安装时无缝回退到标准库 urllib，保证零安装可分享。
  - API Key 不会被本脚本保存或记录，仅在转发当次请求时透传给官方接口。
  - 端口被占用时自动顺延到下一个可用端口（对使用者透明）。
  - 同时监听 IPv4 与 IPv6 回环地址，避免浏览器把 localhost 解析成 ::1 时
    命中不到本服务（否则可能被其它只支持 GET 的服务抢占，导致 POST 返回 501）。
  - 可用 NO_OPEN=1 python3 server.py 关闭自动打开浏览器。
  - 可用 PORT=9000 python3 server.py 指定起始端口。
"""

import os
import sys
import json
import socket
import threading
import webbrowser
import urllib.request
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPSTREAM = "https://api.typesafe.ai/v1/systemone"
START_PORT = int(os.environ.get("PORT", "8722"))
MAX_ATTEMPTS = 20

# ---- 探测官方 Python SDK（可选依赖，装了就用，没装则回退 urllib）----
# 可用 NO_SDK=1 强制走标准库路径。
SDK = None
if os.environ.get("NO_SDK") != "1":
    try:
        import typesafe_sdk as _ts  # type: ignore
        SDK = _ts
    except Exception:
        SDK = None

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    # 关掉默认的逐条访问日志，保持终端整洁
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        if self.path == "/api/systemone":
            self._proxy()
        else:
            self.send_error(405, "Method Not Allowed")

    def do_GET(self):
        self._serve_static()

    # 把浏览器请求转发给 TypeSafe 官方接口
    def _proxy(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        payload = self.rfile.read(length) if length > 0 else b""
        auth = self.headers.get("Authorization") or ""

        if SDK is not None:
            self._proxy_via_sdk(payload, auth)
        else:
            self._proxy_via_urllib(payload, auth)

    # 统一的 JSON 响应输出
    def _send_json(self, status, obj_or_bytes, ctype="application/json"):
        if isinstance(obj_or_bytes, (bytes, bytearray)):
            body = bytes(obj_or_bytes)
        else:
            body = json.dumps(obj_or_bytes, ensure_ascii=False).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # 路径一：官方 SDK 转发（自动重试 429/529、结构化错误）
    def _proxy_via_sdk(self, payload, auth):
        # 从 Authorization: Bearer xxx 中取出 API Key
        api_key = auth[7:].strip() if auth.lower().startswith("bearer ") else auth.strip()
        try:
            req = json.loads(payload.decode("utf-8") or "{}")
        except Exception as e:
            self._send_json(400, {"error": "请求体不是合法 JSON", "detail": str(e)})
            return

        state = req.get("state")
        model = req.get("model")
        questions = req.get("questions") or {}
        try:
            client = SDK.TypeSafeClient(api_key=api_key, model=model)
        except Exception as e:
            # 一般是缺少 API Key
            self._send_json(401, {"detail": {"error_type": "authentication_error",
                                             "message": str(e)}})
            return
        try:
            # 直接传原始 question 字典：SDK 支持，且无需逐类型构造对象，
            # 从而对前端拼好的任意合法请求都保持透明兼容。
            result = client.system_one(state, questions)
            raw = getattr(result, "raw_http_response", None)
            if raw is not None and hasattr(raw, "content"):
                ctype = raw.headers.get("Content-Type", "application/json") if getattr(raw, "headers", None) else "application/json"
                self._send_json(getattr(raw, "status_code", 200), raw.content, ctype)
            else:
                # 兜底：用 SDK 的 json() 序列化
                self._send_json(200, result.json().encode("utf-8") if hasattr(result, "json") else result.model_dump())
        except Exception as e:
            # SDK 的 API 错误携带 status / body，原样透传给前端
            status = getattr(e, "status", None)
            body = getattr(e, "body", None)
            if status is not None:
                if isinstance(body, (dict, list)):
                    self._send_json(status, body)
                elif body is not None:
                    self._send_json(status, {"detail": body})
                else:
                    self._send_json(status, {"error": type(e).__name__, "detail": str(e)})
            else:
                # 连接/超时等非 HTTP 错误
                self._send_json(502, {"error": "转发到 TypeSafe 失败", "detail": str(e)})
        finally:
            try:
                client.close()
            except Exception:
                pass

    # 路径二：标准库 urllib 转发（零安装回退）
    def _proxy_via_urllib(self, payload, auth):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = auth
        req = urllib.request.Request(UPSTREAM, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as up:
                body = up.read()
                ctype = up.headers.get("Content-Type", "application/json")
                self._send_json(up.status, body, ctype)
        except urllib.error.HTTPError as e:
            # 官方返回的非 2xx（如 401 / 422）原样透传给前端
            body = e.read()
            ctype = e.headers.get("Content-Type", "application/json") if e.headers else "application/json"
            self._send_json(e.code, body, ctype)
        except Exception as e:
            self._send_json(502, {"error": "转发到 TypeSafe 失败", "detail": str(e)})

    # 托管本地静态文件
    def _serve_static(self):
        url_path = self.path.split("?")[0]
        url_path = urllib.parse.unquote(url_path)
        if url_path == "/":
            url_path = "/index.html"
        # 归一化并防止目录穿越
        rel = os.path.normpath(url_path).lstrip("/\\")
        file_path = os.path.join(BASE_DIR, rel)
        if not os.path.abspath(file_path).startswith(BASE_DIR):
            self.send_error(403, "Forbidden")
            return
        if not os.path.isfile(file_path):
            self.send_error(404, "Not Found")
            return
        ext = os.path.splitext(file_path)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        with open(file_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# 双栈 HTTP 服务器：优先监听 IPv6，并关闭 V6ONLY 使其同时接受 IPv4，
# 这样无论浏览器把 localhost 解析成 127.0.0.1 还是 ::1 都能命中本服务。
class DualStackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except (AttributeError, OSError):
            pass
        super().server_bind()


def make_server(port):
    # 先尝试双栈（IPv6 + IPv4）；个别环境不支持 IPv6 时回退到纯 IPv4。
    try:
        return DualStackServer(("::", port), Handler)
    except OSError:
        return ThreadingHTTPServer(("0.0.0.0", port), Handler)


def open_browser_later(url):
    def _open():
        try:
            webbrowser.open(url)
        except Exception:
            print("  （未能自动打开浏览器，请手动访问上面的地址）")
    threading.Timer(0.6, _open).start()


def main():
    port = START_PORT
    server = None
    for _ in range(MAX_ATTEMPTS):
        try:
            server = make_server(port)
            break
        except OSError:
            print("  端口 {} 被占用，自动尝试 {} …".format(port, port + 1))
            port += 1
    if server is None:
        print("  启动失败：连续 {} 个端口都被占用。".format(MAX_ATTEMPTS))
        sys.exit(1)

    url = "http://localhost:{}".format(port)
    backend = "官方 SDK（typesafe-sdk，含自动重试）" if SDK is not None else "标准库 urllib（零依赖）"
    print("")
    print("  Jev Studio 已启动 ✓")
    print("  转发后端： " + backend)
    print("  正在自动打开浏览器： " + url)
    print("  若没有自动打开，请手动访问上面的地址。")
    print("  停止服务： 按 Ctrl + C")
    print("")

    if os.environ.get("NO_OPEN") != "1":
        open_browser_later(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止。")
        server.shutdown()


if __name__ == "__main__":
    main()
