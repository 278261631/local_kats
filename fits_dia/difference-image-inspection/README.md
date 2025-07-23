# LSST DESC Difference-Image-Inspection

基于LSST DESC (Dark Energy Science Collaboration) 差异图像检查方法的天文图像处理实现。

## 🌟 概述

LSST DESC的Difference-Image-Inspection是为LSST (Legacy Survey of Space and Time) 项目开发的先进差异图像分析方法。该方法结合了多尺度检测、机器学习分类、质量评估和统计验证，专门用于大规模天文巡天中的瞬变源检测和分析。

**核心特性**：
- **多尺度分析** - 在不同空间尺度上检测源
- **智能分类** - 基于形态学特征的源分类
- **质量评估** - 全面的图像质量和检测可靠性评估
- **统计验证** - 基于LSST经验的统计验证框架
- **聚类分析** - 识别相关源群和空间模式

## 🚀 核心算法

### 多尺度检测框架
- **尺度空间分析** - 1.0, 2.0, 4.0, 8.0像素尺度
- **自适应阈值** - 基于局部统计的动态阈值
- **源去混合** - 高级去混合算法分离重叠源
- **形态学分析** - 椭圆度、方向角、浓度指数等

### 智能分类系统
- **瞬变源** - 候选瞬变天体
- **恒星** - 点源特征
- **星系** - 延展源特征
- **宇宙射线** - 尖锐异常特征
- **人工制品** - 仪器或处理产生的假源
- **噪声** - 低信噪比检测

### 质量评估指标
- **信噪比** - 图像整体信噪比
- **动态范围** - 数据动态范围评估
- **对比度** - 图像对比度指标
- **饱和度** - 饱和像素比例
- **坏像素** - 异常像素检测
- **图像熵** - 信息含量评估

## 📦 安装

### 依赖安装
```bash
cd fits_dia/difference-image-inspection
pip install -r requirements.txt
```

### 主要依赖
- `astropy` - 天文学数据处理
- `photutils` - 天文测光和源检测
- `scikit-learn` - 机器学习和聚类
- `opencv-python` - 图像处理
- `matplotlib` - 可视化
- `numpy/scipy` - 科学计算

## 🎯 使用方法

### 1. 处理指定差异图像
```bash
python run_lsst_dia.py --input aligned_comparison_20250715_175203_difference.fits
```

### 2. 自动处理test_data目录
```bash
python run_lsst_dia.py --auto
```

### 3. 高级参数设置
```bash
python run_lsst_dia.py --input diff.fits --threshold 4.0 --output results
```

### 4. 快速模式（禁用质量评估）
```bash
python run_lsst_dia.py --auto --no-quality --threshold 3.0
```

## 📊 参数说明

### 核心参数
- `--input` - 指定输入差异图像文件
- `--auto` - 自动处理test_data目录
- `--threshold` - 检测阈值（默认5.0）
- `--no-quality` - 禁用质量评估以加快处理
- `--output` - 指定输出目录

### 算法参数
```python
lsst_params = {
    'scales': [1.0, 2.0, 4.0, 8.0],     # 多尺度分析的尺度
    'min_area': 5,                       # 最小检测面积
    'deblend_nthresh': 32,              # 去混合阈值数
    'deblend_cont': 0.005,              # 去混合连续性
    'connectivity': 8,                   # 连通性
}
```

## 📈 输出结果

### 文件输出
```
lsst_dia_YYYYMMDD_HHMMSS_sources.txt        # 源目录
lsst_dia_YYYYMMDD_HHMMSS_quality_report.txt # 质量评估报告
lsst_dia_YYYYMMDD_HHMMSS_visualization.png  # 九面板可视化
lsst_dia.log                                 # 处理日志
```

### 源目录格式
```
# Columns: ID SCALE X Y FLUX AREA SNR MAG FWHM ELLIP CLASS CONF RELIABILITY CLUSTER
   1  2.0   123.456   234.567  1.234e-03    45   8.5  22.3   3.2  0.15  transient  0.80     85.2    1
   2  4.0   345.678   456.789  2.345e-03    32   6.2  21.8   4.1  0.25  star       0.75     72.1    0
```

### 质量评估报告
- **图像质量指标** - SNR、动态范围、对比度等
- **统计验证结果** - 源密度、分类分布、警告信息
- **处理参数** - 检测阈值、尺度设置等

## 🔬 算法特性

### 多尺度检测
- **尺度自适应** - 不同尺度捕获不同类型的源
- **高斯卷积** - 平滑处理增强检测稳定性
- **分割算法** - 先进的图像分割技术
- **去混合处理** - 分离重叠和混合源

### 机器学习分类
- **特征工程** - 多维形态学和测光特征
- **规则分类器** - 基于LSST经验的分类规则
- **置信度评估** - 分类结果的置信度量化
- **可靠性评分** - 综合可靠性评估

### 质量控制
- **多层次验证** - 像素、源、图像三个层次
- **统计检验** - 基于天文统计的验证框架
- **异常检测** - 自动识别异常情况
- **警告系统** - 智能警告和建议

## 🛠️ 技术实现

### 核心类: LSSTDifferenceImageInspection
```python
lsst_dia = LSSTDifferenceImageInspection(
    detection_threshold=5.0,    # 检测阈值
    quality_assessment=True     # 质量评估开关
)

result = lsst_dia.process_difference_image(
    fits_path='difference.fits',
    output_dir='results'
)
```

### 处理流程
1. **图像加载** - FITS文件读取和预处理
2. **质量评估** - 全面的图像质量分析
3. **多尺度检测** - 在多个尺度上检测源
4. **源分类** - 基于特征的智能分类
5. **聚类分析** - 空间聚类和模式识别
6. **统计验证** - 结果验证和质量控制
7. **结果输出** - 多格式结果保存

## 📝 使用示例

### 基本使用
```bash
# 处理差异图像
python run_lsst_dia.py --input aligned_comparison_20250715_175203_difference.fits

# 自动处理
python run_lsst_dia.py --auto --threshold 4.0
```

### 高级使用
```bash
# 高精度模式
python run_lsst_dia.py --auto --threshold 3.0

# 快速模式
python run_lsst_dia.py --auto --no-quality --threshold 5.0

# 指定输出目录
python run_lsst_dia.py --input diff.fits --output lsst_results
```

## 🔍 算法优势

### vs 传统DIA方法
1. **多尺度优势** - 捕获不同尺度的天体特征
2. **智能分类** - 自动区分不同类型的源
3. **质量控制** - 全面的质量评估和验证
4. **统计严格** - 基于大样本统计的验证框架

### vs 其他现代方法
1. **LSST优化** - 专门为大规模巡天优化
2. **实时处理** - 适合大数据量实时处理
3. **可扩展性** - 模块化设计易于扩展
4. **标准化** - 遵循天文学界标准

## 📊 性能特点

### 检测能力
- **高灵敏度** - 检测微弱瞬变源
- **低假阳性** - 智能过滤假检测
- **多类型** - 支持各种瞬变源类型
- **大尺度** - 适合大图像处理

### 计算效率
- **并行化** - 支持多尺度并行处理
- **内存优化** - 高效的内存管理
- **可配置** - 灵活的参数配置
- **可扩展** - 支持分布式处理

## 📚 参考文献

- LSST Science Collaborations (2009). "LSST Science Book"
- Ivezić, Ž., et al. (2019). "LSST: From Science Drivers to Reference Design and Anticipated Data Products"
- Jurić, M., et al. (2017). "The LSST Data Management System"
- Bosch, J., et al. (2018). "The Hyper Suprime-Cam Software Pipeline"

## 🤝 贡献

欢迎提交问题报告和改进建议。本实现专注于LSST DESC的差异图像分析方法。

## 📄 许可证

本项目遵循开源许可证，用于学术和研究目的。
