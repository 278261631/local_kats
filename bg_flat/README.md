# FITS文件背景抽取工具

这个工具用于处理天文FITS文件，提取背景并生成背景减除后的图像。

## 功能特性

- 批量处理指定目录下的所有FITS文件
- 使用先进的2D背景估计算法（基于photutils库）
- 输出背景的JPG可视化图像
- 生成背景减除后的FITS文件
- 详细的日志记录和错误处理

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本使用

直接运行脚本，它会处理 `E:\fix_data\star-detect` 目录下的所有FITS文件：

```bash
python extract_background.py
```

### 自定义使用

如果需要处理其他目录或自定义输出位置，可以修改脚本中的 `main()` 函数：

```python
def main():
    input_directory = r"你的FITS文件目录"
    output_directory = r"输出目录"  # 可选，默认在输入目录下创建background_output
    
    extractor = BackgroundExtractor(input_directory, output_directory)
    extractor.process_all_files()
```

## 输出结构

处理完成后，会在输入目录下创建 `background_output` 文件夹，包含：

```
background_output/
├── backgrounds/                 # 背景图像（JPG格式）
│   ├── file1_background.jpg
│   ├── file2_background.jpg
│   └── ...
├── background_subtracted/       # 背景减除后的FITS文件
│   ├── file1_bg_subtracted.fits
│   ├── file2_bg_subtracted.fits
│   └── ...
└── background_extraction.log    # 处理日志
```

## 背景估计方法

### 2D背景估计（推荐）
- 使用photutils库的Background2D类
- 采用SExtractor风格的背景估计算法
- 能够处理复杂的背景变化

### 简单统计方法（备用）
- 当photutils不可用时自动启用
- 使用sigma-clipped统计计算全局背景水平
- 生成常数背景图

## 支持的文件格式

- `.fits`
- `.fit`
- `.fts`
- 对应的大写扩展名

## 日志和错误处理

- 所有处理过程都会记录到 `background_extraction.log` 文件
- 同时在控制台显示处理进度
- 自动跳过无效或损坏的文件
- 详细的错误信息和统计报告

## 注意事项

1. 确保有足够的磁盘空间存储输出文件
2. 大型FITS文件可能需要较长处理时间
3. 建议在处理前备份原始数据
4. 如果内存不足，可以考虑分批处理文件

## 故障排除

### 常见问题

1. **ImportError: No module named 'photutils'**
   - 解决：运行 `pip install photutils`

2. **FileNotFoundError: 输入目录不存在**
   - 检查路径是否正确
   - 确保目录存在且可访问

3. **内存不足**
   - 处理大文件时可能出现
   - 可以修改代码分块处理大图像

### 性能优化

- 对于大量文件，可以考虑并行处理
- 调整 `box_size` 参数来平衡精度和速度
- 使用SSD存储可以提高I/O性能

## 技术细节

### 背景估计算法
- 使用网格化方法将图像分割成小块
- 对每个网格块进行统计分析
- 使用插值方法生成平滑的背景图

### 数据类型处理
- 输入数据转换为float64以保证精度
- 输出FITS文件使用float32节省空间
- 自动处理不同的FITS HDU结构

## 扩展功能

可以根据需要添加以下功能：
- 不同的背景估计算法
- 批量处理的并行化
- GUI界面
- 更多的输出格式支持
