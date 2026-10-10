-- 0010: 书籍自动分类配置 + 历史(2026-07-17)
-- 定期把 rclone 源(默认 gdrive:books/all)里的新书按用户配置的分类规则移到对应文件夹。
-- 混合分类: 关键词命中优先, 没命中调 LLM 按 description 兜底。
-- 单配置起步(owner='default'), owner 列留多租户扩展口。

CREATE TABLE IF NOT EXISTS aii.book_classify_config (
    owner         text PRIMARY KEY DEFAULT 'default',
    source        text NOT NULL DEFAULT 'gdrive-rw:books/all',   -- rclone 源(可写 remote)
    categories    jsonb NOT NULL DEFAULT '[]',                   -- [{folder, keywords:[], description}]
    skip_patterns jsonb NOT NULL DEFAULT '[]',                   -- 文件名含这些子串则跳过(非书: 视频/娱乐)
    enabled       boolean NOT NULL DEFAULT true,                 -- 定时任务是否启用
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS aii.book_classify_log (
    id        bigserial PRIMARY KEY,
    owner     text NOT NULL DEFAULT 'default',
    filename  text NOT NULL,
    category  text,               -- 分到哪个文件夹; NULL=跳过
    method    text,               -- keyword | llm | skip
    moved_ok  boolean,
    ts        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bcl_ts ON aii.book_classify_log (ts DESC);

-- 种默认配置(soffy 现用的 6 分类, 关键词=我手写那套, description 供 LLM 兜底)
INSERT INTO aii.book_classify_config (owner, source, categories, skip_patterns, enabled)
VALUES (
  'default',
  'gdrive-rw:books/all',
  '[
    {"folder":"数学","description":"纯数学教材:代数几何/拓扑/实复分析/群论/数论/微分几何/范畴论等",
     "keywords":["代数几何","Algebraic Geometry","拓扑","Topology","群论","伽罗瓦","流形上的分析","实分析","复分析","数论","范畴论","Logic and Deduction","现代数学基础","概率与位势"]},
    {"folder":"经济金融","description":"经济学与一般金融理论:微观宏观经济学/数理经济学/经济增长/均衡/投资/行为金融",
     "keywords":["经济","微观","宏观","投资","行为金融","均衡","增长","递归","数理经济","动态优化","Economic","Economists"]},
    {"folder":"量化与AI","description":"量化金融数学、机器学习/人工智能、编程/计算机",
     "keywords":["金融随机分析","金融数学","金融经济学","微观金融","金融统计","数理金融","机器学习","深度学习","强化学习","神经网络","正则表达式"]},
    {"folder":"哲学","description":"哲学、宗教、逻辑思想",
     "keywords":["道德经","第一性原理","哲学","黑格尔","克尔凯郭尔","佛教","逻辑学","尼采"]},
    {"folder":"社科心理","description":"心理学与社会科学",
     "keywords":["心理学","人格","微表情","社会学","认知科学","元认知"]},
    {"folder":"科学","description":"自然科学与科普(物理/生物/科学史/科普读物)",
     "keywords":["生物学","火箭科学家","半小时漫画","科普","物理","脑与数学","科学史"]}
  ]'::jsonb,
  '[".mp4",".mkv",".avi",".mov","西游记漫画"]'::jsonb,
  true
)
ON CONFLICT (owner) DO NOTHING;
