# O'TRAIN FITS差异图像处理工具

基于dcorre/otrain项目的FITS差异图像瞬变天体检测工具。

## 项目简介

O'TRAIN (Optical TRAnsient Identification NEtwork) 是一个基于卷积神经网络(CNN)的天文瞬变天体识别工具。本工具实现了O'TRAIN方法来处理FITS差异图像，用于检测和分类潜在的瞬变天体。

## 参考项目

- 原始项目: https://github.com/dcorre/otrain
- 论文: "O'TRAIN: A robust and flexible 'real or bogus' classifier for the study of the optical transient sky"
- 文档: https://otrain.readthedocs.io

## 功能特点

- **候选天体检测**: 使用阈值检测方法识别差异图像中的候选天体
- **Cutout提取**: 提取标准大小(32x32像素)的候选天体图像块
- **CNN分类**: 模拟CNN分类过程，区分真实瞬变天体和虚假检测
- **结果可视化**: 生成详细的分析结果图表
- **结果保存**: 保存文本格式的详细分析结果
- **标记FITS输出**: 生成带有圆圈标记的FITS文件，标记大小根据候选天体像素数自动调整

## 安装依赖

```bash
cd fits_dia/otrain
pip install -r requirements.txt
```

## 使用方法

### 基本用法

```bash
python process_difference_with_otrain.py /path/to/difference.fits
```

### 高级用法

```bash
python process_difference_with_otrain.py /path/to/difference.fits \
    --output-dir results \
    --cutout-size 32 \
    --threshold 2.5 \
    --min-area 3
```

### 处理测试数据

```bash
python process_difference_with_otrain.py ../test_data/aligned_comparison_20250715_175203_difference.fits
```

## 参数说明

- `fits_file`: 输入的FITS差异图像文件路径
- `--output-dir, -o`: 输出目录路径 (默认: otrain_results)
- `--cutout-size`: Cutout图像大小 (默认: 32像素)
- `--threshold`: 检测阈值倍数 (默认: 2.5, 更低=更敏感)
- `--min-area`: 最小连通区域面积 (默认: 3像素, 更低=检测更小目标)

## 输出文件

处理完成后会在输出目录中生成以下文件:

1. **结果文本文件**: `*_otrain_results_*.txt`
   - 包含所有候选天体的详细信息
   - 分类结果和得分
   - 统计摘要

2. **可视化图像**: `*_otrain_visualization_*.png`
   - 原始差异图像
   - 标记的候选天体位置
   - 真实瞬变天体标注
   - 分类得分分布直方图

3. **带标记的FITS文件**: `*_otrain_marked_*.fits`
   - 基于原始差异图像数据
   - 用圆圈标记所有候选天体位置
   - 标记大小根据候选天体像素数自动调整
   - 真实瞬变天体使用更强的标记强度
   - 包含O'TRAIN处理信息的FITS头

## 检测灵敏度调整

工具默认使用高灵敏度设置以检测更多候选天体：

### 默认参数 (高灵敏度)
- **检测阈值**: 2.5σ (相比标准3.0σ更敏感)
- **最小区域**: 3像素 (相比标准5像素检测更小目标)

### 参数调整建议
```bash
# 极高灵敏度 (可能产生更多虚假检测)
--threshold 2.0 --min-area 2

# 高灵敏度 (默认，推荐)
--threshold 2.5 --min-area 3

# 标准灵敏度 (平衡)
--threshold 3.0 --min-area 5

# 保守检测 (减少虚假检测)
--threshold 4.0 --min-area 10
```

## 处理流程

1. **加载FITS文件**: 读取差异图像数据和头信息
2. **候选检测**: 使用高灵敏度阈值方法检测候选天体
3. **Cutout提取**: 提取32x32像素的候选天体图像块
4. **CNN分类**: 模拟CNN分类过程(实际使用需要训练好的模型)
5. **结果输出**: 保存分析结果、可视化图像和带标记的FITS文件

## 注意事项

### 关于CNN模型

当前实现使用模拟的分类逻辑作为示例。在实际使用中，需要:

1. 安装完整的O'TRAIN包
2. 使用训练好的CNN模型
3. 或者训练自己的模型

### 模型训练

要训练自己的CNN模型，需要:

1. 收集真实和虚假瞬变天体的cutout样本
2. 使用O'TRAIN框架进行模型训练
3. 将训练好的模型集成到本工具中

## 示例输出

```
O'TRAIN处理完成
候选天体: 15
真实瞬变天体: 3
结果已保存到: otrain_results
```

## 技术细节

- **检测方法**: 基于统计阈值的连通区域检测
- **Cutout标准**: 32x32像素，与O'TRAIN标准一致
- **分类模拟**: 使用启发式规则模拟CNN分类
- **可视化**: 多面板显示，包含原图、标注和统计

## 验证工具

项目还包含一个验证工具 `verify_marked_fits.py` 用于验证带标记的FITS文件:

```bash
python verify_marked_fits.py original.fits marked.fits --output-dir verification_results
```

验证工具功能:
- 对比原始和标记FITS文件
- 生成验证可视化图像
- 输出详细的验证报告
- 统计标记信息和像素分布

## 扩展功能

可以通过以下方式扩展功能:

1. 集成真实的CNN模型
2. 添加更多的特征提取方法
3. 实现批量处理功能
4. 添加更多的可视化选项
5. 支持不同的标记样式和颜色

## 故障排除

### 常见问题

1. **依赖包缺失**: 确保安装了所有必需的Python包
2. **FITS文件格式**: 确保输入文件是有效的FITS格式
3. **内存不足**: 对于大图像，可能需要更多内存

### 调试模式

可以通过修改日志级别来获取更详细的调试信息:

```python
logging.basicConfig(level=logging.DEBUG)
```

## 贡献

欢迎提交问题报告和改进建议。

## 许可证

本工具基于O'TRAIN项目开发，请遵循相应的开源许可证。
