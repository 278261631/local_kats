# FITS监控系统 - 完全模块化版本使用指南

## 🎉 功能完全分离完成

已成功将所有功能模块化，实现了：
- **监控器** - 纯粹的文件监控和质量分析
- **图表查看器** - 独立的数据可视化
- **测试运行器** - 独立的测试功能
- **统一启动器** - 所有模块的统一入口

## 📁 完整文件结构

```
fits_checking/
├── fits_monitor.py          # 核心监控程序
├── run_monitor.py           # 监控器启动脚本（纯净版）
├── plot_viewer.py           # 独立图表查看器
├── test_runner.py           # 独立测试运行器 ⭐ 新增
├── fits_launcher.py         # 统一启动器 ⭐ 新增
├── test_monitor.py          # 文件复制器
├── config_loader.py         # 配置管理器
├── config.json              # 配置文件
├── requirements.txt         # 依赖包列表
└── fits_quality_log.csv     # 数据记录文件
```

## 🚀 使用方法

### 方式1: 使用统一启动器（推荐）

```bash
# 启动监控器
python fits_checking/fits_launcher.py monitor

# 启动图表查看器
python fits_checking/fits_launcher.py plot

# 启动实时图表
python fits_checking/fits_launcher.py plot --realtime

# 启动完整测试
python fits_checking/fits_launcher.py test

# 仅文件复制测试
python fits_checking/fits_launcher.py test --copy-only

# 仅监控器测试
python fits_checking/fits_launcher.py test --monitor-only

# 检查系统状态
python fits_checking/fits_launcher.py status
```

### 方式2: 直接使用各模块

```bash
# 监控器模块
python fits_checking/run_monitor.py
python fits_checking/run_monitor.py --interval 3

# 图表查看器模块
python fits_checking/plot_viewer.py
python fits_checking/plot_viewer.py --realtime
python fits_checking/plot_viewer.py --stats

# 测试运行器模块
python fits_checking/test_runner.py
python fits_checking/test_runner.py --copy-only
python fits_checking/test_runner.py --monitor-only
```

## 📊 模块功能详解

### 1. 监控器模块 (run_monitor.py)
- **功能**: 纯粹的文件监控和质量分析
- **特点**: 轻量化，无图表，无测试功能
- **输出**: 日志文件 + CSV数据记录
- **适用**: 生产环境，服务器部署

```bash
python fits_checking/run_monitor.py --interval 5 --no-record
```

### 2. 图表查看器模块 (plot_viewer.py)
- **功能**: 数据可视化和统计分析
- **特点**: 从CSV读取数据，独立运行
- **模式**: 静态图表、实时更新、统计信息
- **适用**: 数据分析，结果展示

```bash
python fits_checking/plot_viewer.py --realtime --interval 3
```

### 3. 测试运行器模块 (test_runner.py)
- **功能**: 测试功能和文件复制
- **特点**: 独立的测试环境，可选监控器协调
- **模式**: 完整测试、仅复制、仅监控
- **适用**: 系统测试，功能验证

```bash
python fits_checking/test_runner.py --interval 2
```

### 4. 统一启动器 (fits_launcher.py)
- **功能**: 所有模块的统一入口
- **特点**: 子命令方式，参数传递
- **优势**: 简化使用，状态检查
- **适用**: 日常使用，系统管理

```bash
python fits_checking/fits_launcher.py status
```

## 🎯 典型使用场景

### 场景1: 生产环境监控
```bash
# 启动纯净监控器
python fits_checking/fits_launcher.py monitor --interval 2

# 另一个终端查看图表
python fits_checking/fits_launcher.py plot --realtime
```

### 场景2: 系统测试
```bash
# 运行完整测试
python fits_checking/fits_launcher.py test

# 另一个终端查看实时图表
python fits_checking/fits_launcher.py plot --realtime
```

### 场景3: 数据分析
```bash
# 查看历史数据统计
python fits_checking/fits_launcher.py plot --stats

# 查看历史趋势图表
python fits_checking/fits_launcher.py plot
```

### 场景4: 开发调试
```bash
# 仅测试文件复制功能
python fits_checking/fits_launcher.py test --copy-only

# 仅测试监控器功能
python fits_checking/fits_launcher.py test --monitor-only
```

### 场景5: 服务器部署
```bash
# 服务器运行监控器（无图形界面）
python fits_checking/run_monitor.py --interval 1

# 本地查看数据（下载CSV后）
python fits_checking/plot_viewer.py --file downloaded_log.csv
```

## 📈 命令行选项总览

### 统一启动器选项
```bash
python fits_launcher.py <command> [options]

Commands:
  monitor     启动监控器
  plot        启动图表查看器  
  test        启动测试运行器
  status      显示系统状态

Monitor options:
  --no-record          禁用数据记录
  --interval N         扫描间隔
  --config FILE        配置文件

Plot options:
  --file FILE          CSV数据文件
  --realtime           实时更新模式
  --stats              统计信息模式
  --interval N         更新间隔

Test options:
  --copy-only          仅文件复制测试
  --monitor-only       仅监控器测试
  --interval N         扫描间隔
  --config FILE        配置文件
```

## ✅ 模块化优势

### 1. 监控器优势
- **纯净**: 专注核心功能，无冗余代码
- **轻量**: 启动快，资源占用少
- **稳定**: 减少依赖，降低故障风险
- **部署友好**: 适合各种环境

### 2. 图表查看器优势
- **独立**: 不依赖监控器状态
- **灵活**: 支持多种查看模式
- **分析**: 丰富的统计功能
- **历史**: 可分析任意时间段数据

### 3. 测试运行器优势
- **隔离**: 测试功能完全独立
- **可控**: 支持多种测试模式
- **调试**: 便于功能验证
- **开发**: 支持增量测试

### 4. 统一启动器优势
- **简化**: 统一的使用接口
- **管理**: 集中的状态检查
- **维护**: 便于系统管理
- **用户友好**: 降低使用门槛

## 🔧 故障排除

### 1. 检查系统状态
```bash
python fits_checking/fits_launcher.py status
```

### 2. 模块独立测试
```bash
# 测试监控器
python fits_checking/test_runner.py --monitor-only

# 测试文件复制
python fits_checking/test_runner.py --copy-only

# 测试图表显示
python fits_checking/plot_viewer.py --stats
```

### 3. 配置问题
```bash
# 检查配置文件
cat fits_checking/config.json

# 重新生成配置
rm fits_checking/config.json
python fits_checking/run_monitor.py --help  # 会自动创建
```

## 🎊 总结

通过完全模块化实现了：

1. **监控器纯净化** - 专注核心监控功能
2. **图表功能独立** - 按需使用，功能丰富
3. **测试功能分离** - 独立测试环境
4. **统一管理入口** - 简化日常使用
5. **灵活部署方案** - 适应各种场景

### 快速开始
```bash
# 检查状态
python fits_checking/fits_launcher.py status

# 运行测试
python fits_checking/fits_launcher.py test

# 查看图表
python fits_checking/fits_launcher.py plot --realtime

# 启动监控
python fits_checking/fits_launcher.py monitor
```

现在您拥有了一个完全模块化的FITS监控系统！🎉
