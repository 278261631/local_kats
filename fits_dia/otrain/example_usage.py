#!/usr/bin/env python3
"""
O'TRAIN处理工具使用示例
"""

import os
import sys
from process_difference_with_otrain import OTrainProcessor

def example_usage():
    """
    展示O'TRAIN处理工具的完整使用流程
    """
    print("="*60)
    print("O'TRAIN处理工具使用示例")
    print("="*60)
    
    # 示例文件路径
    test_fits_file = "../test_data/aligned_comparison_20250715_175203_difference.fits"
    output_directory = "example_results"
    
    # 检查测试文件是否存在
    if not os.path.exists(test_fits_file):
        print(f"❌ 测试文件不存在: {test_fits_file}")
        print("请确保测试数据文件存在")
        return False
    
    try:
        print(f"📁 输入文件: {test_fits_file}")
        print(f"📁 输出目录: {output_directory}")
        print()
        
        # 1. 创建O'TRAIN处理器
        print("🔧 创建O'TRAIN处理器...")
        processor = OTrainProcessor(output_dir=output_directory)
        
        # 2. 设置处理参数 (使用默认的高灵敏度设置)
        print("⚙️ 设置处理参数...")
        # 注意：这些是默认值，已经优化为高灵敏度检测
        processor.cutout_size = 32          # Cutout大小
        processor.detection_threshold = 2.5  # 检测阈值 (更低=更敏感)
        processor.min_area = 3              # 最小区域面积 (更低=检测更小目标)

        print(f"   - Cutout大小: {processor.cutout_size}x{processor.cutout_size} 像素")
        print(f"   - 检测阈值: {processor.detection_threshold} σ (高灵敏度)")
        print(f"   - 最小区域: {processor.min_area} 像素 (检测小目标)")
        print()
        
        # 3. 处理FITS文件
        print("🚀 开始处理FITS文件...")
        result = processor.process_fits_file(test_fits_file)
        
        if result:
            print()
            print("✅ 处理完成!")
            print(f"📊 检测结果:")
            print(f"   - 候选天体总数: {result['candidates']}")
            print(f"   - 真实瞬变天体: {result['real_transients']}")
            print(f"   - 虚假检测: {result['candidates'] - result['real_transients']}")
            print(f"   - 真实率: {result['real_transients']/result['candidates']*100:.1f}%")
            print()
            
            # 4. 检查输出文件
            print("📄 生成的输出文件:")
            if os.path.exists(output_directory):
                output_files = os.listdir(output_directory)
                for i, file in enumerate(output_files, 1):
                    file_path = os.path.join(output_directory, file)
                    file_size = os.path.getsize(file_path) / (1024*1024)  # MB
                    
                    if file.endswith('.txt'):
                        print(f"   {i}. 📝 {file} ({file_size:.2f} MB)")
                        print(f"      → 详细分析结果和统计信息")
                    elif file.endswith('.png'):
                        print(f"   {i}. 🖼️ {file} ({file_size:.2f} MB)")
                        print(f"      → 可视化分析图表")
                    elif file.endswith('.fits'):
                        print(f"   {i}. 🔬 {file} ({file_size:.2f} MB)")
                        print(f"      → 带圆圈标记的FITS文件")
            print()
            
            # 5. 使用建议
            print("💡 使用建议:")
            print("   1. 查看文本结果文件了解详细的候选天体信息")
            print("   2. 打开可视化图像查看检测结果的直观展示")
            print("   3. 使用带标记的FITS文件进行进一步分析")
            print("   4. 可以使用verify_marked_fits.py验证标记结果")
            print()
            
            # 6. 验证示例
            print("🔍 验证标记结果 (可选):")
            marked_fits = None
            for file in os.listdir(output_directory):
                if file.endswith('_marked_*.fits'):
                    marked_fits = os.path.join(output_directory, file)
                    break
            
            if marked_fits:
                print(f"   python verify_marked_fits.py {test_fits_file} {marked_fits}")
            print()
            
            return True
            
        else:
            print("❌ 处理失败!")
            return False
            
    except Exception as e:
        print(f"❌ 处理过程中出错: {str(e)}")
        return False

def show_parameter_effects():
    """
    展示不同参数对处理结果的影响
    """
    print("="*60)
    print("参数调整示例")
    print("="*60)
    
    test_fits_file = "../test_data/aligned_comparison_20250715_175203_difference.fits"
    
    if not os.path.exists(test_fits_file):
        print("❌ 测试文件不存在，跳过参数示例")
        return
    
    # 不同参数组合
    parameter_sets = [
        {"threshold": 2.0, "min_area": 2, "desc": "极高灵敏度 (最多候选)"},
        {"threshold": 2.5, "min_area": 3, "desc": "高灵敏度检测 (默认)"},
        {"threshold": 3.0, "min_area": 5, "desc": "标准检测 (平衡)"},
        {"threshold": 4.0, "min_area": 10, "desc": "保守检测 (更少候选)"}
    ]
    
    print("🔬 不同参数设置的效果对比:")
    print()
    
    for i, params in enumerate(parameter_sets, 1):
        print(f"{i}. {params['desc']}")
        print(f"   - 检测阈值: {params['threshold']} σ")
        print(f"   - 最小区域: {params['min_area']} 像素")
        
        try:
            processor = OTrainProcessor(output_dir=f"param_test_{i}")
            processor.detection_threshold = params['threshold']
            processor.min_area = params['min_area']
            
            # 只进行检测，不保存完整结果
            image_data, header, success = processor.load_fits_image(test_fits_file)
            if success:
                candidates = processor.detect_candidates(image_data)
                print(f"   → 检测到 {len(candidates)} 个候选天体")
            else:
                print("   → 检测失败")
        except Exception as e:
            print(f"   → 错误: {str(e)}")
        
        print()

def main():
    """主函数"""
    print("🌟 O'TRAIN处理工具示例程序")
    print()
    
    # 基本使用示例
    success = example_usage()
    
    if success:
        print("="*60)
        
        # 参数效果示例
        show_parameter_effects()
        
        print("="*60)
        print("🎉 示例程序运行完成!")
        print()
        print("📚 更多信息:")
        print("   - 查看 README.md 了解详细使用说明")
        print("   - 运行 python process_difference_with_otrain.py --help 查看所有参数")
        print("   - 使用 python test_otrain_processor.py 运行完整测试")
        print()
    else:
        print("❌ 示例程序运行失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
