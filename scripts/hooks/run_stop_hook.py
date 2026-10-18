#!/usr/bin/env python3
"""Runner script for Stop hook."""
import os
import runpy
import sys

curr = os.path.dirname(os.path.abspath(__file__))
target = os.path.join(curr, "unconditional_audit_gate.py")
runpy.run_path(target, run_name="__main__")
