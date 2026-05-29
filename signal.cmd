@echo off
curl -s -X POST http://127.0.0.1:57422/state -H "Content-Type: application/json" -d "{\"state\":\"%2\",\"source\":\"%3\"}" >nul 2>&1
