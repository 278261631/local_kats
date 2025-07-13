# FITS监控系统快速使用指南

## 🚀 快速开始

### 1. 安装依赖
```bash
cd fits_checking
pip install -r requirements.txt
```

### 2. 基本使用

#### 方式一：使用启动脚本（推荐）
```bash
# 仅运行监控器
python run_monitor.py

# 运行测试模式（监控器 + 慢速文件复制）
python run_monitor.py --test

# 禁用图表显示
python run_monitor.py --no-plot

# 自定义扫描间隔
python run_monitor.py --interval 10
```

#### 方式二：直接运行
```bash
# 运行主监控程序
python fits_monitor.py

# 运行增强测试
python test_enhanced_monitor.py

# 仅运行文件复制测试
python test_monitor.py
```

### 3. 配置文件

编辑 `config.json` 来自定义设置：
```json
{
    "monitor_settings": {
        "monitor_directory": "你的监控目录路径",
        "scan_interval": 5,
        "enable_plotting": true,
        "enable_recording": true
    }
}
```

## 功能特性

### 已实现的增强功能

1. **慢速测试模式**
   - 文件复制间隔从0.5秒增加到2.5秒
   - 详细的进度显示和状态信息
   - 文件大小和时间戳显示

2. **实时图表显示**
   - FWHM变化趋势图
   - 椭圆度变化趋势图
   - 检测源数量变化图
   - 背景RMS变化图
   - 支持中文标题和标签

3. **数据记录功能**
   - 自动保存到CSV文件 (`fits_quality_log.csv`)
   - 包含时间戳、文件名、所有质量指标
   - 详细的日志记录 (`fits_monitor.log`)

4. **配置管理**
   - JSON配置文件支持
   - 命令行参数覆盖
   - 默认配置自动生成

## 📁 输出文件

运行后会生成以下文件：

- `fits_monitor.log` - 详细日志
- `fits_quality_log.csv` - 质量数据记录
- `config.json` - 配置文件（如果不存在会自动创建）

## 🎯 使用场景

### 场景1：实时监控生产环境
```bash
python run_monitor.py
```
适用于：实际的FITS文件生产环境监控

### 场景2：测试和演示
```bash
python run_monitor.py --test
```
适用于：系统测试、功能演示、开发调试

### 场景3：批量分析（无图表）
```bash
python run_monitor.py --no-plot --interval 1
```
适用于：服务器环境、批量处理、性能优先

## 🔧 故障排除

### 常见问题

1. **ImportError: No module named 'matplotlib'**
   ```bash
   pip install matplotlib
   ```

2. **图表窗口不显示**
   - 检查是否在GUI环境中运行
   - 尝试使用 `--no-plot` 参数

3. **找不到FITS文件**
   - 检查配置文件中的目录路径
   - 确保源目录存在且包含.fits文件

4. **权限错误**
   - 确保对监控目录有读写权限
   - 检查CSV文件是否被其他程序占用

## 📈 质量指标说明

- **FWHM**: 半高全宽，衡量图像锐度
- **椭圆度**: 星像的椭圆程度，0为完美圆形
- **源数量**: 检测到的星点数量
- **背景RMS**: 背景噪声水平
- **5σ限制星等**: 5倍信噪比的极限星等

## 🎨 图表说明

实时图表显示四个子图：
- 左上：FWHM趋势（越小越好）
- 右上：椭圆度趋势（越小越好）
- 左下：源数量趋势（适中为好）
- 右下：背景RMS趋势（稳定为好）

## 💡 提示

- 使用 `Ctrl+C` 优雅地停止程序
- CSV文件可以用Excel或其他工具打开分析
- 日志文件包含详细的调试信息
- 配置文件支持热修改（重启后生效）
