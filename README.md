# recoverable-async-task: An Asynchronous Task Processing Library

[中文文档](README_ZH.md) | [English](README.md)

`recoverable-async-task` is a Python library that streamlines the handling of asynchronous tasks through its `RecoverableAsyncTask` class, with the added benefit of **supporting task checkpointing and resumption**. This feature ensures that tasks can pick up from where they left off in the event of unexpected failures.

## Quick Start Guide

To install the library, use the following command:

```bash
pip install recoverable-async-task
```

The following is a simple illustration of how to utilize the `RecoverableAsyncTask` library to manage concurrent tasks and enable checkpointing and resumption:

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

You may notice that even with `retry_n=3` set, some tasks may still fail due to random issues. In such cases, you can simply execute the tasks again, and they will automatically read the checkpoint file and resume from where they were interrupted. You can repeat this process manually or programmatically until all tasks are successfully completed.

## Contributing Guidelines

If you wish to contribute to the `recoverable-async-task` library, please follow the setup instructions below to prepare your development environment:

```bash
source dev-setup.sh
```
