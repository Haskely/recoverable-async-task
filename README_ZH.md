# 异步任务处理库 recoverable-async-task

[中文文档](README_ZH.md) | [English](README.md)

`recoverable-async-task` 是一款轻量级Python库，专注于提供基于jsonl的任务断点续传功能。它能够自动记录任务执行状态，使得任务在中断后可以从断点处继续执行，非常适合处理大批量、耗时的异步任务。

## 安装

```bash
pip install recoverable-async-task
```

## 快速开始

下面是一个简单示例，展示了如何使用`make_recoverable`装饰器来处理异步任务：

```python
import asyncio
import random
from recoverable_async_task import make_recoverable


async def main():
    @make_recoverable(
        storage_path_name=".checkpoint/example-task",  # checkpoint文件存储路径
        raise_on_error=False,                         # 任务失败时不抛出异常
        show_progress=True,                           # 显示进度条
        force_rerun=False,                            # 不强制重新运行已完成的任务
    )
    async def task(id: int) -> dict:
        await asyncio.sleep(0.1)
        if random.randint(1, 2) == 1:
            raise Exception(f"Task {id=} failed!")
        return {"id": id, "data": f"Task {id=} finished!"}

    # 执行任务并收集结果
    task_ids = list(range(10))  # 创建10个测试任务
    async for result in task.as_completed(task_ids):
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

## 配置参数说明

`make_recoverable`装饰器支持以下参数：

- `storage_path_name`: str, 可选
  - checkpoint文件的存储路径
  - 默认使用被装饰函数的名称
- `raise_on_error`: bool, 默认True
  - 控制任务失败时是否抛出异常
  - 设为False时会跳过失败的任务继续执行
- `show_progress`: bool, 默认True
  - 是否显示进度条
  - 进度条会显示已完成/总任务数
- `force_rerun`: bool, 默认False
  - 是否强制重新运行已完成的任务
  - 适用于需要重新计算的场景

## 断点续传机制

当任务执行失败时：
1. 成功完成的任务状态会被保存在checkpoint文件中
2. 再次运行程序时，会自动跳过已完成的任务
3. 只会执行之前失败或未执行的任务
4. 这个过程可以重复多次，直到所有任务完成

## 并发控制

本库专注于提供断点续传功能。如果需要更强大的并发控制功能，推荐使用 [adaptio](https://github.com/Haskely/adaptio) 库。

## 开发指南

本项目使用 [uv](https://docs.astral.sh/uv/#getting-started) 进行环境管理：

```bash
# 安装依赖
uv sync

# 运行测试
pytest

# 代码格式化
pre-commit run --all-files
```
