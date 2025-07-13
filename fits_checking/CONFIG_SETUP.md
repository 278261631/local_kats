# 配置文件设置指南

## 📋 配置文件说明

本项目使用 `config.json` 文件来管理系统配置。为了避免提交用户特定的路径和设置，配置文件被添加到了 `.gitignore` 中。

## 🚀 快速设置

### 1. 复制配置模板
```bash
cd fits_checking
cp config.json.template config.json
```

### 2. 编辑配置文件
根据您的环境修改 `config.json` 中的路径和设置：

```json
{
    "monitor_settings": {
        "monitor_directory": "您的监控目录路径",
        "scan_interval": 5,
        "enable_recording": true
    },
    "test_settings": {
        "source_directory": "您的FITS文件源目录",
        "copy_delay": 2.5
    }
}
```

## 📁 重要路径配置

### monitor_directory
- **说明**: 监控器监控的目录
- **示例**: `"E:/fix_data/debug_fits_output"`
- **注意**: 确保目录存在且有读写权限

### source_directory  
- **说明**: 测试时FITS文件的源目录
- **示例**: `"E:/fix_data/debug_fits_input"`
- **注意**: 确保目录存在且包含FITS文件

## ⚙️ 配置项说明

### monitor_settings
- `monitor_directory`: 监控目录路径
- `scan_interval`: 扫描间隔（秒）
- `file_timeout`: 文件超时时间（秒）
- `enable_recording`: 是否启用数据记录

### test_settings
- `source_directory`: 测试文件源目录
- `copy_delay`: 文件复制延迟（秒）
- `show_progress`: 是否显示进度

### plotting_settings
- `max_points`: 图表最大数据点数
- `figure_size`: 图表窗口大小
- `update_interval`: 更新间隔（毫秒）
- `font_family`: 字体族

### recording_settings
- `csv_filename`: CSV数据文件名
- `log_filename`: 日志文件名
- `backup_logs`: 是否备份日志

### quality_thresholds
- `fwhm`: FWHM质量阈值
- `ellipticity`: 椭圆度质量阈值
- `n_sources`: 源数量质量阈值

## 🔧 自动配置

如果没有配置文件，系统会自动创建默认配置：

```bash
# 运行任何程序都会自动创建配置文件
python start.py status
```

## 📝 注意事项

1. **不要提交 config.json**: 该文件包含用户特定路径，已被 .gitignore 忽略
2. **使用模板文件**: 修改 `config.json.template` 作为参考
3. **路径格式**: Windows 使用正斜杠 `/` 或双反斜杠 `\\`
4. **权限检查**: 确保对配置的目录有读写权限

## 🚨 故障排除

### 配置文件不存在
```bash
cp config.json.template config.json
```

### 路径错误
- 检查路径是否存在
- 确保使用正确的路径分隔符
- 检查目录权限

### 编码问题
- 确保配置文件使用 UTF-8 编码
- 避免在路径中使用特殊字符
