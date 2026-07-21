# Notes · `chronology.json`

> 从 JSON 本体迁出的注释（下划线键）。JSON 本体现零下划线键、committed bytes 原样过 validate（无隐形预处理）。本文件仅供人读，非契约。

### / · _meta
```json
{
  "registry": "chronology",
  "spec": "AII-HISTORY-KU-SPEC-001 §3.2",
  "note": "纪年注册表种子。canonical 轴 = 共和元年（前841）起连续；之前入 fuzzy 区。per-source 映射 = 王公纪年/干支/年号→canonical。六国年表『系统性误差 override』结构必在，academic_source 允许 TODO（钱穆/杨宽一系）。争议日期政策：全部候选保留，主线取值走 mainline_decision（同 §4.3）。",
  "created": "2026-07-21",
  "author": "CC (手工)"
}
```

### /resolutions[0] · _note  ·  source_id=src:zztj, raw=周威烈王二十三年, canonical=前403
命侯之年，通鉴开篇。

### /resolutions[1] · _note  ·  source_id=src:shiji, raw=晋出公二十二年 / 晋阳之役后二年, canonical=前453
三家灭智、晋阳解围（前455围、前453灭智）。史记系年，年表略有出入，见下六国年表 override 说明。

### /resolutions[2] · _note  ·  source_id=src:zuozhuan, raw=鲁成公八年, canonical=前583
★下宫之难（左传）。与史记·赵世家『晋景公三年·前597』差14年——F2 date 冲突对象的两端之一。

### /resolutions[3] · _note  ·  source_id=src:shiji, raw=晋景公三年, canonical=前597
★史记·赵世家系屠岸贾灭赵于此（前597）。与左传前583差14年（F2 date 冲突）。同为史记，晋世家却系于成公八年左右（因袭左传）——史记篇内自相冲突，故 locator 必到篇。

### /resolutions[4] · _note  ·  source_id=src:sanguozhi, raw=建安五年, canonical=公元200
官渡之战。

### /resolutions[5] · _note  ·  source_id=src:shiji, raw=帝尧/帝舜（五帝本纪）, canonical=fuzzy（前841 之前，约前23世纪，不可 canonical 化）
★E4 传说层。date.type=fuzzy，屏幕 banner 显式标传说，不假装精确纪年。

### /sixstates_override_placeholders · _note
★六国年表系统性误差 override 占位。史记·六国年表战国纪年有已知系统性错误，学界（钱穆《先秦诸子系年》、杨宽《战国史》一系）有校正传统。此处结构先立，academic_source 待逐条落实（TODO）——这是『考据结论的工程化』，非我们自搞考据。灌注战国全量（W-H1）前逐条补全（见 spec Q2）。
