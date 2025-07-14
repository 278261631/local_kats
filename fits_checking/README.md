# FITS文件监控和质量评估系统

一个高效的FITS文件实时监控和质量评估系统，使用watchdog事件驱动机制实现实时响应。

## 📁 项目结构

```
fits_checking/
├── fits_monitor.py          # 核心监控程序
├── plot_viewer.py           # 独立图表查看器
├── run_monitor.py           # 监控器启动脚本
├── test_runner.py           # 测试运行器
├── config_loader.py         # 配置管理器
├── config.json              # 配置文件
├── requirements.txt         # 依赖包列表
├── verify_system.py        # 系统验证脚本
├── README.md               # 使用说明（本文件）
└── WATCHDOG_UPGRADE.md     # Watchdog升级文档
```

## 🚀 主要功能

- **实时监控** - 使用watchdog事件驱动，实时响应新FITS文件
- **质量分析** - 自动分析FWHM、椭圆度、源数量等质量指标
- **性能优化** - 中央区域抽取，处理速度提升5-6倍
- **数据记录** - 将分析结果保存到CSV文件
- **图表显示** - 独立的图表查看器，支持静态和实时模式
- **配置管理** - 灵活的配置文件支持

## 📦 安装依赖

```bash
pip install -r requirements.txt
```

## ✅ 系统验证

安装依赖后，运行验证脚本确保系统正常：

```bash
python verify_system.py
```

验证脚本会检查：
- 必需文件是否存在
- 核心模块是否能正常导入
- 命令行帮助是否正常
- 配置文件是否能正确加载
- FITS监控器是否能正常创建

## 🎯 快速开始

### 1. 基本监控
```bash
# 启动监控器（实时响应）
python run_monitor.py

# 查看图表（独立运行）
python plot_viewer.py
```

### 2. 测试模式
```bash
# 默认：仅运行文件复制测试
python test_runner.py

# 完整测试（监控器+文件复制器）
python test_runner.py --full-test
```

## 📋 命令行选项

### 监控器 (run_monitor.py)
```bash
python run_monitor.py [选项]

选项:
  --no-record          禁用数据记录
  --interval N         设置扫描间隔（秒，兼容性参数）
  --config FILE        指定配置文件路径
  -h, --help          显示帮助信息
```

### 图表查看器 (plot_viewer.py)
```bash
python plot_viewer.py [选项]

选项:
  -f, --file FILE      指定CSV数据文件
  -r, --realtime       启用实时更新模式
  -s, --stats          显示数据统计信息
  -i, --interval N     实时更新间隔秒数
  -h, --help          显示帮助信息
```

### 测试运行器 (test_runner.py)
```bash
python test_runner.py [选项]

选项:
  --full-test          运行完整测试（监控器+文件复制器）
  --monitor-only       仅运行监控器测试
  --interval N         设置监控扫描间隔（秒）
  --no-clear           不清理目标目录中现有的FITS文件
  --config FILE        指定配置文件路径
  -h, --help          显示帮助信息

默认行为: 仅运行文件复制测试（相当于之前的--copy-only）
```

## 📊 输出文件

### 数据记录文件
- `fits_quality_log.csv` - 包含以下字段：
  - timestamp: 时间戳
  - filename: 文件名
  - n_sources: 检测到的源数量
  - fwhm: 半高全宽（像素）
  - ellipticity: 椭圆度
  - lm5sig: 5σ限制星等
  - background_mean: 背景均值
  - background_rms: 背景RMS

### 日志文件
- `fits_monitor.log` - 详细的监控和分析日志

## 📈 质量评估标准

| 指标 | 优秀 | 良好 | 一般 | 较差 |
|------|------|------|------|------|
| FWHM (像素) | < 2.0 | 2.0-3.0 | 3.0-5.0 | > 5.0 |
| 椭圆度 | < 0.1 | 0.1-0.2 | 0.2-0.3 | > 0.3 |
| 源数量 | > 50 | 10-50 | < 10 | - |

## 🔧 配置文件

编辑 `config.json` 自定义设置：

```json
{
  "monitor_settings": {
    "monitor_directory": "E:/fix_data/debug_fits_output",
    "scan_interval": 5,
    "enable_recording": true
  },
  "analysis_settings": {
    "use_central_region": true,
    "central_region_size": 200,
    "min_image_size": 300
  },
  "quality_thresholds": {
    "fwhm_excellent": 2.0,
    "fwhm_good": 3.0,
    "fwhm_fair": 5.0,
    "ellipticity_excellent": 0.1,
    "ellipticity_good": 0.2,
    "ellipticity_fair": 0.3,
    "min_sources_good": 10,
    "min_sources_excellent": 50
  }
}
```

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
# 终端1: 启动完整测试（监控器+文件复制器）
python test_runner.py --full-test

# 终端2: 实时查看图表
python plot_viewer.py --realtime
```

### 场景3: 增量测试
```bash
# 不清理现有文件，继续添加新文件（默认仅复制）
python test_runner.py --no-clear

# 完整测试但不清理现有文件
python test_runner.py --full-test --no-clear
```

### 场景4: 数据分析
```bash
# 查看统计信息
python plot_viewer.py --stats

# 分析历史数据
python plot_viewer.py --file old_data.csv
```

## 🧹 测试环境清理

test_runner.py默认会在开始测试前清理目标目录中现有的FITS文件，确保测试环境干净：

```bash
# 默认行为：清理现有FITS文件后开始测试
python test_runner.py

# 保留现有文件，增量添加新文件
python test_runner.py --no-clear
```

**清理功能特点**：
- 🗑️ **自动清理**: 默认清除目标目录中所有.fits文件
- 📁 **递归清理**: 支持清理子目录中的FITS文件
- 🔍 **详细日志**: 显示清理的文件列表
- ⚙️ **可选功能**: 使用--no-clear跳过清理

## ⚡ 性能特点

- **事件驱动**: 使用watchdog库，实时响应文件变化（<100ms）
- **中央区域分析**: 只分析图像中央200×200像素，速度提升5-6倍
- **低资源消耗**: 无需定期轮询，大幅降低CPU和内存使用
- **并发处理**: 多线程处理文件，避免阻塞监控
- **智能等待**: 自动检测文件写入完成

## 🔍 故障排除

### 1. 监控器无响应
```bash
# 检查目录权限
ls -la /path/to/monitor/directory

# 检查watchdog安装
python -c "import watchdog; print('OK')"
```

### 2. 图表不显示
```bash
# 检查数据文件
python plot_viewer.py --stats

# 检查matplotlib后端
python -c "import matplotlib; print(matplotlib.get_backend())"
```

### 3. CSV文件问题
```bash
# 检查文件权限
ls -la fits_quality_log.csv

# 手动指定文件
python plot_viewer.py --file /full/path/to/file.csv
```

## 📝 示例输出

```
======================================================================
    FITS文件监控和质量评估系统 v2.0
    增强版 - 支持实时图表显示和数据记录
======================================================================
2025-07-14 13:40:23 - INFO - 开始监控目录: E:/fix_data/debug_fits_output
2025-07-14 13:40:23 - INFO - 使用watchdog事件驱动监控（实时响应）
2025-07-14 13:40:23 - INFO - 文件监控已启动，等待FITS文件...
2025-07-14 13:40:25 - INFO - 检测到新的FITS文件: test_image_001.fits
2025-07-14 13:40:26 - INFO - 检测到的源数量: 45
2025-07-14 13:40:26 - INFO - FWHM (像素): 2.34
2025-07-14 13:40:26 - INFO - [GOOD] FWHM: 良好 (2.0-3.0 像素)
2025-07-14 13:40:26 - INFO - 数据已记录到CSV: test_image_001.fits
```
