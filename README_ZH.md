# 异步任务处理库 recoverable-async-task

[中文文档](README_ZH.md) | [English](README.md)

`recoverable-async-task` 是一款Python库，它通过提供一个`RecoverableAsyncTask`类，使得异步任务的处理变得简便，并支持任务的*断点续传功能*。这样，即便在遇到意外失败时，任务也能够恢复并继续执行。

## 快速开始

安装方式如下：

```bash
pip install recoverable-async-task
```

下面是一个简单示例，展示了如何利用`RecoverableAsyncTask`库来处理并发任务并进行断点续传：

```python
import asyncio

from recoverable_async_task import RecoverableAsyncTask


async def main():
    async def task(id: int | str):
        import random

        await asyncio.sleep(0.1)

        if random.randint(1, 2) == 1:
            raise Exception(f"Task {id=} failed!")

        return {"id": id, "data": f"Task {id=} finished!"}

    # 创建 RecoverableAsyncTask 实例
    re_async_task = RecoverableAsyncTask(
        task,
        max_workers=10,
        max_qps=10,
        retry_n=3,
        checkpoint_path_name="save-dir/my-example-task",
    )

    # 推送任务以并发处理
    for i in range(100):
        re_async_task.push(i)

    # 收集并打印结果
    async for result in re_async_task.collect_results():
        print(result)


asyncio.run(main())
```

您可能会观察到，即使设置了`retry_n=3`，仍然会有任务因为随机原因失败。在这种情况下，您可以再次直接执行，任务将自动读取checkpoint文件，并从断点继续执行。您可以手动或通过编程方式重复此过程，直到所有任务成功完成。

## 贡献指南

本项目开发推荐使用 [uv](https://docs.astral.sh/uv/#getting-started) 工具管理环境，请先安装 uv，然后执行以下命令：

```bash
uv sync
```

## 计划

[] 支持自定义进度条统计信息
[] 支持传入自定义错误处理逻辑
