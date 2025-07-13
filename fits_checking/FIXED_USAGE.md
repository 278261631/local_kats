# FITS监控系统 - 修复版使用指南

## 🎉 修复完成

已成功解决以下问题：

### ✅ 1. Unicode编码错误修复
- **问题**: `UnicodeEncodeError: 'gbk' codec can't encode character '\u2717'`
- **解决方案**: 
  - 将特殊Unicode字符（✓、✗、○、△）替换为ASCII字符（[OK]、[POOR]、[GOOD]、[FAIR]）
  - 设置日志文件编码为UTF-8
  - 添加环境变量设置

### ✅ 2. matplotlib图表显示修复
- **问题**: 图表在PyCharm内嵌显示而非独立窗口
- **解决方案**:
  - 强制使用TkAgg后端：`matplotlib.use('TkAgg')`
  - 设置交互模式：`plt.ion()`
  - 优化中文字体设置

## 🚀 快速开始

### 1. 验证修复
```bash
cd fits_checking
python test_fixed.py
```
应该看到所有4项测试通过。

### 2. 运行完整测试（推荐）
```bash
python run_monitor.py --test
```

### 3. 仅运行监控器
```bash
python run_monitor.py
```

### 4. 自定义选项
```bash
# 禁用图表显示（适合服务器环境）
python run_monitor.py --no-plot

# 设置扫描间隔为3秒
python run_monitor.py --interval 3

# 测试模式，无图表，快速扫描
python run_monitor.py --test --no-plot --interval 1
```

## 📊 功能特性

### 已实现的增强功能

1. **慢速测试模式**
   - 文件复制间隔：2.5秒（原0.5秒）
   - 详细进度显示：`[1/总数] 正在复制: filename`
   - 文件大小信息：`[OK] 复制完成 - 大小: 1,234,567 字节`
   - 等待提示：`[WAIT] 等待 2.5 秒...`

2. **实时图表显示**
   - 独立窗口显示（不在PyCharm内嵌）
   - 四个子图：FWHM、椭圆度、源数量、背景RMS
   - 中文标题和标签支持
   - 实时数据更新

3. **数据记录功能**
   - CSV文件：`fits_quality_log.csv`
   - UTF-8编码支持中文路径
   - 完整质量指标记录

4. **质量评估显示**
   - `[OK]` - 优秀
   - `[GOOD]` - 良好  
   - `[FAIR]` - 一般
   - `[POOR]` - 较差
   - `[WARNING]` - 发现问题

## 📁 输出文件

运行后会生成：
- `fits_monitor.log` - 详细日志（UTF-8编码）
- `fits_quality_log.csv` - 质量数据记录
- `config.json` - 配置文件
- `test_log.log` - 测试日志（如果运行了测试）

## 🔧 配置文件

`config.json` 示例：
```json
{
    "monitor_settings": {
        "monitor_directory": "E:/fix_data/debug_fits_output",
        "scan_interval": 5,
        "enable_plotting": true,
        "enable_recording": true
    },
    "test_settings": {
        "source_directory": "E:/fix_data/debug_fits_input",
        "copy_delay": 2.5
    }
}
```

## 🎯 使用场景

### 场景1: 开发测试
```bash
python run_monitor.py --test
```
- 启动监控器和文件复制器
- 实时图表显示
- 完整功能演示

### 场景2: 生产监控
```bash
python run_monitor.py
```
- 仅监控器运行
- 等待真实FITS文件
- 完整分析和记录

### 场景3: 服务器部署
```bash
python run_monitor.py --no-plot --interval 2
```
- 无图形界面
- 快速扫描
- 仅日志和CSV记录

## 📈 质量指标说明

- **FWHM**: 半高全宽，衡量图像锐度
  - [OK]: < 2.0 像素
  - [GOOD]: 2.0-3.0 像素
  - [FAIR]: 3.0-5.0 像素
  - [POOR]: > 5.0 像素

- **椭圆度**: 星像椭圆程度
  - [OK]: < 0.1
  - [GOOD]: 0.1-0.2
  - [FAIR]: 0.2-0.3
  - [POOR]: > 0.3

- **源数量**: 检测到的星点数
  - [OK]: > 50
  - [GOOD]: 10-50
  - [POOR]: < 10

## 🛠️ 故障排除

### 1. 如果仍有编码问题
```bash
# 使用专门的启动脚本
python start_monitor.py --test
```

### 2. 如果图表不显示
- 检查是否安装了tkinter：`python -m tkinter`
- 尝试禁用图表：`--no-plot`

### 3. 如果找不到FITS文件
- 检查配置文件中的路径
- 确保源目录存在且包含.fits文件

## ✅ 验证清单

运行前请确认：
- [ ] Python 3.7+
- [ ] 已安装依赖：`pip install -r requirements.txt`
- [ ] 源目录存在：`E:/fix_data/debug_fits_input`
- [ ] 源目录包含.fits文件
- [ ] 有写入权限到当前目录

## 🎊 完成状态

- ✅ Unicode编码错误已修复
- ✅ matplotlib独立窗口显示已实现
- ✅ 慢速测试模式已优化
- ✅ 实时图表显示正常工作
- ✅ CSV数据记录功能完整
- ✅ 配置管理系统完善
- ✅ 所有测试通过

现在可以安全使用系统进行FITS文件监控和质量评估！
