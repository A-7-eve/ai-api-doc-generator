"""pytest 配置：确保 backend 目录在 sys.path 中"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
