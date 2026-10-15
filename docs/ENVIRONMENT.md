# 环境说明

## 一、环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.11 及以上 | 隔离环境建在仓库根目录 `.venv/`（已在 `.gitignore` 中） |
| Node.js | 22 及以上 | 仅前端需要 |
| 操作系统 | Windows（脚本为 PowerShell） | Python 与测试部分跨平台 |

依赖清单：`requirements.txt`（运行）与 `requirements-dev.txt`（含开发与校验依赖，内嵌 `-r requirements.txt`）。

## 二、一次性初始化

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1
```

该脚本会建立 `.venv`、升级 pip、安装依赖并做一次导入自检。
若系统 `python` 不是目标解释器，用 `-BasePython` 指定：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1 -BasePython "C:\Path\To\python.exe"
```

## 三、日常验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_all.ps1
```

依次执行 `validate_research_data.py`、`validate_stage2_content.py` 与 `unittest discover -s tests`；
任何一步失败都会立即中断并报出是哪一步。

> 数据扩充后，应同步更新校验器中对应的契约定义，而不是把校验当噪声关掉。

## 四、启动服务

后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
```

可选参数：`-Port 8000`、`-BindHost 127.0.0.1`、`-Reload`（开发热重载）。

前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

首次运行会自动执行 `npm install`；加 `-SkipBuild` 可跳过构建直接使用已有产物。

访问：后端健康检查 `http://127.0.0.1:8000/api/health`，前端 `http://127.0.0.1:3000`。

## 五、环境变量

后端读取仓库根目录的 `.env.local`（该文件不入库），字段见 `.env.example`：

| 变量 | 用途 |
|---|---|
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | 生成式模型（OpenAI 兼容接口），用于流程骨架抽取与回答生成 |
| `DASHSCOPE_API_KEY` | 语义检索的向量嵌入（`text-embedding-v4`）与重排序（`gte-rerank-v2`） |

模型不可用时，系统退回由检索证据拼装的回答，不会退回写死的固定答案。
