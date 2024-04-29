# 异步任务处理库 recoverable-async-task

[中文文档](README_ZH.md) | [English](README.md)

`recoverable-async-task` 是一款Python库，它通过提供一个`RecoverableAsyncTask`类，使得异步任务的处理变得简便，并支持任务的*断点续传功能*。这样，即便在遇到意外失败时，任务也能够恢复并继续执行。

## 快速开始

安装方式如下：

```bash
pip install recoverable-async-task
```

`example.py`是一个简单示例，展示了如何利用`RecoverableAsyncTask`库来处理并发任务并进行断点续传：

```bash
python3 example.py
```

您可能会观察到，即使设置了`retry_n=3`，仍然会有任务因为随机原因失败。在这种情况下，您可以再次直接执行，任务将自动读取checkpoint文件，并从断点继续执行。您可以手动或通过编程方式重复此过程，直到所有任务成功完成。

## 贡献指南

若您希望为`recoverable-async-task`库做出贡献，请按照以下指令进行环境设置：

```bash
source dev-setup.sh
```
