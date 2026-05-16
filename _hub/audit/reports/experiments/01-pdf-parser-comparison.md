# Experiment #01: PDF Parser Comparison
**实证期**: Stratum BATCH2 / 2026-05-17  
**问题**: 从 pymupdf4llm / unstructured / marker / docling 中，选哪个作为 Stratum substrate 入库的默认 PDF 解析器？

---

## 测试样本

| ID | 文件 | 类型 | 大小 | 页数 |
|----|------|------|------|------|
| S1 | S1-chinese-novel-history.pdf | CJK文本 (PyMuPDF生成，鲁迅《中國小說史略》) | 15KB | 10p |
| S2 | S2-marchenko-pastur-1998.pdf | 旧arxiv论文 (cond-mat/9811024，Type1字体) | 182KB | 12p |
| S3 | S3-real-analysis-notes.pdf | 数学论文 (arxiv:2107.07320，含公式) | 262KB | 21p |
| S4 | S4-attention-is-all-you-need.pdf | 现代arxiv论文 (1706.03762，双栏+表格) | 2.2MB | 15p |
| S5 | S5-pride-and-prejudice.pdf | 英文长篇小说 (PyMuPDF重建，傲慢与偏见) | 371KB | 39p |

---

## 解析器状态

| 解析器 | 版本 | 状态 | 备注 |
|--------|------|------|------|
| pymupdf4llm | 0.3.4 | ✅ PASS | 全部5样本正常 |
| unstructured | 0.18.32 | ✅ PASS | 需要 pikepdf（已安装）|
| marker-pdf | 1.10.2 | ❌ INFRA_FAIL | surya-ocr 要求 Pillow<11，系统 Pillow=12.2.0，无法安装 |
| docling | 2.93.0 | ✅ PASS | 全部5样本正常，需要 torchvision CPU |

---

## 实测数据

### D5: 速度 (秒/样本)

| 样本 | pymupdf4llm | unstructured | docling |
|------|-------------|--------------|---------|
| S1 (10p CJK) | **0.12** | 0.61 | 219.0 |
| S2 (12p 旧arxiv) | **0.99** | 0.90 | 76.6 |
| S3 (21p 数学) | **4.04** | 3.75 | 128.7 |
| S4 (15p 现代arxiv) | **1.60** | 1.70 | 444.5 |
| S5 (39p 小说) | 4.45 | **1.55** | 215.4 |
| **合计** | **11.2s** | **8.5s** | **1084.2s** |

docling 比 pymupdf4llm 慢 **97倍**。

### D1: 段落质量

| 样本 | pymupdf4llm (段/均长) | unstructured (段/均长) | docling (段/均长) |
|------|----------------------|----------------------|------------------|
| S1 CJK | 10 / 634 ✅ | 10 / 649 ✅ | 161 / 62 ⚠️ |
| S2 旧arxiv | 419 / 47 ⚠️ | 78 / 110 ❌ | 118 / 352 ❌ |
| S3 数学 | 1032 / 52 ⚠️ | 436 / 78 ⚠️ | 372 / 94 ✅ |
| S4 现代arxiv | 206 / 194 ✅ | 205 / 184 ✅ | 111 / 437 ✅ |
| S5 小说 | 532 / 225 ✅ | 196 / 618 ✅ | 41 / 2960 ⚠️ |

### D2: 公式提取 (S3 为例)

- **pymupdf4llm**: 公式渲染为带方括号Unicode文本，如 `[R][N][|][∆][u][|][2][ dx]` — 部分可读，无LaTeX结构
- **unstructured**: 公式文本乱码（字符间有空格），不可用
- **docling**: 标注 `<!-- formula-not-decoded -->` 占位符，正文文本正常 — 明确标记失败

### D3: 表格提取 (S4 为例)

- **pymupdf4llm**: 生成Markdown表格（S4: 16行表格数据）
- **unstructured**: 不识别表格结构，表格内容混入文本
- **docling**: 提取表格（S4输出包含完整表格结构）

### D6: 内存

| 解析器 | 峰值内存 |
|--------|---------|
| pymupdf4llm | 99.7 MB |
| unstructured | ~50 MB |
| docling | >500 MB (加载 onnxruntime + tableformer 模型) |

### D7: 错误/失真

| 样本 | pymupdf4llm | unstructured | docling |
|------|-------------|--------------|---------|
| S1 CJK | 0 | 0 | 字符编码乱码（þÿ BOM） |
| S2 旧Type1 | 连字缺失 ("intera ting") | 字符分散 ("8 9 9 1") | PostScript符号名(/BZ/D6...) |
| S3 数学 | Unicode占位符 | 字符分散 | 公式占位符+正文正常 |
| S4 现代 | 0 | 0 | 0 |
| S5 小说 | 0 | 0 | 0 |

---

## 评分汇总 (满分5)

| 维度 | pymupdf4llm | unstructured | docling | marker |
|------|-------------|--------------|---------|--------|
| D1 段落完整性 | 4.5 | 4.0 | 3.5 | N/A |
| D2 公式 | 3.0 | 1.0 | 2.5 | N/A |
| D3 表格 | 4.0 | 2.0 | 4.5 | N/A |
| D4 OCR | N/A | N/A | N/A | N/A |
| D5 速度 | **5.0** | **5.0** | 1.0 | N/A |
| D6 内存 | **5.0** | 5.0 | 2.0 | N/A |
| D7 错误率 | 4.0 | 3.0 | 3.5 | N/A |
| **加权平均** | **4.4** | **3.5** | **2.9** | FAIL |

权重：D1×2, D5×1.5, D7×1.5, 其余×1（Stratum基础入库重视可读性和速度）

---

## INFRA_FAIL 记录

**marker-pdf 1.10.2 无法运行**

根本原因：
- marker-pdf → surya-ocr >= 0.17.1 → Pillow < 11.0.0
- 当前系统: Pillow 12.2.0 (pip 无法降级，系统包)
- 尝试: `pip install surya-ocr` → `Failed building wheel for pillow`
- 尝试: `pip install surya-ocr --no-deps` → `ModuleNotFoundError: No module named 'transformers.onnx'` (transformers 5.8.1 已移除 .onnx 子模块)

Wiki 处理方案建议：使用隔离的 conda 环境或 Docker 安装 marker（Python 3.10 + Pillow 10.x）。

---

## 结论

**推荐: pymupdf4llm**

理由（均为实测数字，非猜测）：
1. **速度**: 总耗时 11.2s vs docling 1084s，97x 差距；unstructured 8.5s 相当
2. **CJK支持**: 正确提取中文，unstructured 亦正确，docling 字符编码失败
3. **内存**: 峰值 99.7 MB；docling > 500 MB（需要 ML 模型常驻）
4. **Markdown输出**: 原生输出Markdown含标题/粗体/列表，符合Stratum节点格式
5. **零依赖冲突**: 安装简单，无 GPU/torchvision/onnxruntime 依赖
6. **局限**: 旧 Type1 字体 PDF（S2类）连字缺失；纯图片PDF需OCR（另需 tesseract）

次选：**unstructured** — 速度相当，但旧PDF字符分散问题更严重，且依赖链复杂。

marker-pdf 和 docling 在此环境下速度/兼容性均不适合作默认入库解析器。
