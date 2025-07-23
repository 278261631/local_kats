# David Hogg TheThresher

基于David Hogg等人的TheThresher方法的天文图像统计建模和处理实现。

## 🌟 概述

TheThresher是一种先进的"幸运成像"(Lucky Imaging)技术，由David Hogg、J.A. Hitchcock等人开发。该方法通过统计建模和贝叶斯推理从天文图像中提取高质量信息，特别适用于差异图像分析和瞬变源检测。

**参考文献**: Hitchcock et al. (2022), "The Thresher: Lucky imaging without the waste", Monthly Notices of the Royal Astronomical Society, 511, 5372-5384

## 🚀 核心算法

### 统计建模方法
- **泊松-伽马混合模型** - 描述像素强度的统计分布
- **贝叶斯推理** - 通过最大似然估计提取真实信号
- **自适应阈值** - 基于统计显著性的动态阈值设定
- **鲁棒估计** - 对噪声和异常值的鲁棒处理

### 处理流程
1. **背景统计估计** - 多种统计量的鲁棒估计
2. **统计模型拟合** - 泊松-伽马混合模型参数估计
3. **显著性分析** - 创建统计显著性图像
4. **自适应阈值** - 基于统计显著性的检测
5. **形态学处理** - 去除噪声和连接相关区域
6. **源检测** - 连通组件分析和源属性计算

## 📦 安装

### 依赖安装
```bash
cd fits_dia/davidwhogg_thresher
pip install -r requirements.txt
```

### 主要依赖
- `astropy` - 天文学数据处理
- `scipy` - 科学计算和统计分析
- `numpy` - 数值计算
- `opencv-python` - 图像处理
- `matplotlib` - 可视化
- `scikit-learn` - 高级统计分析

## 🎯 使用方法

### 1. 处理指定差异图像
```bash
python run_thresher.py --input aligned_comparison_20250715_175203_difference.fits
```

### 2. 自动处理test_data目录
```bash
python run_thresher.py --auto
```

### 3. 高级参数设置
```bash
python run_thresher.py --input diff.fits --threshold 2.5 --bayesian --output results
```

### 4. 使用简单统计模型
```bash
python run_thresher.py --auto --no-bayesian --threshold 3.0
```

## 📊 参数说明

### 核心参数
- `--input` - 指定输入差异图像文件
- `--auto` - 自动处理test_data目录
- `--threshold` - 统计显著性阈值（默认3.0）
- `--bayesian` - 启用贝叶斯推理（默认）
- `--no-bayesian` - 使用简单统计模型
- `--output` - 指定输出目录

### 算法参数
```python
thresher_params = {
    'gamma_shape': 2.0,          # 伽马分布形状参数
    'gamma_scale': 1.0,          # 伽马分布尺度参数
    'poisson_rate': 1.0,         # 泊松分布率参数
    'convergence_tol': 1e-6,     # 收敛容差
    'max_iterations': 100,       # 最大迭代次数
    'background_percentile': 25, # 背景估计百分位数
}
```

## 📈 输出结果

### 文件输出
```
davidhogg_thresher_YYYYMMDD_HHMMSS_processed.fits     # 处理后图像
davidhogg_thresher_YYYYMMDD_HHMMSS_significance.fits  # 显著性图像
davidhogg_thresher_YYYYMMDD_HHMMSS_sources.txt        # 源目录
davidhogg_thresher_YYYYMMDD_HHMMSS_visualization.png  # 可视化结果
davidhogg_thresher.log                                 # 处理日志
```

### 源目录格式
```
# David Hogg TheThresher Source Catalog
# Columns: ID X Y MAX_SIG MEAN_SIG TOTAL_SIG AREA
   1   123.456   234.567    8.5    6.2   1234.5    45
   2   345.678   456.789    7.3    5.8    987.3    32
```

## 🔬 算法特性

### 贝叶斯模型
- **泊松过程** - 建模光子计数统计
- **伽马先验** - 描述强度分布的先验知识
- **最大似然估计** - 优化模型参数
- **后验推理** - 计算像素显著性

### 统计鲁棒性
- **Sigma-clipped统计** - 去除异常值影响
- **MAD估计** - 鲁棒标准差估计
- **多重统计量** - 偏度、峰度等高阶统计
- **自适应处理** - 根据数据特性调整参数

### 形态学处理
- **开运算** - 去除小噪声点
- **闭运算** - 连接相近区域
- **连通组件分析** - 识别独立源
- **质心计算** - 精确源定位

## 🛠️ 技术实现

### 核心类: DavidHoggThresher
```python
thresher = DavidHoggThresher(
    significance_threshold=3.0,    # 显著性阈值
    use_bayesian_inference=True    # 贝叶斯推理开关
)

result = thresher.process_difference_image(
    fits_path='difference.fits',
    output_dir='results'
)
```

### 统计模型
```python
# 贝叶斯模型
model_params = {
    'type': 'bayesian',
    'gamma_shape': 2.5,
    'gamma_scale': 0.8,
    'poisson_rate': 1.2,
    'log_likelihood': -12345.6
}

# 简单模型
model_params = {
    'type': 'simple',
    'mean': 0.355,
    'std': 0.021,
    'threshold': 0.418
}
```

## 📝 使用示例

### 基本使用
```bash
# 处理差异图像
python run_thresher.py --input aligned_comparison_20250715_175203_difference.fits

# 自动处理
python run_thresher.py --auto --threshold 2.5
```

### 高级使用
```bash
# 贝叶斯推理模式
python run_thresher.py --auto --bayesian --threshold 2.0

# 简单统计模式
python run_thresher.py --auto --no-bayesian --threshold 3.5

# 指定输出目录
python run_thresher.py --input diff.fits --output thresher_results
```

## 🔍 算法优势

### vs 传统方法
1. **统计严格性** - 基于概率模型的严格统计推理
2. **自适应性** - 根据数据特性自动调整参数
3. **鲁棒性** - 对噪声和异常值的强鲁棒性
4. **可解释性** - 提供统计显著性量化

### vs 其他DIA方法
1. **理论基础** - 基于贝叶斯统计理论
2. **参数估计** - 自动估计模型参数
3. **不确定性量化** - 提供检测置信度
4. **计算效率** - 优化的算法实现

## 📚 参考文献

- Hitchcock, J.A., Bramich, D.M., Foreman-Mackey, D., Hogg, D.W., Hundertmark, M. (2022). "The Thresher: Lucky imaging without the waste". Monthly Notices of the Royal Astronomical Society, 511, 5372-5384.
- Hogg, D.W. (2021). "Mapping Stellar Surfaces. I. Degeneracies in the rotational light curve problem"
- Bramich, D.M. (2008). "A new algorithm for difference image analysis"

## 🤝 贡献

欢迎提交问题报告和改进建议。本实现专注于天文学应用的统计建模方法。

## 📄 许可证

本项目遵循开源许可证，用于学术和研究目的。
