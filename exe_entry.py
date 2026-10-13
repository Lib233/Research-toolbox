"""Packaging-only entry for the standalone Windows executable.

Keep the scientific UI and numerical code unchanged. PyInstaller unpacks data in
an ephemeral directory; copy demo sources out once so their paths remain stable
across app launches and saved analysis records.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def prepare_portable_demo_data():
    """Return a stable resource root if packaged, otherwise None."""
    if not getattr(sys, 'frozen', False):
        return None

    bundle_dir = Path(sys._MEIPASS)
    application_dir = Path(sys.executable).resolve().parent
    bundled_samples = bundle_dir / 'samples'
    portable_samples = application_dir / 'samples'

    if portable_samples.is_dir():
        if not (portable_samples / 'demo_signal.csv').is_file():
            raise RuntimeError(
                'EXE 旁的 samples 文件夹不完整。请备份自己的文件后，'
                '将该文件夹改名或移走，再重新启动程序。'
            )
        return application_dir

    if not bundled_samples.is_dir():
        raise RuntimeError('EXE 内缺少 samples 演示数据，请重新运行打包脚本。')

    staging = application_dir / '_samples_unpack_in_progress'
    try:
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(bundled_samples, staging)
        staging.rename(portable_samples)
    except OSError as exc:
        raise RuntimeError(
            '无法在 EXE 所在目录创建演示数据文件夹。'
            '请将 EXE 放在桌面或其他有写入权限的普通文件夹中运行。'
            f'\n\n详细原因：{exc}'
        ) from exc
    return application_dir


def main():
    try:
        stable_root = prepare_portable_demo_data()
    except Exception as exc:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('Research Toolbox 启动失败', str(exc))
        root.destroy()
        raise SystemExit(1)

    import desktop
    if stable_root is not None:
        desktop.BASE = stable_root
    desktop.Desktop().mainloop()


if __name__ == '__main__':
    main()
