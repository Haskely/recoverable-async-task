# recoverable-async-task: An Asynchronous Task Processing Library

[中文文档](README_ZH.md) | [English](README.md)

`recoverable-async-task` is a Python library that streamlines the handling of asynchronous tasks through its `RecoverableAsyncTask` class, with the added benefit of **supporting task checkpointing and resumption**. This feature ensures that tasks can pick up from where they left off in the event of unexpected failures.

## Quick Start Guide

To install the library, use the following command:

```bash
pip install recoverable-async-task
```

The `example.py` file provides a simple illustration of how to utilize the `RecoverableAsyncTask` library to manage concurrent tasks and enable checkpointing and resumption:

```bash
python3 example.py
```

You may notice that even with `retry_n=3` set, some tasks may still fail due to random issues. In such cases, you can simply execute the tasks again, and they will automatically read the checkpoint file and resume from where they were interrupted. You can repeat this process manually or programmatically until all tasks are successfully completed.

## Contributing Guidelines

If you wish to contribute to the `recoverable-async-task` library, please follow the setup instructions below to prepare your development environment:

```bash
source dev-setup.sh
```
