#!/usr/bin/env python3
"""
对比不同图像对齐方法的效果
展示刚体变换、相似变换和单应性变换的差异
"""

import os
import sys
from datetime import datetime
from fits_alignment_comparison import FITSAlignmentComparison

def compare_alignment_methods(fits_dir):
    """
    对比不同对齐方法的效果
    
    Args:
        fits_dir (str): 包含FITS文件的目录
    """
    # 设置文件路径
    fits1 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250622_182433_-14.9C_.fit")
    fits2 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250628_193509_-14.9C_.fit")
    
    # 检查文件是否存在
    if not os.path.exists(fits1) or not os.path.exists(fits2):
        print("错误: FITS文件不存在")
        return
    
    # 定义对齐方法
    alignment_methods = [
        {'method': 'rigid', 'name': '刚体变换', 'description': '仅平移和旋转，保持形状不变'},
        {'method': 'similarity', 'name': '相似变换', 'description': '平移、旋转和等比缩放'},
        {'method': 'homography', 'name': '单应性变换', 'description': '包含透视变形'}
    ]
    
    results = []
    
    print("=" * 80)
    print("FITS图像对齐方法对比测试")
    print("=" * 80)
    print(f"参考图像: {os.path.basename(fits1)}")
    print(f"比较图像: {os.path.basename(fits2)}")
    print("=" * 80)
    
    for method_info in alignment_methods:
        method = method_info['method']
        name = method_info['name']
        description = method_info['description']
        
        print(f"\n正在测试: {name} ({description})")
        print("-" * 60)
        
        try:
            # 创建比较系统
            comparator = FITSAlignmentComparison(
                use_central_region=True,
                central_region_size=200,
                alignment_method=method
            )
            
            # 执行比较（不显示可视化以节省时间）
            result = comparator.process_fits_comparison(
                fits1, 
                fits2, 
                output_dir=f"alignment_comparison_{method}",
                show_visualization=False
            )
            
            if result:
                results.append({
                    'method': method,
                    'name': name,
                    'description': description,
                    'alignment_success': result['alignment_success'],
                    'features_detected': result['features_detected'],
                    'new_bright_spots': result['new_bright_spots'],
                    'processing_time': result['processing_time']
                })
                
                print(f"✅ {name} 完成")
                print(f"   对齐成功: {'是' if result['alignment_success'] else '否'}")
                print(f"   特征匹配: {result['features_detected']['matches']} 个")
                print(f"   新亮点: {result['new_bright_spots']} 个")
            else:
                print(f"❌ {name} 失败")
                
        except Exception as e:
            print(f"❌ {name} 出错: {str(e)}")
    
    # 生成对比报告
    print("\n" + "=" * 80)
    print("对比结果总结")
    print("=" * 80)
    
    if results:
        print(f"{'方法':<12} {'对齐':<6} {'匹配点':<8} {'新亮点':<8} {'描述'}")
        print("-" * 80)
        
        for result in results:
            alignment_status = "成功" if result['alignment_success'] else "失败"
            matches = result['features_detected']['matches']
            bright_spots = result['new_bright_spots']
            
            print(f"{result['name']:<12} {alignment_status:<6} {matches:<8} {bright_spots:<8} {result['description']}")
        
        # 推荐建议
        print("\n" + "=" * 80)
        print("推荐建议")
        print("=" * 80)
        print("🌟 对于天文图像，推荐使用顺序：")
        print("   1. 刚体变换 (rigid) - 最适合天文图像，保持形状不变")
        print("   2. 相似变换 (similarity) - 允许等比缩放，适合不同焦距的图像")
        print("   3. 单应性变换 (homography) - 可能产生透视变形，不推荐")
        
        print("\n💡 选择建议：")
        print("   - 如果图像来自同一台望远镜的不同时间观测 → 使用刚体变换")
        print("   - 如果图像来自不同设备或焦距设置 → 使用相似变换")
        print("   - 如果前两种方法都失败 → 可尝试单应性变换")
        
        # 找出最佳方法
        rigid_result = next((r for r in results if r['method'] == 'rigid'), None)
        if rigid_result and rigid_result['alignment_success']:
            print(f"\n✅ 推荐使用刚体变换，检测到 {rigid_result['new_bright_spots']} 个新亮点")
        else:
            similarity_result = next((r for r in results if r['method'] == 'similarity'), None)
            if similarity_result and similarity_result['alignment_success']:
                print(f"\n✅ 推荐使用相似变换，检测到 {similarity_result['new_bright_spots']} 个新亮点")
    
    print("\n" + "=" * 80)
    print("测试完成！各方法的详细结果已保存到对应的输出目录中。")
    print("=" * 80)

def main():
    """主函数"""
    fits_dir = r"E:\fix_data\align-compare"
    
    if not os.path.exists(fits_dir):
        print(f"错误: 目录不存在 - {fits_dir}")
        print("请修改脚本中的 fits_dir 变量为正确的路径")
        return
    
    try:
        compare_alignment_methods(fits_dir)
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")

if __name__ == "__main__":
    main()
