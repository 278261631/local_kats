"""
测试星点检测器的简单脚本
"""

import os
import sys
from star_detector import StarDetector

def test_single_file():
    """测试单个文件的处理"""
    
    # 测试文件路径
    test_file = r"E:\fix_data\star-detect\aligned_comparison_20250715_175203_difference.fits"
    output_dir = "test_output"
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查文件是否存在
    if not os.path.exists(test_file):
        print(f"错误: 测试文件不存在: {test_file}")
        return False
    
    print(f"测试文件: {test_file}")
    
    # 初始化检测器 - 精选模式
    detector = StarDetector(
        min_area=12,            # 较大的最小面积
        max_area=400,           # 适中的最大面积
        threshold_factor=3.5,   # 较高的阈值因子
        min_circularity=0.5,    # 较高的圆度要求
        min_solidity=0.7,       # 较高的实心度要求
        adaptive_threshold=False, # 使用固定阈值
        dark_star_mode=False    # 关闭暗星模式
    )
    
    try:
        # 处理文件
        result = detector.process_fits_file(test_file, output_dir)
        
        if result:
            print(f"✅ 测试成功!")
            print(f"   检测到星点数量: {result['num_stars']}")
            print(f"   输出图像: {result['output_image']}")
            print(f"   图像统计: {result['image_stats']}")
            
            # 显示前几个星点的坐标和形状信息
            if result['stars']:
                print(f"   前5个星点信息:")
                for i, star_data in enumerate(result['stars'][:5]):
                    if len(star_data) == 6:  # 包含形状指标
                        x, y, area, circularity, solidity, aspect_ratio = star_data
                        print(f"     星点{i+1}: ({x}, {y}), 面积={area:.1f}, 圆度={circularity:.3f}, 实心度={solidity:.3f}")
                    else:  # 兼容旧格式
                        x, y, area = star_data[:3]
                        print(f"     星点{i+1}: ({x}, {y}), 面积={area:.1f}")
            
            return True
        else:
            print("❌ 测试失败: 无法处理文件")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def check_dependencies():
    """检查依赖包是否正确安装"""
    print("检查依赖包...")
    
    try:
        import numpy
        print(f"✅ numpy: {numpy.__version__}")
    except ImportError:
        print("❌ numpy 未安装")
        return False
    
    try:
        import cv2
        print(f"✅ opencv-python: {cv2.__version__}")
    except ImportError:
        print("❌ opencv-python 未安装")
        return False
    
    try:
        import astropy
        print(f"✅ astropy: {astropy.__version__}")
    except ImportError:
        print("❌ astropy 未安装")
        return False
    
    try:
        import matplotlib
        print(f"✅ matplotlib: {matplotlib.__version__}")
    except ImportError:
        print("❌ matplotlib 未安装")
        return False
    
    return True

if __name__ == "__main__":
    print("星点检测器测试程序")
    print("=" * 40)
    
    # 检查依赖
    if not check_dependencies():
        print("\n请先安装依赖包: pip install -r requirements.txt")
        sys.exit(1)
    
    print("\n开始测试...")
    
    # 测试单个文件
    success = test_single_file()
    
    if success:
        print("\n🎉 所有测试通过! 可以运行主程序了。")
        print("运行命令: python detect_stars.py")
    else:
        print("\n❌ 测试失败，请检查错误信息。")
