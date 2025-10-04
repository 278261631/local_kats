import cv2
import numpy as np
from pathlib import Path


def nothing(x):
    pass


def create_line_mask_interactive(image_path, output_dir='output'):
    """
    交互式调整参数来创建亮线掩码
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图片: {image_path}")
        return
    
    # 缩小显示尺寸以适应屏幕
    display_scale = 0.3
    display_image = cv2.resize(image, None, fx=display_scale, fy=display_scale)
    
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        display_gray = cv2.resize(gray, None, fx=display_scale, fy=display_scale)
    else:
        gray = image.copy()
        display_gray = display_image.copy()
    
    # 创建窗口和滑动条
    cv2.namedWindow('Controls')
    cv2.namedWindow('Original')
    cv2.namedWindow('Mask')
    cv2.namedWindow('Result')
    
    # 参数滑动条
    cv2.createTrackbar('Threshold', 'Controls', 200, 255, nothing)
    cv2.createTrackbar('Min Area', 'Controls', 50, 500, nothing)
    cv2.createTrackbar('Max Area', 'Controls', 5000, 10000, nothing)
    cv2.createTrackbar('Min Aspect', 'Controls', 5, 50, nothing)
    cv2.createTrackbar('Dilate', 'Controls', 1, 10, nothing)
    cv2.createTrackbar('Method', 'Controls', 0, 2, nothing)  # 0=area, 1=morphology, 2=edge
    
    print("交互式亮线去除工具")
    print("=" * 50)
    print("调整滑动条参数来优化效果")
    print("按 's' 保存当前结果")
    print("按 'q' 退出")
    print("=" * 50)
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    while True:
        # 获取当前参数
        threshold = cv2.getTrackbarPos('Threshold', 'Controls')
        min_area = cv2.getTrackbarPos('Min Area', 'Controls')
        max_area = cv2.getTrackbarPos('Max Area', 'Controls')
        min_aspect = cv2.getTrackbarPos('Min Aspect', 'Controls')
        dilate_size = cv2.getTrackbarPos('Dilate', 'Controls')
        method = cv2.getTrackbarPos('Method', 'Controls')
        
        # 确保参数有效
        threshold = max(1, threshold)
        min_area = max(1, min_area)
        max_area = max(min_area + 1, max_area)
        min_aspect = max(1, min_aspect)
        dilate_size = max(1, dilate_size)
        
        # 检测亮区域
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        
        # 根据选择的方法创建掩码
        if method == 0:  # 基于面积和长宽比
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
            mask = np.zeros(gray.shape, dtype=np.uint8)
            
            for i in range(1, num_labels):
                area = stats[i, cv2.CC_STAT_AREA]
                width = stats[i, cv2.CC_STAT_WIDTH]
                height = stats[i, cv2.CC_STAT_HEIGHT]
                aspect_ratio = max(width, height) / (min(width, height) + 1)
                
                # 标记符合条件的区域为亮线
                if (area >= min_area and area <= max_area) or aspect_ratio > min_aspect:
                    mask[labels == i] = 255
        
        elif method == 1:  # 形态学方法
            # 检测垂直线
            kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20))
            vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v, iterations=2)
            
            # 检测水平线
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
            horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h, iterations=2)
            
            mask = cv2.bitwise_or(vertical, horizontal)
        
        else:  # 边缘检测方法
            edges = cv2.Canny(binary, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, 
                                   minLineLength=30, maxLineGap=10)
            mask = np.zeros(gray.shape, dtype=np.uint8)
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    cv2.line(mask, (x1, y1), (x2, y2), 255, 3)
        
        # 膨胀掩码
        if dilate_size > 0:
            kernel = np.ones((dilate_size, dilate_size), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=1)
        
        # 修复图像
        result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
        
        # 缩小显示
        display_mask = cv2.resize(mask, None, fx=display_scale, fy=display_scale)
        display_result = cv2.resize(result, None, fx=display_scale, fy=display_scale)
        
        # 显示图像
        cv2.imshow('Original', display_image)
        cv2.imshow('Mask', display_mask)
        cv2.imshow('Result', display_result)
        
        # 等待按键
        key = cv2.waitKey(100) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('s'):
            # 保存结果
            base_name = Path(image_path).stem
            result_file = output_path / f"{base_name}_interactive_result.png"
            mask_file = output_path / f"{base_name}_interactive_mask.png"
            
            cv2.imwrite(str(result_file), result)
            cv2.imwrite(str(mask_file), mask)
            
            print(f"\n已保存:")
            print(f"  结果: {result_file}")
            print(f"  掩码: {mask_file}")
            print(f"  参数: threshold={threshold}, min_area={min_area}, max_area={max_area}")
            print(f"        min_aspect={min_aspect}, dilate={dilate_size}, method={method}")
    
    cv2.destroyAllWindows()


def batch_process_with_params(image_path, output_dir, threshold, min_area, max_area, min_aspect, dilate_size, method=0):
    """
    使用指定参数批量处理
    method: 0=area, 1=morphology, 2=edge
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图片: {image_path}")
        return

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # 检测亮区域
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # 根据选择的方法创建掩码
    if method == 0:  # 基于面积和长宽比
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
        mask = np.zeros(gray.shape, dtype=np.uint8)

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            width = stats[i, cv2.CC_STAT_WIDTH]
            height = stats[i, cv2.CC_STAT_HEIGHT]
            aspect_ratio = max(width, height) / (min(width, height) + 1)

            if (area >= min_area and area <= max_area) or aspect_ratio > min_aspect:
                mask[labels == i] = 255

    elif method == 1:  # 形态学方法
        # 检测垂直线
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20))
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v, iterations=2)

        # 检测水平线
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h, iterations=2)

        mask = cv2.bitwise_or(vertical, horizontal)

    else:  # method == 2, 边缘检测方法
        edges = cv2.Canny(binary, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                               minLineLength=30, maxLineGap=10)
        mask = np.zeros(gray.shape, dtype=np.uint8)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(mask, (x1, y1), (x2, y2), 255, 3)

    # 膨胀掩码
    if dilate_size > 0:
        kernel = np.ones((dilate_size, dilate_size), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

    # 修复图像
    result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)

    # 保存结果
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    base_name = Path(image_path).stem

    result_file = output_path / f"{base_name}_optimized_result.png"
    mask_file = output_path / f"{base_name}_optimized_mask.png"

    cv2.imwrite(str(result_file), result)
    cv2.imwrite(str(mask_file), mask)

    print(f"处理完成:")
    print(f"  结果: {result_file}")
    print(f"  掩码: {mask_file}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='交互式亮线去除工具')
    parser.add_argument('--input', '-i', type=str, default='line_test.png',
                        help='输入图片路径')
    parser.add_argument('--output', '-o', type=str, default='output',
                        help='输出目录')
    parser.add_argument('--interactive', action='store_true',
                        help='使用交互模式')
    parser.add_argument('--threshold', type=int, default=200,
                        help='亮度阈值')
    parser.add_argument('--min-area', type=int, default=50,
                        help='最小面积')
    parser.add_argument('--max-area', type=int, default=5000,
                        help='最大面积')
    parser.add_argument('--min-aspect', type=int, default=5,
                        help='最小长宽比')
    parser.add_argument('--dilate', type=int, default=1,
                        help='膨胀大小')
    parser.add_argument('--method', type=int, default=0, choices=[0, 1, 2],
                        help='方法: 0=面积长宽比, 1=形态学, 2=边缘检测')

    args = parser.parse_args()

    if args.interactive:
        create_line_mask_interactive(args.input, args.output)
    else:
        batch_process_with_params(args.input, args.output,
                                 args.threshold, args.min_area, args.max_area,
                                 args.min_aspect, args.dilate, args.method)

