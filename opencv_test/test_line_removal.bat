@echo off
chcp 65001 >nul
echo Testing bright line removal in signal_blob_detector...
echo.
echo This will process a difference.fits file and generate:
echo   - _stretched.png (original stretched image)
echo   - _stretched_no_lines.png (with bright lines removed)
echo.
cd ..
python opencv_test/signal_blob_detector.py
pause

