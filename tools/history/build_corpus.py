#!/usr/bin/env python3
"""W-H1a 语料层构建（ARC-SPEC §4.2）——白文 → 段落级 ULID → 每书语料文件。

R5 纪律：底本一律**维基文库白文**（CC BY-SA，标点许可登记），**禁对齐在版点校本**。
本脚本内嵌的白文均系 WebFetch 自 zh.wikisource.org 逐字摘录（会话可溯），非点校本、非记忆备录。
覆盖 = 首弧牵引 + 25 fixtures 被引段落（**部分覆盖**，非全书；全书全量入库属后续波次，见 REGISTRY.md 诚实标注）。

ULID 方案（无 ulid 模块）：substrate ULID = SHA256(src_id) 前 80 bit → Crockford base32（26 字，稳定可复现，
**确定性派生非时序 ULID**，honest 标注）；para_ulid = `<substrate-ULID>:NNNN`（后缀 4 位数字，合契约 para_ulid 模式 `[0-9A-HJKMNP-TV-Z]{4,8}`）。

用法：python3 tools/history/build_corpus.py   （幂等重跑，覆盖 docs/history/corpus/*.json）
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"
OUT = ROOT / "corpus"

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def derive_ulid(src_id: str) -> str:
    """确定性派生 26 字 Crockford base32（稳定、可复现；非时序 ULID，仅取其寻址格式）。"""
    h = hashlib.sha256(src_id.encode()).digest()
    n = int.from_bytes(h[:13], "big")  # 104 bit → 但只取 130 bit 需要更多；取 26*5=130 bit
    # 26 Crockford 字 = 130 bit；补足
    n = int.from_bytes(hashlib.sha256((src_id + "|ulid").encode()).digest()[:17], "big") >> 6
    s = ""
    for _ in range(26):
        s = CROCKFORD[n & 31] + s
        n >>= 5
    return s


# ── 底本登记（R5：URL / 许可 / 抓取日期 / 白文声明）───────────────────────────
BASES = {
    "src:zuozhuan": {
        "book": "左传（春秋左氏传）",
        "url": "https://zh.wikisource.org/wiki/春秋左氏傳",
        "license": "CC BY-SA 3.0（维基文库标点白文）",
        "fetch_date": "2026-07-22",
    },
    "src:shiji": {
        "book": "史记",
        "url": "https://zh.wikisource.org/wiki/史記",
        "license": "CC BY-SA 3.0（维基文库标点白文）",
        "fetch_date": "2026-07-22",
    },
    "src:guoyu": {
        "book": "国语",
        "url": "https://zh.wikisource.org/wiki/國語 / ctext.org",
        "license": "CC BY-SA 3.0（维基文库标点白文；晋语九补 ctext）",
        "fetch_date": "2026-07-22",
    },
    "src:zhanguoce": {
        "book": "战国策",
        "url": "https://zh.wikisource.org/wiki/戰國策",
        "license": "CC BY-SA 3.0（维基文库标点白文）",
        "fetch_date": "2026-07-22",
    },
    "src:zztj": {
        "book": "资治通鉴",
        "url": "https://zh.wikisource.org/wiki/資治通鑑/卷001",
        "license": "CC BY-SA 3.0（维基文库标点白文）",
        "fetch_date": "2026-07-22",
    },
    "src:sanguozhi": {
        "book": "三国志（含裴注）",
        "url": "https://zh.wikisource.org/wiki/三國志",
        "license": "CC BY-SA 3.0（维基文库标点白文）",
        "fetch_date": "2026-07-22",
    },
}

# ── 白文段落（verbatim 自 wikisource，R5；chapter + text + 支撑 fixture）─────────
# 每条 text 为逐字摘录（繁体照录），backs = 该段支撑的 fixture 引文。
PARAS = {
    "src:zuozhuan": [
        (
            "隐公五年",
            "五年春，公矢魚于棠。……（臧僖伯諫曰：凡物不足以講大事，其材不足以備器用，則君不舉焉。）……書曰「公矢魚于棠」，非禮也，且言遠地也。",
            ["F19"],
        ),
        ("哀公九年", "秋，吳城邗，溝通江、淮。", ["F20"]),
        ("哀公十四年", "甲午，齊陳恆弒其君壬于舒州。", ["F10"]),
        (
            "桓公二年",
            "師服曰：吾聞國家之立也，本大而末小，是以能固。故天子建國，諸侯立家，卿置側室，大夫有貳宗，士有隸子弟，庶人、工、商各有分親，皆有等衰。是以民服事其上，而下無覬覦。今晉，甸侯也，而建國，本既弱矣，其能久乎？",
            ["arc:jin-decline/thesis:shifu"],
        ),
        (
            "昭公三年",
            "晉之公族盡矣。肸聞之，公室將卑，其宗族枝葉先落，則公從之。肸之宗十一族，唯羊舌氏在而已，肸又無子。……欒、郤、胥、原、狐、續、慶、伯，降在皁隸，政在家門，民無所依。君日不悛，以樂慆憂。公室之卑，其何日之有？",
            ["arc:jin-decline/thesis:shuxiang"],
        ),
        (
            "昭公三十二年",
            "物生有兩、有三、有五、有陪貳。……社稷無常奉，君臣無常位，自古以然。……三后之姓於今為庶，王所知也。……魯君世從其失，季氏世脩其勤，民忘君矣。",
            ["arc:jin-decline/thesis:shimo"],
        ),
    ],
    "src:shiji": [
        (
            "赵世家",
            "三國攻晉陽，歲餘，引汾水灌其城，城不浸者三版。城中懸釜而炊，易子而食。",
            ["F23"],
        ),
        (
            "晋世家",
            "六卿彊，公室卑。……靜公二年，魏武侯、韓哀侯、趙敬侯滅晉後而三分其地，靜公遷為家人，晉絕不祀。",
            ["F25"],
        ),
        (
            "田敬仲完世家",
            "簡公出奔，田氏之徒追執簡公于徐州。……田氏之徒恐簡公復立而誅己，遂殺簡公。……康公之十九年，田和立為齊侯，列於周室，紀元年。",
            ["F10"],
        ),
        (
            "项羽本纪",
            "旦日饗士卒，為擊破沛公軍！……項莊拔劍起舞，項伯亦拔劍起舞，常以身翼蔽沛公，莊不得擊。……噲即帶劍擁盾入軍門，披帷西向立，瞋目視項王，頭髮上指，目眥盡裂。",
            ["F12"],
        ),
    ],
    "src:guoyu": [
        (
            "晋语九",
            "智宣子將以瑤為後，智果曰：不如宵也。……瑤之賢於人者五，其不逮者一也。……如是而甚不仁。以其五賢陵人，而以不仁行之，其誰能待之？若果立瑤也，智宗必滅。……智果別族于太史為輔氏。及智氏之亡也，唯輔果在。",
            ["F21"],
        ),
        ("晋语九·围晋阳", "晉師圍而灌之，沈灶產蛙，民無叛意。", ["F23"]),
    ],
    "src:zhanguoce": [
        (
            "赵策一",
            "圍晉陽三年，城中巢居而處，懸釜而炊。……決晉水而灌之，城下不沉者三板。……張孟談於是陰見韓、魏之君。",
            ["F23"],
        ),
        (
            "魏策一",
            "知伯索地於魏桓子，魏桓子弗予。任章曰：……無故索地，鄰國必恐；重欲無厭，天下必懼。君予之地，知伯必憍。……君不如與之，以驕知伯。……君曰：善。乃與之萬家之邑一。知伯大說。因索蔡、皋梁於趙，趙弗與，因圍晉陽。韓、魏反於外，趙氏應之於內，知氏遂亡。",
            ["F22"],
        ),
    ],
    "src:zztj": [
        ("周纪一·命侯", "初命晉大夫魏斯、趙籍、韓虔為諸侯。", ["F24"]),
        (
            "周纪一·臣光曰",
            "臣光曰：臣聞天子之職莫大於禮，禮莫大於分，分莫大於名。",
            ["F24", "arc:jin-decline/thesis:sima-guang"],
        ),
        (
            "周纪一·围晋阳",
            "三家以國人圍而灌之。……智伯行水，魏桓子御，韓康子驂乘。……趙襄子使張孟談潛出見二子，曰：臣聞脣亡則齒寒。",
            ["F23"],
        ),
    ],
    "src:sanguozhi": [
        (
            "蜀书·诸葛亮传·裴注引郭冲条亮五事其三",
            "亮屯於陽平，……司馬宣王率二十萬眾……亮意氣自若，敕軍中皆臥旗息鼓，不得妄出菴幔，又令大開四城門，埽地卻灑。宣王疑其有伏兵，於是引軍北趣山。",
            ["F8"],
        ),
        (
            "蜀书·诸葛亮传·裴注臣松之案",
            "案陽平在漢中。亮初屯陽平，宣帝尚為荊州都督，鎮宛城，至曹真死後，始與亮於關中相抗禦耳。……就如沖言，宣帝既舉二十萬眾，已知亮兵少力弱，若疑其有伏兵，正可設防持重，何至便走乎？",
            ["F8"],
        ),
    ],
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for src_id, paras in PARAS.items():
        sub_ulid = derive_ulid(src_id)
        base = BASES[src_id]
        para_objs = []
        total_chars = 0
        for i, (chapter, text, backs) in enumerate(paras, 1):
            pid = f"{sub_ulid}:{i:04d}"
            total_chars += len(text)
            para_objs.append(
                {"para_ulid": pid, "chapter": chapter, "text": text, "backs_fixtures": backs}
            )
        doc = {
            "substrate": {
                "substrate_ulid": sub_ulid,
                "source_ref": src_id,
                "book": base["book"],
                "base_text": {
                    "url": base["url"],
                    "license": base["license"],
                    "fetch_date": base["fetch_date"],
                    "char_count": total_chars,
                    "form": "白文（维基文库标点，CC BY-SA）",
                    "r5": "禁对齐在版点校本；非记忆备录，WebFetch 逐字",
                },
                "coverage": "部分（首弧牵引 + fixtures 被引段落）；全书全量入库属后续波次",
                "ulid_scheme": "substrate ULID = SHA256(src_id) 派生 Crockford base32（稳定可复现，非时序 ULID）",
            },
            "paragraphs": para_objs,
        }
        out = OUT / (src_id.replace("src:", "") + ".json")
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest.append((base["book"], src_id, sub_ulid, len(para_objs), total_chars, out.name))
        print(f"{out.name}: {len(para_objs)} paras, {total_chars} chars, ulid={sub_ulid}")
    print(f"--- {len(manifest)} substrates")
    return manifest


if __name__ == "__main__":
    main()
