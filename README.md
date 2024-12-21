# recoverable-async-task

[English](README.md) | [中文文档](README_ZH.md)

`recoverable-async-task` is a lightweight Python library that focuses on providing JSONL-based checkpoint recovery functionality for async tasks. It automatically records task execution states, allowing tasks to resume from where they left off after interruption, making it ideal for handling large-scale, time-consuming asynchronous tasks.

## Installation

```bash
pip install recoverable-async-task
```

## Quick Start

Here's a simple example demonstrating how to use the `make_recoverable` decorator to handle async tasks:

```python
import asyncio
import random
from recoverable_async_task import make_recoverable


async def main():
    @make_recoverable(
        storage_path_name=".checkpoint/example-task",  # Checkpoint file storage path
        raise_on_error=False,                         # Don't raise exceptions on task failure
        show_progress=True,                           # Show progress bar
        force_rerun=False,                            # Don't force rerun completed tasks
    )
    async def task(id: int) -> dict:
        await asyncio.sleep(0.1)
        if random.randint(1, 2) == 1:
            raise Exception(f"Task {id=} failed!")
        return {"id": id, "data": f"Task {id=} finished!"}

    # Execute tasks and collect results
    task_ids = list(range(10))  # Create 10 test tasks
    async for result in task.as_completed(task_ids):
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration Parameters

The `make_recoverable` decorator supports the following parameters:

- `storage_path_name`: str, optional
  - Storage path for checkpoint files
  - Defaults to the decorated function's name
- `raise_on_error`: bool, defaults to True
  - Controls whether to raise exceptions on task failure
  - When False, skips failed tasks and continues execution
- `show_progress`: bool, defaults to True
  - Whether to display a progress bar
  - Shows completed/total tasks count
- `force_rerun`: bool, defaults to False
  - Whether to force rerun completed tasks
  - Useful for scenarios requiring recalculation

## Checkpoint Recovery Mechanism

When task execution fails:
1. Successfully completed task states are saved in the checkpoint file
2. When rerunning the program, completed tasks are automatically skipped
3. Only previously failed or unexecuted tasks will be processed
4. This process can be repeated until all tasks are completed

## Concurrency Control

This library focuses on providing checkpoint recovery functionality. For more powerful concurrency control features, we recommend using the [adaptio](https://github.com/Haskely/adaptio) library.

## Development Guide

This project uses [uv](https://docs.astral.sh/uv/#getting-started) for environment management:

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Format code
pre-commit run --all-files
```
