@echo off
cd /d C:\Users\wkk\Desktop\verilog-wrapper\backend
start "Verilog Backend" python verilog-editor.py
cd /d C:\Users\wkk\Desktop\verilog-wrapper\verilog-editor
start "Verilog Frontend" npx vite --host
