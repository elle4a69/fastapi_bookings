#!/usr/bin/env python3
"""Runner script for PreToolUse pre-commit hook."""
import os
import runpy
import sys

curr = os.path.dirname(os.path.abspath(__file__))
target = os.path.join(curr, "pre_commit_guard.py")
runpy.run_path(target, run_name="__main__")
