@echo off
chcp 65001 >nul
echo Starting interactive line removal tool...
python interactive_line_removal.py --input line_test.png --output output --interactive
pause

