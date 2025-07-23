#!/usr/bin/env python3
"""
验证带标记的FITS文件
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.visualization import ZScaleInterval, ImageNormalize
import argparse

def verify_marked_fits(original_fits, marked_fits, output_dir="verification_results"):
    """
    验证带标记的FITS文件
    
    Args:
        original_fits (str): 原始FITS文件路径
        marked_fits (str): 带标记的FITS文件路径
        output_dir (str): 输出目录
    """
    try:
        print("验证带标记的FITS文件...")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 加载原始FITS文件
        print(f"加载原始文件: {original_fits}")
        with fits.open(original_fits) as hdul:
            original_data = hdul[0].data.astype(np.float64)
            original_header = hdul[0].header
        
        # 加载带标记的FITS文件
        print(f"加载标记文件: {marked_fits}")
        with fits.open(marked_fits) as hdul:
            marked_data = hdul[0].data.astype(np.float64)
            marked_header = hdul[0].header
        
        # 检查基本信息
        print(f"原始图像大小: {original_data.shape}")
        print(f"标记图像大小: {marked_data.shape}")
        print(f"原始数据范围: [{np.min(original_data):.6f}, {np.max(original_data):.6f}]")
        print(f"标记数据范围: [{np.min(marked_data):.6f}, {np.max(marked_data):.6f}]")
        
        # 检查头信息中的O'TRAIN信息
        if 'OTRAIN' in marked_header:
            print(f"O'TRAIN处理标记: {marked_header['OTRAIN']}")
        if 'OTCANDS' in marked_header:
            print(f"候选天体数量: {marked_header['OTCANDS']}")
        if 'OTREALS' in marked_header:
            print(f"真实瞬变天体数量: {marked_header['OTREALS']}")
        
        # 计算差异
        difference = marked_data - original_data
        marked_pixels = np.sum(difference != 0)
        print(f"被标记的像素数量: {marked_pixels}")
        print(f"标记像素占比: {marked_pixels / (original_data.shape[0] * original_data.shape[1]) * 100:.4f}%")
        
        # 创建对比图像
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('FITS文件标记验证', fontsize=16)
        
        # 图像归一化
        norm_original = ImageNormalize(original_data, interval=ZScaleInterval())
        norm_marked = ImageNormalize(marked_data, interval=ZScaleInterval())
        
        # 1. 原始图像
        ax1 = axes[0, 0]
        im1 = ax1.imshow(original_data, cmap='gray', norm=norm_original, origin='lower')
        ax1.set_title('Original FITS Image')
        ax1.set_xlabel('X (pixels)')
        ax1.set_ylabel('Y (pixels)')
        plt.colorbar(im1, ax=ax1)
        
        # 2. 带标记的图像
        ax2 = axes[0, 1]
        im2 = ax2.imshow(marked_data, cmap='gray', norm=norm_marked, origin='lower')
        ax2.set_title('Marked FITS Image')
        ax2.set_xlabel('X (pixels)')
        ax2.set_ylabel('Y (pixels)')
        plt.colorbar(im2, ax=ax2)
        
        # 3. 差异图像
        ax3 = axes[1, 0]
        # 只显示有差异的区域
        diff_display = np.where(difference != 0, difference, np.nan)
        im3 = ax3.imshow(diff_display, cmap='hot', origin='lower')
        ax3.set_title('Marking Difference (Hot spots = Marks)')
        ax3.set_xlabel('X (pixels)')
        ax3.set_ylabel('Y (pixels)')
        plt.colorbar(im3, ax=ax3)
        
        # 4. 标记强度分布
        ax4 = axes[1, 1]
        mark_values = difference[difference != 0]
        if len(mark_values) > 0:
            ax4.hist(mark_values, bins=50, alpha=0.7, edgecolor='black')
            ax4.set_xlabel('Mark Intensity')
            ax4.set_ylabel('Pixel Count')
            ax4.set_title('Mark Intensity Distribution')
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, 'No marks found', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Mark Intensity Distribution')
        
        plt.tight_layout()
        
        # 保存验证图像
        verification_file = os.path.join(output_dir, "fits_marking_verification.png")
        plt.savefig(verification_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"验证图像已保存到: {verification_file}")
        
        # 保存验证报告
        report_file = os.path.join(output_dir, "verification_report.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("FITS文件标记验证报告\n")
            f.write("="*50 + "\n")
            f.write(f"原始文件: {original_fits}\n")
            f.write(f"标记文件: {marked_fits}\n")
            f.write(f"验证时间: {np.datetime64('now')}\n\n")
            
            f.write("图像信息:\n")
            f.write(f"  图像大小: {original_data.shape}\n")
            f.write(f"  原始数据范围: [{np.min(original_data):.6f}, {np.max(original_data):.6f}]\n")
            f.write(f"  标记数据范围: [{np.min(marked_data):.6f}, {np.max(marked_data):.6f}]\n\n")
            
            f.write("标记信息:\n")
            f.write(f"  被标记像素数: {marked_pixels}\n")
            f.write(f"  标记像素占比: {marked_pixels / (original_data.shape[0] * original_data.shape[1]) * 100:.4f}%\n")
            
            if 'OTCANDS' in marked_header:
                f.write(f"  候选天体数量: {marked_header['OTCANDS']}\n")
            if 'OTREALS' in marked_header:
                f.write(f"  真实瞬变天体数量: {marked_header['OTREALS']}\n")
            
            if len(mark_values) > 0:
                f.write(f"  标记强度范围: [{np.min(mark_values):.6f}, {np.max(mark_values):.6f}]\n")
                f.write(f"  平均标记强度: {np.mean(mark_values):.6f}\n")
        
        print(f"验证报告已保存到: {report_file}")
        print("验证完成!")
        
        return True
        
    except Exception as e:
        print(f"验证过程中出错: {str(e)}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="验证带标记的FITS文件")
    parser.add_argument('original_fits', help='原始FITS文件路径')
    parser.add_argument('marked_fits', help='带标记的FITS文件路径')
    parser.add_argument('--output-dir', '-o', default='verification_results', help='输出目录路径')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not os.path.exists(args.original_fits):
        print(f"原始文件不存在: {args.original_fits}")
        sys.exit(1)
    
    if not os.path.exists(args.marked_fits):
        print(f"标记文件不存在: {args.marked_fits}")
        sys.exit(1)
    
    # 执行验证
    success = verify_marked_fits(args.original_fits, args.marked_fits, args.output_dir)
    
    if success:
        print("\n✓ 验证成功完成!")
    else:
        print("\n✗ 验证失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()
