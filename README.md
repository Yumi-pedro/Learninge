# BetterEnglish

保留五个页面和本地学习数据，通过 Python 本机服务连接 Ollama，提供英语口语文本反馈。

零基础启动、Mac 检查、模型准备、数据保护和测试范围请阅读 [中文使用说明](README.txt)。

无需 Python 第三方依赖。在本目录运行 `python3 server.py`，继续使用原来的 `http://localhost:8080`。
默认模型为本地 `qwen3:4b`，需另外在 Mac 上确认安装并验证。没有模型时会明确提示，不伪装成 AI。

本轮新增同话题两轮回答对照、真实引用与重复建议校验。更新时需同时更新 `index.html` 和 `server.py`，并重启网站服务。已有词汇及历史存储键名保持不变。
