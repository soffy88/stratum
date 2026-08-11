#!/usr/bin/env python3
"""MD 预检独立脚本 — 供 econ_batch_run.sh 调用.

用法: .venv/bin/python scripts/misc_precheck.py <md_path> <title>
输出: PASS | PASS_MULTI_FMT:N章 | PASS_FALLBACK:N章 | FAIL:原因
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def strip_frontmatter(text):
    if text.startswith('---'):
        end = text.find('\n---', 3)
        if end != -1:
            return text[text.find('\n', end + 1) + 1:]
    return text


def main():
    if len(sys.argv) < 3:
        print("FAIL:参数不足", flush=True)
        sys.exit(1)

    md_path = sys.argv[1]
    title = sys.argv[2]

    try:
        text = open(md_path, encoding='utf-8', errors='replace').read()
    except Exception as e:
        print(f"FAIL:文件读取失败-{str(e)[:40]}", flush=True)
        sys.exit(1)

    from aii.service.md_quality_check import check_md_quality
    from chapter_ingest import chapter_starts

    text_stripped = strip_frontmatter(text)
    q = check_md_quality(text_stripped, medium='book', title=title)

    if q['ok']:
        print("PASS", flush=True)
        return

    # Multi-format fallback: chapter_ingest 能识别更多格式
    # ★排除 running_header_noise(R9间隔字母页眉)——它只是页眉噪声, 不反映章节结构;
    #   chapter_ingest 能切出≥3章即视为可入库(切章正则不吃页眉行)
    n = len(chapter_starts(text))
    nonch = [f for f in q['hard_failures']
             if f['check'] not in ('chapter_structure', 'running_header_noise')]
    if not nonch and n >= 3:
        fmt_parts = []
        for f in q['hard_failures']:
            d = f.get('detail', '')
            if '# Chapter' in d:
                fmt_parts.append('canonical')
            elif '第N章' in d or '小数编号' in d:
                fmt_parts.append('non-canonical')
        fmt = ",".join(fmt_parts) if fmt_parts else "unknown"
        print(f'PASS_MULTI_FMT:{n}章(fmt={fmt})', flush=True)
        return

    # Hard failure
    fails = '; '.join(f["check"] + ":" + f["detail"][:80] for f in q['hard_failures'])
    print(f'FAIL:{fails}', flush=True)


if __name__ == '__main__':
    main()
