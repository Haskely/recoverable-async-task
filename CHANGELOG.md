# Changelog

所有重要的更改都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.2.4] - 2024-03-26

### 改进

- 重构 `RecoverableTask` 类，优化结果生成流程和任务完成状态处理
- 增强错误处理机制，提供更稳定的任务恢复能力
- 优化 GitHub Actions 发布工作流程，提升包发布的自动化程度

## [0.2.3] - 2024-03-25

### 变更

- 移除 `raise_on_error` 参数及相关的错误处理逻辑，简化错误处理方式
- 优化结果存储逻辑：只有当任务结果不为 `None` 时才将结果添加到存储中

## [0.2.2] - 2024-03-22

### 改进

- 为模块和类添加详细的文档字符串，提升代码可读性
- 优化 GitHub Actions 测试工作流程，提升 CI/CD 流程的稳定性和效率

## [0.2.1] - 2024-03-21

### 改进

- 限制 checkpoint 文件名长度最大为 80 字符，超出时会在前面添加"..."，以提高可读性并保持任务存储命名的一致性

## [0.2.0] - 2024-03-20

### 变更

- 将环境管理工具替换为 [uv](https://docs.astral.sh/uv/)
- 重新定义项目范围，专注于提供基于 jsonl 的 checkpoint 功能
- 移除并发控制功能，推荐使用 [adaptio](https://github.com/Haskely/adaptio) 库

### 新增

- 新增 `TaskWrapper` 类用于包装异步任务函数
- 新增 `force_rerun` 参数支持强制重新运行已完成的任务
- 新增任务进度显示，支持显示已完成/总任务数

### 重构

- 移除 `RecoverableAsyncTask` 类，改为提供更简单的 `jsonl_checkpoint` 装饰器
- 优化错误处理机制，支持配置任务失败时是否抛出异常
- 改进代码结构，提升可维护性

## [0.1.0] - 2024-03-10

### 新增

- 发布首个正式版本
- 实现 `RecoverableAsyncTask` 类用于异步任务处理
- 支持任务断点续传功能
- 支持基础的并发控制和重试机制

[0.2.3]: https://github.com/username/recoverable-async-task/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/username/recoverable-async-task/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/username/recoverable-async-task/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/username/recoverable-async-task/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/username/recoverable-async-task/releases/tag/v0.1.0
