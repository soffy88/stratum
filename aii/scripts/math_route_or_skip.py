"""供 math_flywheel_prog.sh 逐本调用: 判断这本 MD 是否值得走 B 范式抽取.
两道门禁:
  1. 乱码门(★2026-07-07新增, 见萨金特Stochastic Finance一案): 旧stratum转换器
     (pymupdf4llm/marker)留下的"图片占位符/上下标丢失/替换符"伪影, 0-LLM程序抽取
     原样抠出来就是乱码KU(math_prog_827bed3779等9本书实测确认)。命中→尝试用
     markitdown从stratum源PDF就地重转, 重转成功则继续走正常流程; 找不到源PDF
     则隔离等人工, 不进入本轮抽取(避免继续产出乱码KU)。
  2. 可抽门(原有): 没有编号定义/定理的叙事类数学科普书→挪到/books/MD/其它,
     让misc飞轮(LLM规划模式)接手.

退出码: 0=可抽(继续走正常流程)  1=已挪到其它/隔离(本轮跳过)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from math_corruption_gate import is_corrupted  # noqa: E402
from math_extractable_gate import is_extractable  # noqa: E402

MISC_DIR = Path("/home/soffy/books/MD/其它")
QUARANTINE_DIR = Path(
    "/data/soffy/projects/stratum/aii/quarantine_corrupted_md/math_prog_乱码待重转"
)
SUBSTRATE_DATA = Path("/home/soffy/.stratum/data/substrate")
# ★不直接写 PATH 里的 "rclone"——脚本被 math_flywheel_prog.sh 间接调用, 该链路
# 不像 math_drive_sync.sh 那样自己 export PATH=~/.local/bin, 会撞上
# FileNotFoundError(aii-book-classify.service 2026-07-18 撞过的同一个坑,
# 见 memory)。直接给绝对路径, 不依赖调用者的 PATH。
RCLONE = "/home/soffy/.local/bin/rclone"
# 已入库源 MD 归档位置(2026-07-19 用户指令: 已入库的不能删, 挪到 Drive 对应
# 位置)——gdrive-rw:aii-已入库源MD/ 下已有跟本地 books/MD/ 一致的分类子目录
# (中文数学/其它/经济学/英文数学), 是既有约定, 不是新起的目录。
ARCHIVE_REMOTE = "gdrive-rw:aii-已入库源MD/其它"


def _rclone_env() -> dict:
    """服务器在墙内, rclone 直连 Google 常超时(同 math_drive_sync.sh 的既有结论,
    首次实测就撞上了: 真实书文件传到一半超时, 小的测试文件走运没撞上)——统一走
    本机代理, 尊重外部已设的 HTTPS_PROXY(不覆盖)。"""
    env = os.environ.copy()
    proxy = os.environ.get("RCLONE_PROXY", "http://127.0.0.1:7890")
    if proxy and not env.get("HTTPS_PROXY"):
        env["HTTPS_PROXY"] = proxy
        env["HTTP_PROXY"] = proxy
    return env


def _frontmatter_field(text, key):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    fm = text[:end] if end != -1 else ""
    for line in fm.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def _find_source_pdf(sid):
    if not sid:
        return None
    for p in SUBSTRATE_DATA.glob(f"*/{sid}--*"):
        return p
    return None


path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace")

bad, sig = is_corrupted(text)
if bad:
    from markitdown import MarkItDown

    sid = _frontmatter_field(text, "substrate_id")
    src_pdf = _find_source_pdf(sid)
    if src_pdf:
        new_text = MarkItDown().convert(str(src_pdf)).text_content
        language = _frontmatter_field(text, "language") or "zh"
        doc_type = _frontmatter_field(text, "doc_type") or "book"
        title = _frontmatter_field(text, "title") or path.stem
        fm = (
            f"---\ndoc_type: {doc_type}\nlanguage: {language}\n"
            f"source: stratum_markitdown_regen\nsubstrate_id: {sid}\ntitle: {title}\n---\n\n"
        )
        path.write_text(fm + new_text, encoding="utf-8")
        print(f"  ⚠ 乱码门命中{sig}, 已用markitdown重转: {path.name[:40]}")
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        dst = QUARANTINE_DIR / path.name
        if not dst.exists():
            shutil.move(str(path), str(dst))
        print(f"  → 乱码门命中{sig}但找不到源PDF, 隔离等人工: {path.name[:40]}")
        sys.exit(1)

ok, n = is_extractable(text)
if ok:
    sys.exit(0)

MISC_DIR.mkdir(parents=True, exist_ok=True)
dst = MISC_DIR / path.name
if dst.exists():
    # ★2026-07-09 实测: 之前只跳过挪动、不处理源文件——源文件留在数学文件夹原地不动,
    # 下一轮discover又扫到它、又走到这里、又跳过, 无限重复(math_prog飞轮日志里"微积分的
    # 力量"/"贝叶斯思维"这两本书连续几小时每轮都打印同一条跳过日志, 永远空转)。目标位置
    # 已经有文件说明这本书已经被路由过一次了, 源文件是多余的旧副本, 得断循环、不再挪.
    # ★2026-07-19 用户指令: 已入库的 md 不能直接删——归档到 Drive(gdrive-rw:aii-已入库源MD/
    # 其它/)再清本地副本, 断循环但不丢数据; Drive 上传失败则本地原样保留、下轮重试
    # (不能既传失败又删了本地, 那真丢了)。
    try:
        subprocess.run(
            [RCLONE, "copy", str(path), ARCHIVE_REMOTE, "--drive-chunk-size", "64M"],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
            env=_rclone_env(),
        )
        path.unlink()
        print(
            f"  ⚠ 其它/ 已有同名文件(已处理过), 已归档到 Drive({ARCHIVE_REMOTE}) 并清本地多余源副本: {path.name[:40]}"
        )
    except Exception as e:
        print(f"  ⚠ 归档到 Drive 失败({e}), 本地文件保留不删(下轮重试): {path.name[:40]}")
    sys.exit(1)
shutil.move(str(path), str(dst))
print(f"  → 挪至其它(MARK命中={n}<5, 非编号教材): {path.name[:40]}")
sys.exit(1)
