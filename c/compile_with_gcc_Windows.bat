@echo off
cd /d "%~dp0"
gcc -O3 -std=c99 -Wall -Wextra track_velocity.c -lm -o track_velocity.exe
if errorlevel 1 echo C compiler not installed. Optional module can be skipped.
pause
