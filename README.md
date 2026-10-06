# Jev Studio · 本地运行版

一个可以直接分享给别人使用的 TypeSafe **Jev** 调用界面。后端脚本在**用户本机**运行，浏览器只与 `localhost` 通信，从而绕开官方接口的 CORS 白名单限制。

## 为什么需要本地脚本

TypeSafe 的接口（`api.typesafe.ai/v1/systemone`）采用**来源白名单**，浏览器直接跨域调用会被拦截（返回 `Disallowed CORS origin`）。因此纯 HTML 双击打开无法调用。本方案用一个零依赖的本地脚本转发请求：服务器到服务器不受 CORS 限制，问题彻底解决。

## 使用步骤

后端使用 **Python 3**（macOS 与多数 Linux 已自带，无需额外安装）。

1. 确认有 Python 3（终端执行 `python3 --version`；Windows 可从 [python.org](https://www.python.org/downloads/) 安装，安装时勾选 “Add Python to PATH”）。
2. 启动服务：
   - **macOS / Linux**：双击 `start.command`（或终端执行 `python3 server.py`）
   - **Windows**：双击 `start.bat`（或命令行执行 `python server.py`）
3. 浏览器会自动打开，或手动访问：`http://localhost:8722`
4. 在页面「连接配置」里填入你自己的 **TypeSafe API Key**，即可开始使用。

> 停止服务：在运行窗口按 `Ctrl + C`。

## 可选：启用官方 Python SDK

脚本默认零依赖（仅用标准库）。若本机安装了官方 SDK，会**自动优先使用它**转发，从而获得官方的自动重试（429/529 指数退避）与结构化错误：

```
pip install typesafe-sdk
```

未安装时无缝回退到标准库 `urllib`，保证零安装也能分享给别人直接用。可用 `NO_SDK=1 python3 server.py` 强制走标准库路径。

## 文件说明

| 文件 | 作用 |
|------|------|
| `index.html` | 前端界面（构建请求、可视化结果） |
| `server.py` | 本地服务：托管页面 + 转发 API 请求（默认仅用 Python 标准库） |
| `start.command` | macOS / Linux 一键启动 |
| `start.bat` | Windows 一键启动 |

## 安全说明

- API Key 只保存在你自己的浏览器内存中，刷新即消失。
- 本地脚本**不会保存或记录**你的 Key，仅在转发当次请求时透传给官方接口。
- 整个过程数据只在「你的电脑 ↔ TypeSafe 官方」之间流动，不经过任何第三方服务器。

## 常见问题

- **提示“需要启动本地服务”**：说明你是直接双击 HTML 打开的（`file://`）。请改用 `start.command` / `start.bat` 启动，再访问 `http://localhost:8722`。
- **提示 `501 Unsupported method ('POST')`**：说明 8722 端口被另一个只支持 GET 的服务（如 `python3 -m http.server`）抢占了。请关掉那个服务，再用 `python3 server.py` 启动本脚本（本脚本已双栈监听 IPv4/IPv6，避免被抢占）。
- **提示 `401`**：API Key 无效或填写有误。
- **提示 `422`**：请求内容不符合接口要求（如缺少必填字段）。
- **端口 8722 被占用**：脚本会**自动顺延**到下一个可用端口（8723、8724…），以终端显示的地址为准；也可手动指定：`PORT=9000 python3 server.py`。
- **不想自动打开浏览器**（如在服务器上运行）：`NO_OPEN=1 python3 server.py`。
