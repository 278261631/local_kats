@echo off
chcp 65001 >nul
echo ========================================
echo Histogram Peak Blob Detector
echo ========================================
echo.

cd /d "%~dp0"

python signal_blob_detector.py aligned_comparison_20251004_151632_difference.fits --threshold 0.3 --min-area 1 --max-area 1000

echo.
echo ========================================
echo Detection Complete
echo ========================================
pause

