#!/usr/bin/env python3
"""Remove bpmn.io bioc:stroke / bioc:fill color attributes from a BPMN file."""
import re
import sys
from pathlib import Path


def strip_bpmn_colors(text: str) -> str:
    text = re.sub(r'\s+bioc:stroke="[^"]*"', '', text)
    text = re.sub(r'\s+bioc:fill="[^"]*"', '', text)
    text = re.sub(r'\s+xmlns:bioc="[^"]*"', '', text)
    return text


def main():
    paths = sys.argv[1:] or [
        str(Path(__file__).resolve().parents[1] / 'static/src/bpmn/lr-department-master-process.bpmn'),
    ]
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            print(f'skip missing: {path}')
            continue
        original = path.read_text(encoding='utf-8')
        cleaned = strip_bpmn_colors(original)
        before = len(re.findall(r'bioc:(stroke|fill)=', original))
        after = len(re.findall(r'bioc:(stroke|fill)=', cleaned))
        path.write_text(cleaned, encoding='utf-8')
        print(f'{path}: {before} -> {after} color attrs')


if __name__ == '__main__':
    main()
