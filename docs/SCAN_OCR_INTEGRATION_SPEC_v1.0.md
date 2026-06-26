# 扫描书 OCR 集成 — SPEC（PaddleOCR/PPStructureV3,Stratum Layer4）

**To**: Stratum CC
**From**: Stratum advisor
**日期**: 2026-06-20
**实证完成**: PaddleOCR中文95%+ + PPStructureV3结构化MD + onnxruntime绕Python3.14 + CPU 8-9s/页可行
**核心**: 方案C独立后处理服务,§20零主库改动,跟md_export_service同模式

---

## §0 定位与原则

- 扫描书OCR = 知识库完整性缺口(9本+未来扫描书)
- 方案C: Stratum独立后处理服务(scan_ocr_service),不改主库入库流程
- 触发: 只对扫描版(parse_quality scanned/empty/garbled),数字版不碰(仍pymupdf)
- batch_cpu主路径(一次性回填),GPU为可选升级
- 数学公式: OCR后LLM归一化(无FormulaNet ONNX)

---

## §1 依赖（Dockerfile.sl）

```
新增pip(~130MB):
  opencv-contrib-python (92MB) + paddleocr+paddlex (23MB) + shapely+pyclipper (15MB)
  onnxruntime 已有(不新增)
  modelscope 仅首次下载用,生产可跳过(预挂载卷)

模型卷挂载(docker-compose.yml,1.2GB走卷不进镜像):
  volumes:
    - /home/soffy/models/paddlex:/root/.paddlex
环境变量:
  PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True  # 离线加载,跳联网校验

GPU可选(升级路径,非必需):
  onnxruntime → onnxruntime-gpu
  docker-compose deploy.resources.reservations.devices nvidia
```

## §2 scan_ocr_service（Stratum新增,核心）

```python
# src/stratum/services/scan_ocr_service.py
# 模式同 md_export_service（事后更新substrates,不引入新架构）

from paddleocr import PPStructureV3
import fitz  # 渲染PDF页为图

def ocr_one(substrate_id: str, use_gpu: bool = False) -> dict:
    """单本扫描书OCR → 结构化MD → 更新substrate"""
    # 1. 取source_path(原始扫描PDF)
    # 2. PPStructureV3(engine='onnxruntime', use_formula_recognition=False)
    #    逐页: fitz渲染(dpi=150) → OCR → save_to_markdown
    # 3. 拼接全书MD
    # 4. UPDATE substrates SET
    #      content=<ocr_md>, parser='paddleocr-v6',
    #      parse_quality='ocr_ok', updated_at=NOW()
    # 5. md_export_service.export_one(substrate_id)  重新导出
    # 返回: {pages, elapsed, status}

def ocr_batch(use_gpu: bool = False) -> dict:
    """批量回填所有扫描书"""
    # 查触发条件:
    # SELECT id,source_path FROM substrates
    # WHERE parse_quality IN ('scanned','empty','garbled')
    #   AND (parser IS NULL OR parser NOT LIKE 'ocr%')
    # 逐本 ocr_one,进度记录
    # CPU: 9本~4.5h / GPU: ~45min

# 配置:
PPStructureV3 参数:
  engine='onnxruntime'
  use_formula_recognition=False  # FormulaNet无ONNX,绕过
  OCRv6 medium模型(178MB) + PPStructureV3版面(900MB)
DPI=150（速度精度平衡,8-9s/页）
```

## §3 数学公式 LLM 归一化（扫描数学书后处理）

```
扫描数学书OCR后,公式布局乱(分式/极限60-70%):
- 文字段95%可直接用
- 公式段需LLM归一化: x^{2}→x², lim行序重排

实现（Layer4或调oskill）:
- OCR的MD里检测公式特征(^{}/分式/lim/∫等)
- 这些段落 → LLM归一化prompt → 规范化
- 中文教材类(无公式)跳过此步,直接用
判据: 书类型(数学/物理 vs 社科/管理)决定要不要归一化
```

## §4 API + 触发

```
# src/stratum/api/routers/ 加 OCR 触发:
POST /api/v1/ocr/batch     # 批量回填所有扫描书(后台任务)
POST /api/v1/ocr/{id}      # 单本OCR
GET  /api/v1/ocr/status    # OCR进度

# 或: 前端「扫描书」管理区
#   显示 parse_quality=scanned 的书 + [OCR识别]按钮
#   batch回填进度(复用BackgroundTasksPanel)

# 自动触发(可选,GPU直通后):
#   入库检测scanned → 自动排队OCR
#   但CPU慢,默认手动批量,不阻塞日常入库
```

## §5 实施顺序

```
阶段1 依赖:
  Dockerfile.sl 加 paddleocr/opencv/paddlex
  docker-compose 模型卷挂载 + PADDLE离线环境变量
  预下载模型到 /home/soffy/models/paddlex
  build验证 onnxruntime后端可加载PPStructureV3

阶段2 scan_ocr_service:
  ocr_one + ocr_batch
  单本测试(曼昆扫描版,验证中文95%+结构化MD)

阶段3 公式归一化:
  数学书OCR后LLM归一化(Fitzpatrick验证)

阶段4 批量回填9本:
  ocr_batch CPU一次性(~4.5h,可挂着跑)
  或配GPU直通(~45min)
  → 9本scanned→ocr_ok,content更新,导出AII

阶段5 API/前端:
  OCR触发 + 进度显示
```

## §6 验收

```
- 曼昆扫描版 → PPStructureV3 → 中文95%+ 结构化MD(标题/段落/表格)
- parse_quality scanned → ocr_ok, parser='paddleocr-v6'
- 数学书(Fitzpatrick) → OCR + LLM归一化 → 公式可读
- 9本批量回填(CPU 4.5h或GPU 45min)
- OCR的MD导出AII(中文教材直接用,数学书归一化后用)
- 日常数字版入库不受影响(仍pymupdf,不触发OCR)
- 模型走卷不进镜像,离线加载
```

## §7 §20 / 注意

- 方案C全在Stratum层(scan_ocr_service),零主库改动 ✅
- parse_quality='scanned'初次标记不改(OCR后覆盖ocr_ok)
- 模型1.2GB走持久卷(~/.stratum或/home/soffy/models/paddlex),不进镜像
- CPU batch主路径,GPU可选升级(VRAM不冲突,3080剩6.5GB)
- 公式LLM归一化用现有provider(成本可控,只数学书触发)
- R-3: 真实扫描书OCR→结构化MD→导出,不接受mock

---

**End**
— Stratum advisor, 2026-06-20

扫描书OCR救知识库缺口。方案C零主库改动(同md_export模式)。
中文教材直接救,数学公式书LLM归一化。CPU一次性回填可行。
```
