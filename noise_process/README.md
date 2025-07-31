# FITS文件孤立噪点清理工具

这个工具专门用于检测和清理FITS天文图像中的孤立噪点。

## 功能特性

- **智能噪点检测**: 结合统计异常值检测和孤立性分析
- **多种清理方法**: 支持中值滤波、高斯滤波和邻域平均
- **可视化对比**: 自动生成处理前后的对比图
- **详细统计**: 提供完整的处理统计信息
- **灵活配置**: 支持多种参数调整

## 文件说明

- `isolated_noise_cleaner.py` - 主要的噪点清理工具
- `test_noise_cleaner.py` - 测试脚本
- `README.md` - 使用说明

## 快速开始

### 基本使用

```bash
# 处理单个FITS文件（默认输出到程序目录下的noise_cleaned_<文件名>目录）
python isolated_noise_cleaner.py --input image.fits

# 指定输出目录
python isolated_noise_cleaner.py --input image.fits --output ./cleaned/

# 使用不同的清理方法
python isolated_noise_cleaner.py --input image.fits --method gaussian
```

### 参数调整

```bash
# 调整检测敏感度
python isolated_noise_cleaner.py --input image.fits --threshold 5.0

# 调整孤立性检测参数
python isolated_noise_cleaner.py --input image.fits --isolation-radius 2 --min-neighbors 1

# 不保存可视化和掩码
python isolated_noise_cleaner.py --input image.fits --no-visualization --no-mask
```

### 测试工具

```bash
# 运行基本测试
python test_noise_cleaner.py

# 测试不同清理方法
python test_noise_cleaner.py --methods
```

## 算法原理

### 1. 统计异常值检测
- 使用MAD (Median Absolute Deviation) 计算Z-score
- 识别统计上的异常像素
- 默认阈值: 5.0σ

### 2. 孤立性分析
- 检查每个异常像素的邻域
- 计算邻居中异常像素的数量
- 孤立噪点: 邻居数量 < 阈值

### 3. 形态学过滤（可选）
- 使用开运算去除小的噪声团块
- 可通过设置kernel_size=1来跳过

### 4. 噪点清理
- **中值滤波**: 使用邻域中值替换噪点
- **高斯滤波**: 使用高斯平滑后的值替换
- **邻域平均**: 使用非噪点邻居的平均值

## 参数说明

### 检测参数
- `zscore_threshold`: Z-score阈值，越大越严格 (默认: 5.0)
- `isolation_radius`: 孤立性检测半径 (默认: 2)
- `min_neighbors`: 最小邻居数量 (默认: 1)
- `morphology_kernel_size`: 形态学核大小，1表示跳过 (默认: 1)

### 清理参数
- `cleaning_method`: 清理方法 (median/gaussian/mean)
- `median_kernel_size`: 中值滤波核大小 (默认: 3)
- `gaussian_sigma`: 高斯滤波标准差 (默认: 1.0)
- `interpolation_radius`: 插值半径 (默认: 2)

### 输出参数
- `save_visualization`: 保存可视化结果 (默认: True)
- `save_mask`: 保存噪点掩码 (默认: True)

## 输出文件

处理完成后会在输出目录中生成以下文件：

1. `*_cleaned.fits` - 清理后的FITS文件
2. `*_noise_mask.fits` - 噪点掩码文件 (可选)
3. `*_noise_cleaning_comparison.png` - 可视化对比图 (可选)

### 默认输出路径
- 如果不指定`--output`参数，程序会在当前程序所在目录下创建`noise_cleaned_<文件名>`目录
- 例如：处理`image.fits`时，会创建`noise_cleaned_image`目录
- 所有输出文件都会保存在这个目录中

## 使用建议

### 天文图像优化设置
```python
cleaner.clean_params.update({
    'zscore_threshold': 5.0,        # 较高阈值避免误检恒星
    'isolation_radius': 2,          # 小半径检测单像素噪点
    'min_neighbors': 1,             # 低邻居数检测孤立噪点
    'morphology_kernel_size': 1,    # 跳过形态学过滤
    'cleaning_method': 'median',    # 中值滤波保持边缘
    'median_kernel_size': 3,        # 小核保持细节
})
```

### 不同图像类型的建议
- **深空图像**: 使用较高的zscore_threshold (5.0-6.0)
- **行星图像**: 可以使用较低的阈值 (3.0-4.0)
- **高噪声图像**: 增大isolation_radius和min_neighbors
- **低噪声图像**: 减小这些参数以检测更多噪点

## 性能说明

- 处理时间主要取决于图像大小和检测到的异常像素数量
- 孤立性检测是最耗时的步骤
- 大图像建议先裁剪到感兴趣区域

## 注意事项

1. 该工具主要针对**孤立的单像素噪点**，不适合处理大面积噪声
2. 对于包含大量恒星的图像，建议提高zscore_threshold避免误检
3. 处理前建议备份原始文件
4. 可视化图像使用1%-99%百分位数进行显示范围调整

## 示例结果

使用测试文件的处理结果：
- 输入图像: 3211×4800像素 (15,412,800总像素)
- 检测噪点: 8,352个 (0.054%)
- 最大变化: 58,810 ADU
- 平均变化: 1.29 ADU
- 噪点区域平均变化: 2,374.83 ADU

这表明工具成功识别并清理了极值噪点，同时保持了图像的整体完整性。
