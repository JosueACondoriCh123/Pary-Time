"""Configuración global de la suite (Frente 0).

NDE1_NO_DESKTOP=1: ningún test toca el escritorio real de la persona. El runtime usa `NoWindows` y no abre
archivos aunque arranque el scheduler de verdad (p.ej. con `TestClient(create_app(...))`). Los tests de
ventanas reales (`tests/runtime/test_b2_windows.py`) pasan `Win32Ops` explícitamente sobre su propia ventana Tk.
"""
import os

os.environ["NDE1_NO_DESKTOP"] = "1"
