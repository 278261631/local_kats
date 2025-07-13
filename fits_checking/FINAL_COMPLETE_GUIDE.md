# FITS监控系统 - 完整使用指南

## 🎉 功能完全模块化完成

经过多轮优化，现在拥有一个完全模块化的FITS监控系统：

### ✅ 解决的问题
1. ✅ **Unicode编码错误** - 替换特殊字符为ASCII
2. ✅ **图表显示问题** - 独立窗口显示，不在PyCharm内嵌
3. ✅ **功能耦合问题** - 完全模块化，各功能独立
4. ✅ **路径问题** - 提供多种启动方式

## 📁 完整文件结构

```
fits_checking/
├── fits_monitor.py          # 核心监控程序
├── run_monitor.py           # 监控器启动脚本（纯净版）
├── plot_viewer.py           # 独立图表查看器
├── test_runner.py           # 独立测试运行器
├── test_monitor.py          # 文件复制器
├── config_loader.py         # 配置管理器
├── fits_launcher.py         # 统一启动器（subprocess方式）
├── start.py                 # 简单启动器（直接导入方式）⭐ 推荐
├── config.json              # 配置文件
├── requirements.txt         # 依赖包列表
└── fits_quality_log.csv     # 数据记录文件
```

## 🚀 推荐使用方式

### 使用简单启动器（推荐，避免路径问题）

```bash
# 检查系统状态
python fits_checking/start.py status

# 启动监控器
python fits_checking/start.py monitor

# 启动图表查看器
python fits_checking/start.py plot

# 启动实时图表
python fits_checking/start.py plot --realtime

# 启动完整测试
python fits_checking/start.py test

# 仅文件复制测试
python fits_checking/start.py test --copy-only

# 仅监控器测试
python fits_checking/start.py test --monitor-only
```

### 直接使用各模块

```bash
# 进入目录
cd fits_checking

# 监控器模块
python run_monitor.py
python run_monitor.py --interval 3 --no-record

# 图表查看器模块
python plot_viewer.py
python plot_viewer.py --realtime --interval 3
python plot_viewer.py --stats

# 测试运行器模块
python test_runner.py
python test_runner.py --copy-only
python test_runner.py --monitor-only
```

## 📊 四个独立模块

### 1. 监控器模块 (run_monitor.py)
- **功能**: 纯粹的文件监控和质量分析
- **特点**: 轻量化，无图表，无测试功能
- **输出**: 日志文件 + CSV数据记录
- **适用**: 生产环境，服务器部署

### 2. 图表查看器模块 (plot_viewer.py)
- **功能**: 数据可视化和统计分析
- **特点**: 从CSV读取数据，独立运行
- **模式**: 静态图表、实时更新、统计信息
- **适用**: 数据分析，结果展示

### 3. 测试运行器模块 (test_runner.py)
- **功能**: 测试功能和文件复制
- **特点**: 独立的测试环境，可选监控器协调
- **模式**: 完整测试、仅复制、仅监控
- **适用**: 系统测试，功能验证

### 4. 启动器模块 (start.py / fits_launcher.py)
- **功能**: 统一的系统入口
- **特点**: 简化使用，状态检查
- **优势**: 避免路径问题，参数传递
- **适用**: 日常使用，系统管理

## 🎯 典型使用场景

### 场景1: 快速测试系统
```bash
# 检查状态
python fits_checking/start.py status

# 运行完整测试
python fits_checking/start.py test

# 查看实时图表
python fits_checking/start.py plot --realtime
```

### 场景2: 生产环境监控
```bash
# 启动纯净监控器
python fits_checking/start.py monitor --interval 2

# 另一个终端查看图表
python fits_checking/start.py plot --realtime
```

### 场景3: 数据分析
```bash
# 查看历史数据统计
python fits_checking/start.py plot --stats

# 查看历史趋势图表
python fits_checking/start.py plot
```

### 场景4: 开发调试
```bash
# 仅测试文件复制功能
python fits_checking/start.py test --copy-only

# 仅测试监控器功能
python fits_checking/start.py test --monitor-only
```

### 场景5: 服务器部署
```bash
# 服务器运行监控器（无图形界面）
cd fits_checking
python run_monitor.py --interval 1

# 本地查看数据（下载CSV后）
python plot_viewer.py --file downloaded_log.csv
```

## 📈 图表功能特性

### 四个子图显示
1. **FWHM (半高全宽)** - 蓝色线条 + 质量阈值线
2. **椭圆度** - 红色线条 + 质量阈值线
3. **检测源数量** - 绿色线条 + 质量阈值线
4. **背景RMS** - 紫色线条

### 质量阈值参考线
- **FWHM**: 优秀(<2.0)、良好(<3.0)、一般(<5.0)
- **椭圆度**: 优秀(<0.1)、良好(<0.2)、一般(<0.3)
- **源数量**: 充足(>50)、一般(>10)

### 三种显示模式
- **静态模式**: 显示所有历史数据
- **实时模式**: 每5秒自动刷新
- **统计模式**: 详细数据分析

## ✅ 模块化优势总结

### 1. 主程序优势
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

### 4. 启动器优势
- **简化**: 统一的使用接口
- **管理**: 集中的状态检查
- **维护**: 便于系统管理
- **用户友好**: 降低使用门槛

## 🔧 故障排除

### 1. 路径问题
```bash
# 使用简单启动器（推荐）
python fits_checking/start.py status

# 或者进入目录后直接运行
cd fits_checking
python run_monitor.py --help
```

### 2. 编码问题
- 所有特殊字符已替换为ASCII
- 日志文件使用UTF-8编码
- 支持中文路径和文件名

### 3. 图表显示问题
- 强制使用TkAgg后端
- 确保在独立窗口显示
- 支持中文标题和标签

### 4. 依赖问题
```bash
# 安装依赖
pip install -r fits_checking/requirements.txt

# 检查依赖
python -c "import matplotlib, pandas, numpy, astropy; print('依赖正常')"
```

## 🎊 最终总结

通过完全模块化实现了：

1. **监控器纯净化** - 专注核心监控功能
2. **图表功能独立** - 按需使用，功能丰富
3. **测试功能分离** - 独立测试环境
4. **统一管理入口** - 简化日常使用
5. **灵活部署方案** - 适应各种场景
6. **问题完全解决** - Unicode、路径、耦合等问题

### 🚀 立即开始使用

```bash
# 1. 检查系统状态
python fits_checking/start.py status

# 2. 运行完整测试
python fits_checking/start.py test

# 3. 查看实时图表
python fits_checking/start.py plot --realtime

# 4. 启动生产监控
python fits_checking/start.py monitor
```

现在您拥有了一个完全模块化、功能完整、问题全部解决的FITS监控系统！🎉
