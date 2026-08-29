@echo off
rem Lancador clicavel do Analisador de Artigos.
rem O atalho do desktop aponta para este arquivo.
title Analisador de Artigos
cd /d "%~dp0.."
python "scripts\iniciar.py"
rem Se o python nem chegou a rodar, a janela some antes de dar para ler.
if errorlevel 9009 (
  echo.
  echo   [ERRO] Python nao encontrado no PATH.
  echo   Instale de https://www.python.org/downloads/ marcando "Add to PATH".
  echo.
  pause
)
