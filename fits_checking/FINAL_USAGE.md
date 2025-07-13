# FITS监控系统 - 最终使用指南

## 🎉 功能分离完成

已成功将图表功能从主监控程序中分离，实现了轻量化的主程序和功能丰富的独立图表查看器。

## 📁 文件结构

```
fits_checking/
├── fits_monitor.py          # 主监控程序（轻量化）
├── plot_viewer.py           # 独立图表查看器 ⭐
├── run_monitor.py           # 启动脚本
├── test_monitor.py          # 慢速测试文件复制器
├── config_loader.py         # 配置管理器
├── demo_separated.py        # 分离功能演示脚本 ⭐
├── test_separated.py        # 分离功能测试脚本 ⭐
├── config.json              # 配置文件
├── requirements.txt         # 依赖包列表
└── fits_quality_log.csv     # 数据记录文件
```

## 🚀 快速开始

### 1. 运行演示
```bash
cd fits_checking
python demo_separated.py
```
这将创建演示数据并展示所有功能。

### 2. 基本使用

#### 启动主监控程序
```bash
# 基本监控模式
python run_monitor.py

# 测试模式（监控器 + 文件复制器）
python run_monitor.py --test

# 自定义扫描间隔
python run_monitor.py --interval 3
```

#### 查看图表（独立运行）
```bash
# 静态图表（推荐）
python plot_viewer.py

# 实时更新图表
python plot_viewer.py --realtime

# 显示统计信息
python plot_viewer.py --stats

# 指定CSV文件
python plot_viewer.py --file custom_data.csv
```

## 📊 图表查看器功能

### 四个子图显示
1. **FWHM (半高全宽)** - 蓝色线条 + 质量阈值线
2. **椭圆度** - 红色线条 + 质量阈值线
3. **检测源数量** - 绿色线条 + 质量阈值线
4. **背景RMS** - 紫色线条

### 三种运行模式
- **静态模式**: 显示所有历史数据
- **实时模式**: 每5秒自动刷新
- **统计模式**: 详细数据分析

### 质量阈值参考线
- FWHM: 优秀(<2.0)、良好(<3.0)、一般(<5.0)
- 椭圆度: 优秀(<0.1)、良好(<0.2)、一般(<0.3)
- 源数量: 充足(>50)、一般(>10)

## 🎯 典型使用场景

### 场景1: 日常监控
```bash
# 终端1: 启动监控器
python run_monitor.py

# 终端2: 需要时查看图表
python plot_viewer.py
```

### 场景2: 实时观测
```bash
# 终端1: 启动测试模式
python run_monitor.py --test

# 终端2: 实时查看图表
python plot_viewer.py --realtime
```

### 场景3: 数据分析
```bash
# 查看统计信息
python plot_viewer.py --stats

# 查看历史趋势
python plot_viewer.py
```

### 场景4: 服务器部署
```bash
# 服务器: 运行监控器（无图形界面）
python run_monitor.py --interval 2

# 本地: 下载CSV文件后查看
python plot_viewer.py --file downloaded_log.csv
```

## 📈 命令行选项

### plot_viewer.py
```bash
python plot_viewer.py [选项]

选项:
  -f, --file FILE       指定CSV数据文件
  -r, --realtime        启用实时更新模式
  -s, --stats           显示数据统计信息
  -i, --interval N      实时更新间隔秒数
  -h, --help           显示帮助信息
```

### run_monitor.py
```bash
python run_monitor.py [选项]

选项:
  --test               运行测试模式
  --no-record          禁用数据记录
  --interval N         设置扫描间隔
  --config FILE        指定配置文件
  -h, --help          显示帮助信息
```

## ✅ 分离后的优势

### 主程序优势
- **轻量化**: 移除matplotlib依赖，启动更快
- **稳定性**: 减少图形界面相关问题
- **服务器友好**: 可在无图形界面环境运行
- **资源节省**: 不占用图形显示资源

### 图表查看器优势
- **按需使用**: 需要时才启动
- **功能丰富**: 静态、实时、统计多种模式
- **数据分析**: 可分析历史数据
- **独立运行**: 不依赖主程序状态

## 🔧 故障排除

### 1. 图表不显示
```bash
# 检查数据文件
python plot_viewer.py --stats

# 检查matplotlib后端
python -c "import matplotlib; print(matplotlib.get_backend())"
```

### 2. 找不到CSV文件
```bash
# 检查文件是否存在
ls -la fits_quality_log.csv

# 指定完整路径
python plot_viewer.py --file /path/to/file.csv
```

### 3. 实时更新不工作
- 确保主监控程序正在运行
- 检查CSV文件是否在更新
- 尝试减少更新间隔

## 📋 测试清单

运行以下命令验证功能：

```bash
# 1. 运行完整测试
python test_separated.py

# 2. 运行演示
python demo_separated.py

# 3. 测试主程序帮助
python run_monitor.py --help

# 4. 测试图表查看器帮助
python plot_viewer.py --help

# 5. 创建测试数据并查看
python demo_separated.py  # 创建数据
python plot_viewer.py --stats  # 查看统计
```

## 🎊 总结

通过功能分离实现了：

1. **主程序轻量化** - 专注核心监控功能
2. **图表功能增强** - 支持多种显示和分析模式
3. **使用更灵活** - 按需启动图表查看器
4. **部署更方便** - 主程序可在服务器环境运行
5. **维护更简单** - 功能模块化，便于开发调试

现在您可以：
- 运行轻量化的监控程序进行文件监控
- 按需使用功能丰富的图表查看器
- 在不同环境中灵活部署
- 独立分析历史数据

**开始使用**: `python fits_checking/demo_separated.py`
