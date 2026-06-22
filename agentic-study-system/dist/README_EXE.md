# Agentic Study System 启动器

## 文件

- `AgenticStudyLauncher.exe`

## 使用方式

双击 `AgenticStudyLauncher.exe`，默认启动：

```text
http://127.0.0.1:8000
```

命令行指定端口：

```powershell
.\AgenticStudyLauncher.exe --port 8010
```

不自动打开浏览器：

```powershell
.\AgenticStudyLauncher.exe --no-browser
```

## 运行依赖

该启动器使用 Conda 环境：

```text
embedding-env
```

默认查找：

```text
E:\Anaconda\envs\embedding-env\python.exe
```

如果 Python 路径不同，可以设置：

```powershell
$env:AGENTIC_STUDY_PYTHON="完整的 python.exe 路径"
.\AgenticStudyLauncher.exe
```

## 注意

该 exe 是启动器，不会把项目源码、`.env`、课程数据封装进二进制。运行时仍读取当前项目目录下的 `main.py`、`config.yaml`、`.env`、`webapp` 和 `curriculum`，因此后续修改项目文件后无需重新打包。
