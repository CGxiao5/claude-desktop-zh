# -*- coding: utf-8 -*-
"""内置运行时自带：把 pywin32 目录加入 sys.path。
自动生成于 build_embedded_python.py，请勿手改。"""
import os as _os, sys as _sys
_lib = _os.path.dirname(_os.path.abspath(__file__))
for _p in ("win32", _os.path.join("win32", "lib")):
    _d = _os.path.join(_lib, _p)
    if _d not in _sys.path:
        _sys.path.append(_d)
