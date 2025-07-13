# FITS监控系统 - 分离式图表查看器使用指南

## 🎯 设计理念

将图表功能从主监控程序中分离出来，实现：
- **主程序轻量化**: 监控程序专注于文件监控和数据记录
- **按需图表显示**: 需要时手动运行图表查看器
- **独立数据分析**: 可以随时查看历史数据和统计信息

## 📁 文件结构

```
fits_checking/
├── fits_monitor.py          # 主监控程序（已移除图表功能）
├── plot_viewer.py           # 独立图表查看器 ⭐ 新增
├── run_monitor.py           # 启动脚本（已更新）
├── test_monitor.py          # 测试文件复制器
├── config_loader.py         # 配置管理器
├── config.json              # 配置文件
├── requirements.txt         # 依赖包（已更新）
└── fits_quality_log.csv     # 数据记录文件
```

## 🚀 使用方法

### 1. 启动主监控程序

```bash
# 基本监控模式
python run_monitor.py

# 测试模式（监控器 + 文件复制器）
python run_monitor.py --test

# 自定义扫描间隔
python run_monitor.py --interval 3

# 禁用数据记录（仅监控）
python run_monitor.py --no-record
```

### 2. 查看图表（独立运行）

```bash
# 查看静态图表（推荐）
python plot_viewer.py

# 查看实时更新图表
python plot_viewer.py --realtime

# 显示数据统计信息
python plot_viewer.py --stats

# 指定自定义CSV文件
python plot_viewer.py --file custom_log.csv

# 组合使用
python plot_viewer.py --stats --realtime --interval 3
```

## 📊 图表查看器功能

### 静态图表模式
- 一次性加载所有数据
- 显示完整的历史趋势
- 包含质量阈值参考线
- 适合数据分析和报告

### 实时更新模式
- 每5秒（可配置）自动刷新数据
- 适合监控正在进行的观测
- 可以看到最新的数据变化

### 统计信息模式
- 显示详细的数据统计
- 包含平均值、中位数、标准差等
- 数据范围和分布信息

## 🎨 图表内容

### 四个子图显示：

1. **FWHM (半高全宽)**
   - 蓝色线条，圆点标记
   - 质量阈值线：优秀(<2.0)、良好(<3.0)、一般(<5.0)
   - 衡量图像锐度

2. **椭圆度**
   - 红色线条，圆点标记
   - 质量阈值线：优秀(<0.1)、良好(<0.2)、一般(<0.3)
   - 衡量星像圆度

3. **检测源数量**
   - 绿色线条，圆点标记
   - 质量阈值线：充足(>50)、一般(>10)
   - 衡量图像中星点数量

4. **背景RMS**
   - 紫色线条，圆点标记
   - 衡量背景噪声水平

## 💡 使用场景

### 场景1: 日常监控
```bash
# 终端1: 启动监控器
python run_monitor.py

# 终端2: 需要时查看图表
python plot_viewer.py
```

### 场景2: 测试和调试
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

# 查看历史数据图表
python plot_viewer.py
```

### 场景4: 服务器部署
```bash
# 服务器上运行监控器（无图形界面）
python run_monitor.py --interval 2

# 本地查看数据（下载CSV文件后）
python plot_viewer.py --file downloaded_log.csv
```

## 📈 命令行选项详解

### plot_viewer.py 选项

```bash
python plot_viewer.py [选项]

选项:
  -f, --file FILE       指定CSV数据文件 (默认: fits_quality_log.csv)
  -r, --realtime        启用实时更新模式
  -s, --stats           显示数据统计信息
  -i, --interval N      实时更新间隔秒数 (默认: 5)
  -h, --help           显示帮助信息
```

### run_monitor.py 选项

```bash
python run_monitor.py [选项]

选项:
  --test               运行测试模式（包含文件复制器）
  --no-record          禁用数据记录
  --interval N         设置扫描间隔（秒）
  --config FILE        指定配置文件路径
  -h, --help          显示帮助信息
```

## 🔧 配置文件

`config.json` 中移除了图表相关配置：

```json
{
    "monitor_settings": {
        "monitor_directory": "E:/fix_data/debug_fits_output",
        "scan_interval": 5,
        "enable_recording": true
    },
    "test_settings": {
        "source_directory": "E:/fix_data/debug_fits_input",
        "copy_delay": 2.5
    }
}
```

## 📊 数据文件格式

CSV文件包含以下字段：
- `timestamp`: 时间戳
- `filename`: FITS文件名
- `n_sources`: 检测到的源数量
- `fwhm`: 半高全宽（像素）
- `ellipticity`: 椭圆度
- `lm5sig`: 5σ限制星等
- `background_mean`: 背景均值
- `background_rms`: 背景RMS

## ✅ 优势

### 主程序优势
- **轻量化**: 移除matplotlib依赖，启动更快
- **稳定性**: 减少图形界面相关的潜在问题
- **服务器友好**: 可在无图形界面的服务器上运行
- **资源节省**: 不占用图形显示资源

### 图表查看器优势
- **按需使用**: 需要时才启动，不影响主程序
- **功能丰富**: 静态、实时、统计多种模式
- **数据分析**: 可以分析历史数据
- **独立运行**: 不依赖主程序状态

## 🛠️ 故障排除

### 1. 找不到CSV文件
```bash
# 检查文件是否存在
ls -la fits_quality_log.csv

# 指定完整路径
python plot_viewer.py --file /path/to/fits_quality_log.csv
```

### 2. 图表不显示
```bash
# 检查matplotlib后端
python -c "import matplotlib; print(matplotlib.get_backend())"

# 检查是否有数据
python plot_viewer.py --stats
```

### 3. 实时更新不工作
- 确保主监控程序正在运行
- 检查CSV文件是否在更新
- 尝试减少更新间隔：`--interval 2`

## 🎊 总结

通过分离图表功能：
- ✅ 主监控程序更轻量、更稳定
- ✅ 图表功能更丰富、更灵活
- ✅ 支持多种使用场景
- ✅ 便于部署和维护
- ✅ 数据分析更方便

现在您可以：
1. 运行 `python run_monitor.py --test` 启动监控
2. 运行 `python plot_viewer.py --realtime` 查看实时图表
3. 随时运行 `python plot_viewer.py --stats` 查看统计信息
