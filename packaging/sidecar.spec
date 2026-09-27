# python -m PyInstaller --noconfirm packaging/sidecar.spec
# One-folder output for Electron: dist/nde1-core/nde1-core.exe.
# console=True preserves NDE1_READY on stdout; Electron launches with windowsHide.
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "core" / "__main__.py")],
    pathex=[str(root)], binaries=[],
    datas=[(str(path), "core/council/prompts")
           for path in (root / "core" / "council" / "prompts").glob("*.md")],
    hiddenimports=[
        "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
        "win32api", "win32gui", "win32process", "win32timezone",
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="nde1-core",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="nde1-core")
