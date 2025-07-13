# FITS文件监控和质量评估系统

## 功能概述

这是一个增强版的FITS文件监控系统，具有以下主要功能：

1. **实时监控** - 监控指定目录中新创建的FITS文件
2. **质量分析** - 自动分析FITS图像质量指标（FWHM、椭圆度、源数量等）
3. **实时图表显示** - 实时显示质量指标的变化趋势
4. **数据记录** - 将分析结果保存到CSV文件
5. **慢速测试模式** - 支持慢速文件复制以便观察实时效果

## 主要组件

### 1. 核心模块

- `fits_monitor.py` - 主监控程序
- `test_monitor.py` - 慢速测试文件复制器
- `test_enhanced_monitor.py` - 增强功能测试脚本

### 2. 主要类

- `FITSQualityAnalyzer` - FITS图像质量分析器
- `FITSFileMonitor` - 文件监控器
- `RealTimePlotter` - 实时图表显示器
- `DataRecorder` - 数据记录器

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本使用

```python
from fits_monitor import FITSFileMonitor

# 创建监控器
monitor = FITSFileMonitor(
    monitor_directory="E:/fix_data/debug_fits_output",
    enable_plotting=True,   # 启用实时图表
    enable_recording=True   # 启用数据记录
)

# 开始监控
monitor.start_monitoring(scan_interval=5)
```

### 运行完整测试

```bash
python test_enhanced_monitor.py
```

这将启动：
- 监控器线程：监控新的FITS文件并分析
- 文件复制器线程：慢速复制FITS文件到监控目录（2.5秒间隔）

## 输出文件

### 1. 日志文件
- `fits_monitor.log` - 详细的监控和分析日志

### 2. 数据记录文件
- `fits_quality_log.csv` - 包含以下字段的CSV文件：
  - timestamp: 时间戳
  - filename: 文件名
  - n_sources: 检测到的源数量
  - fwhm: 半高全宽（像素）
  - ellipticity: 椭圆度
  - lm5sig: 5σ限制星等
  - background_mean: 背景均值
  - background_rms: 背景RMS

### 3. 实时图表
显示四个子图：
- FWHM变化趋势
- 椭圆度变化趋势
- 检测源数量变化
- 背景RMS变化

## 质量评估标准

### FWHM评估
- 优秀: < 2.0 像素
- 良好: 2.0-3.0 像素
- 一般: 3.0-5.0 像素
- 较差: > 5.0 像素

### 椭圆度评估
- 优秀: < 0.1
- 良好: 0.1-0.2
- 一般: 0.2-0.3
- 较差: > 0.3

### 源数量评估
- 充足: > 50
- 一般: 10-50
- 较少: < 10

## 配置选项

### 监控器参数
- `monitor_directory`: 监控目录路径
- `enable_plotting`: 是否启用实时图表显示
- `enable_recording`: 是否启用数据记录
- `scan_interval`: 扫描间隔（秒）

### 图表参数
- `max_points`: 图表显示的最大数据点数（默认50）

## 注意事项

1. **依赖要求**: 需要安装matplotlib用于图表显示
2. **性能考虑**: 实时图表会消耗一定的系统资源
3. **文件路径**: 确保监控目录路径正确且有读写权限
4. **中文显示**: 图表支持中文标题和标签

## 故障排除

### 常见问题

1. **图表不显示**
   - 检查matplotlib是否正确安装
   - 确保系统支持GUI显示

2. **CSV文件写入失败**
   - 检查目录写入权限
   - 确保文件未被其他程序占用

3. **FITS文件分析失败**
   - 检查FITS文件格式是否正确
   - 确保astropy和sep库正确安装

## 示例输出

```
2024-01-15 10:30:15 - INFO - 开始监控目录: E:\fix_data\debug_fits_output
2024-01-15 10:30:15 - INFO - 实时图表显示已启用
2024-01-15 10:30:15 - INFO - 数据记录功能已启用
2024-01-15 10:30:20 - INFO - 检测到新的FITS文件: test_image_001.fits
2024-01-15 10:30:21 - INFO - 检测到的源数量: 45
2024-01-15 10:30:21 - INFO - FWHM (像素): 2.34
2024-01-15 10:30:21 - INFO - 椭圆度: 0.15
2024-01-15 10:30:21 - INFO - ✓ FWHM: 良好 (2.0-3.0 像素)
2024-01-15 10:30:21 - INFO - ○ 椭圆度: 良好 (0.1-0.2)
2024-01-15 10:30:21 - INFO - 数据已记录到CSV: test_image_001.fits
```
