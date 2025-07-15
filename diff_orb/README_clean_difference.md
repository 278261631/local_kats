# 差异FITS文件清理工具

这个工具集用于进一步处理`compare_aligned_fits.py`输出的`_difference.fits`文件，去除其中的黑色坑和背景亮光，输出更干净的差异FITS文件。

## 文件说明

### 核心文件
- `clean_difference_fits.py` - 核心清理算法实现
- `process_difference_fits.py` - 简化的批量处理工具
- `test_clean_difference.py` - 测试不同参数效果的工具

### 功能特点

1. **高级清理算法**：
   - 动态噪声阈值估计
   - 连通组件分析去除小噪声区域
   - 形态学操作填充黑色坑
   - 中值滤波和高斯平滑
   - 强度阈值过滤

2. **多种配置预设**：
   - `minimal` - 最小清理，保留约1%的像素
   - `ultra_gentle` - 超温和清理，保留约0.16%的像素（**默认配置**）
   - `gentle` - 温和清理，保留约0.02%的像素
   - `default` - 原默认配置，平衡效果，保留约0.01%的像素
   - `strict` - 严格清理，几乎不保留像素

3. **完整输出**：
   - 清理后的FITS文件
   - 对比可视化图像
   - 详细统计报告

## 使用方法

### 1. 处理单个文件

```bash
# 使用默认配置（ultra_gentle）
python process_difference_fits.py --input aligned_comparison_20250715_175203_difference.fits

# 使用原默认配置
python process_difference_fits.py --input difference.fits --config default

# 使用严格清理配置
python process_difference_fits.py --input difference.fits --config strict

# 使用温和清理配置
python process_difference_fits.py --input difference.fits --config gentle

# 使用最小清理配置（保留最多信息）
python process_difference_fits.py --input difference.fits --config minimal

# 指定输出目录
python process_difference_fits.py --input difference.fits --output cleaned_results
```

### 2. 批量处理目录

```bash
# 处理目录中所有_difference.fits文件
python process_difference_fits.py --input-dir aligned_diff_results_20250715_175200

# 使用特定配置批量处理
python process_difference_fits.py --input-dir results_folder --config strict
```

### 3. 测试不同参数效果

```bash
# 运行参数测试，生成对比图
python test_clean_difference.py
```

### 4. 高级自定义参数

```bash
# 直接使用核心工具，自定义所有参数
python clean_difference_fits.py --input difference.fits \
    --noise-percentile 10 \
    --noise-multiplier 5.0 \
    --min-component-size 20 \
    --intensity-threshold 0.08
```

## 配置参数说明

### 预设配置对比

| 参数 | minimal | ultra_gentle | gentle | default | strict |
|------|---------|--------------|--------|---------|--------|
| noise_percentile | 40 | 30 | 20 | 15 | 10 |
| noise_multiplier | 1.5 | 2.0 | 3.0 | 4.0 | 5.0 |
| min_component_size | 1 | 3 | 5 | 10 | 20 |
| intensity_threshold | 0.005 | 0.01 | 0.03 | 0.05 | 0.08 |
| 保留像素比例 | ~1.02% | ~0.16% | ~0.02% | ~0.01% | ~0.00% |

### 参数详解

- **noise_percentile**: 噪声水平百分位数，越小越严格
- **noise_multiplier**: 噪声阈值倍数，越大越严格
- **min_component_size**: 最小连通组件大小，越大越严格
- **intensity_threshold**: 强度阈值（相对于最大值），越大越严格

## 输出文件

处理完成后会生成以下文件：

1. **`*_advanced_cleaned_*.fits`** - 清理后的FITS文件
2. **`*_comparison_*.jpg`** - 对比可视化图像
3. **`*_cleaning_report_*.txt`** - 详细统计报告

## 处理效果示例

以测试文件为例：

```
原始数据统计:
  形状: (3211, 4800)
  非零像素数: 14,905,142
  最大值: 0.977139

清理结果对比:
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ 配置        │ 保留像素    │ 减少比例    │ 最大强度    │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ minimal     │ 152,724     │ 98.98%      │ 0.900499    │
│ ultra_gentle│ 23,918      │ 99.84%      │ 0.891938    │
│ gentle      │ 2,286       │ 99.98%      │ 0.736027    │
│ default     │ 989         │ 99.99%      │ 0.735019    │
│ strict      │ 120         │ 100.00%     │ 0.720911    │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

## 算法流程

1. **加载FITS数据** - 读取原始差异图像
2. **噪声水平估计** - 使用百分位数估计背景噪声
3. **噪声阈值过滤** - 去除低于阈值的像素
4. **强度阈值过滤** - 去除相对强度过低的像素
5. **连通组件分析** - 去除小的噪声区域
6. **形态学操作** - 填充黑色坑，去除小噪声
7. **中值滤波** - 平滑结果
8. **高斯平滑** - 最终平滑处理

## 注意事项

1. **参数选择**：
   - 对于天文图像，建议根据需要选择：
     - `minimal` - 如果需要保留最多的原始信息
     - `ultra_gentle` - 如果需要温和清理但保留较多信息
     - `gentle` - 标准温和清理
     - `default` - 平衡的清理效果
     - `strict` - 仅在需要极度清理时使用

2. **处理时间**：
   - 大图像处理时间较长，请耐心等待
   - 可以先用小图像测试参数效果

3. **结果验证**：
   - 建议查看生成的对比图像验证清理效果
   - 检查统计报告确认像素减少比例合理

4. **文件路径**：
   - Windows系统请使用完整路径或相对路径
   - 避免路径中包含特殊字符

## 故障排除

### 常见问题

1. **"输入文件不存在"**
   - 检查文件路径是否正确
   - 确认文件名拼写无误

2. **"处理失败"**
   - 检查FITS文件是否损坏
   - 查看日志文件了解详细错误

3. **"所有像素都被过滤掉"**
   - 参数过于严格，尝试使用`gentle`配置
   - 或手动调整参数值

4. **处理速度慢**
   - 大图像正常现象
   - 可以调整`morphology_kernel_size`等参数加速

### 获取帮助

```bash
# 查看详细帮助信息
python process_difference_fits.py --help
python clean_difference_fits.py --help
```
