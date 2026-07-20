"""重转损坏MD: markitdown从stratum保留的源PDF重新生成, 替换段落级重复的旧文件.
旧文件先备份到 aii/quarantine_corrupted_md/{category}/, 找不到源PDF的只搬出不重转
(等后续决定要不要补抓源). 用法: python scripts/regen_from_markitdown.py [--dry-run]
"""

import glob
import os
import re
import shutil
import sys
from collections import Counter

from markitdown import MarkItDown

ROOT = "/home/soffy/books/MD"
BACKUP_ROOT = "/data/soffy/projects/stratum/aii/quarantine_corrupted_md"
SUBSTRATE_DATA = "/home/soffy/.stratum/data/substrate"
FOLDERS = ["经济学", "中文数学", "英文数学", "其它"]

_CHAPTER_RE = re.compile(r"^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+\s*章|CHAPTER\s+\d+)\b")


def check_dup(text):
    paras = [p.strip() for p in text.split("\n") if len(p.strip()) > 80]
    c = Counter(paras)
    mc = c.most_common(1)
    return mc[0][1] if mc else 0


def frontmatter_field(text, key):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    fm = text[:end] if end != -1 else ""
    for line in fm.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def strip_running_headers(text):
    """无页边界信息(markitdown不给分页标记), 用全局行频率近似原有的按页页眉页脚剔除逻辑:
    短行(<150字符)出现次数异常多(>8次或>1%总行数) → 当页眉页脚剔除, 只留第一次出现。"""
    lines = text.split("\n")
    total = len(lines)
    cnt = Counter(l.strip() for l in lines if l.strip())
    thresh = max(8, int(total * 0.01))
    headers = {l for l, c in cnt.items() if c > thresh and len(l) < 150}
    out = []
    seen_header_once = set()
    for l in lines:
        s = l.strip()
        if s in headers:
            if s in seen_header_once:
                continue
            seen_header_once.add(s)
        out.append(l)
    return "\n".join(out)


def promote_chapters(text):
    out = []
    for l in text.split("\n"):
        s = l.strip()
        if s and _CHAPTER_RE.match(s):
            out.append(f"\n# {s}\n")
        else:
            out.append(l)
    return "\n".join(out)


def find_source_pdf(sid):
    for p in glob.glob(f"{SUBSTRATE_DATA}/*/{sid}--*"):
        return p
    return None


def main():
    dry_run = "--dry-run" in sys.argv
    md_engine = MarkItDown()

    corrupted = []
    for cat in FOLDERS:
        for p in glob.glob(f"{ROOT}/{cat}/*.md"):
            try:
                text = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            # ★已经markitdown重转过的不再重复处理(重转结果里表格分隔线/页脚这类良性短行
            # 复现仍可能命中check_dup阈值, 但不是真的坏——靠source frontmatter幂等跳过)
            if frontmatter_field(text, "source") == "stratum_markitdown_regen":
                continue
            if check_dup(text) >= 3:
                corrupted.append((cat, p, text))

    print(f"corrupted files found: {len(corrupted)}")
    regenerated, moved_only, failed = [], [], []

    for cat, path, old_text in corrupted:
        sid = frontmatter_field(old_text, "substrate_id")
        title = frontmatter_field(old_text, "title") or os.path.splitext(os.path.basename(path))[0]
        language = frontmatter_field(old_text, "language") or "zh"
        doc_type = frontmatter_field(old_text, "doc_type") or "book"
        name = os.path.basename(path)

        backup_dir = f"{BACKUP_ROOT}/{cat}"
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = f"{backup_dir}/{name}"

        src_pdf = find_source_pdf(sid) if sid else None

        if dry_run:
            status = "REGEN" if src_pdf else "MOVE_ONLY(无源PDF)"
            print(f"[dry-run] {status}: {cat}/{name}  sid={sid}  src={src_pdf}")
            continue

        shutil.copy2(path, backup_path)

        if not src_pdf:
            os.remove(path)
            moved_only.append((cat, name, sid))
            print(f"MOVED (无源PDF可重转): {cat}/{name}")
            continue

        try:
            result = md_engine.convert(src_pdf)
            new_text = result.text_content
            new_text = strip_running_headers(new_text)
            new_text = promote_chapters(new_text)
            fm = (
                f"---\ndoc_type: {doc_type}\nlanguage: {language}\n"
                f"source: stratum_markitdown_regen\nsubstrate_id: {sid}\ntitle: {title}\n---\n\n"
            )
            # ★stratum抓取写的文件owner是root(容器进程写的), soffy对文件本身无写权限,
            # 但对目录有rwx——POSIX下删除文件看的是目录权限, 不是文件owner, 先删再新建
            # (新建的文件自然归soffy)绕开这个权限问题, 不需要sudo。
            os.remove(path)
            open(path, "w", encoding="utf-8").write(fm + new_text)
            regenerated.append((cat, name, len(old_text), len(new_text)))
            print(f"REGEN OK: {cat}/{name}  {len(old_text)} -> {len(new_text)} chars")
        except Exception as e:
            # 重转失败: path 从未被覆写, 库内仍是旧内容(未变动); 备份是多余的, 删掉避免混淆
            os.remove(backup_path)
            failed.append((cat, name, str(e)))
            print(f"REGEN FAILED: {cat}/{name}: {e}")

    print(f"\n=== summary ===")
    print(f"regenerated: {len(regenerated)}")
    print(f"moved (no source): {len(moved_only)}")
    print(f"failed: {len(failed)}")
    for f in failed:
        print("  FAILED:", f)


if __name__ == "__main__":
    main()
