"""供 math_flywheel_prog.sh 逐本调用: 判断这本 MD 是否值得走 B 范式抽取.
不可抽(没有编号定义/定理, 如叙事类数学科普书)→ 挪到 /books/MD/其它, 让 misc 飞轮
(LLM规划模式)接手, 不进入本轮抽取循环(避免像数字乾坤/混沌那样白跑抽出0 KU).

退出码: 0=可抽(继续走正常流程)  1=已挪到其它(本轮跳过)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from math_extractable_gate import is_extractable  # noqa: E402

MISC_DIR = Path("/home/soffy/books/MD/其它")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace")
ok, n = is_extractable(text)
if ok:
    sys.exit(0)

MISC_DIR.mkdir(parents=True, exist_ok=True)
dst = MISC_DIR / path.name
if dst.exists():
    print(f"  ⚠ 其它/ 已有同名文件, 跳过挪动(可能已处理过): {path.name[:40]}")
    sys.exit(1)
shutil.move(str(path), str(dst))
print(f"  → 挪至其它(MARK命中={n}<5, 非编号教材): {path.name[:40]}")
sys.exit(1)
