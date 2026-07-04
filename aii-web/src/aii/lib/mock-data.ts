/**
 * Mock 数据 — NEXT_PUBLIC_USE_MOCK=true 时使用。
 *
 * 目的:让前端在后端没起时也能跑,看 UI 装配。
 * 故意混入一条 degraded warning 让 DegradedBanner 在某些 query 时显示。
 * AII 接管业务逻辑后,这个文件可以删,或保留作为 demo 数据。
 */

import type {
  ApiResult,
  QueryRequest,
  QueryResponse,
  IngestRequest,
  IngestResponse,
  GraphHealthResponse,
  DiagnoseRequest,
  DiagnoseResponse,
  EvolutionResponse,
  GovernanceActionRequest,
  GovernanceActionResponse,
  ChatRequest,
  ChatResponse,
} from '@/aii/types/api';

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ============================================================
// /query
// ============================================================

export async function mockQuery(req: QueryRequest): Promise<ApiResult<QueryResponse>> {
  await delay(300);
  // 故意:如果 query 含 "degraded",返回降级 warning(测试 banner)
  const isDegraded = req.query.toLowerCase().includes('degraded');
  return {
    ok: true,
    degraded: isDegraded,
    warning: isDegraded ? 'degraded_no_provider' : undefined,
    data: {
      total: 3,
      query_id: 'mock-q-001',
      items: [
        {
          id: 'frag-001',
          title: '中央银行政策传导路径',
          body:
            '货币政策通过利率渠道、资产价格渠道和信贷渠道影响实体经济。其中,利率渠道在 2008 年后的有效性显著下降,反映在 IS 曲线变陡。',
          grade: 'proven',
          defeaters: [],
          source: 'cb_research_2024.pdf §3.2',
          score: 0.92,
          metadata: [
            { label: '出处', value: 'cb_research_2024.pdf' },
            { label: '章节', value: '§3.2' },
          ],
        },
        {
          id: 'frag-002',
          title: '量化宽松对资产价格的影响',
          body:
            'QE 通过资产组合再平衡效应推高风险资产价格。但 2020 年后,这一传导效率出现分化:股市受益明显,信用债市场反应钝化。',
          grade: 'moderate',
          defeaters: [
            { id: 'd-1', text: 'Krishnamurthy & Vissing-Jorgensen (2022) 用工具变量识别后,效应只有早期估计的 1/3。', weight: 0.6 },
          ],
          source: 'fed_qe_review_2023.pdf §5',
          score: 0.78,
          metadata: [{ label: '反证强度', value: '中等(weight=0.6)' }],
        },
        {
          id: 'frag-003',
          title: '资本流动与汇率脆弱性的关系',
          body:
            '这是一个还在验证中的断言,需要更多新兴市场样本支持。Pending verification — 不应作为推荐依据。',
          grade: 'pending_verification',
          defeaters: [],
          source: 'em_panel_wip_2025.pdf §draft',
          score: 0.55,
          metadata: [{ label: '状态', value: '隔离区,待验证' }],
        },
      ],
    },
  };
}

// ============================================================
// /ingest
// ============================================================

export async function mockIngest(req: IngestRequest): Promise<ApiResult<IngestResponse>> {
  await delay(500);
  const lines = req.text.split('\n').filter((l) => l.trim().length > 0);
  return {
    ok: true,
    degraded: false,
    data: {
      ingested_count: lines.length,
      fragment_ids: lines.map((_, i) => `frag-mock-${Date.now()}-${i}`),
      rejected: lines.length > 5 ? [{ reason: '超出单次上限示例', preview: lines[5]?.slice(0, 40) }] : undefined,
    },
  };
}

// ============================================================
// /graph/health
// ============================================================

export async function mockGraphHealth(): Promise<ApiResult<GraphHealthResponse>> {
  await delay(200);
  return {
    ok: true,
    degraded: false,
    data: {
      total_nodes: 1247,
      total_edges: 3892,
      grade_distribution: {
        proven: 312,
        high: 428,
        moderate: 287,
        low: 145,
        very_low: 38,
        unverified: 19,
        contradicted: 12,
        pending_verification: 6,
      },
      defeater_count: 89,
      last_audit_at: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
      health_score: 0.74,
    },
  };
}

// ============================================================
// /diagnose
// ============================================================

export async function mockDiagnose(_req: DiagnoseRequest): Promise<ApiResult<DiagnoseResponse>> {
  await delay(400);
  return {
    ok: true,
    degraded: false,
    data: {
      axes: [
        { axis: '来源可信度', value: 0.82 },
        { axis: '反证密度', value: 0.31 },
        { axis: '同侪复现', value: 0.65 },
        { axis: '时效性', value: 0.78 },
        { axis: '边界清晰度', value: 0.55 },
        { axis: '可证伪性', value: 0.70 },
      ],
      series: [
        { name: '当前片段', values: [0.82, 0.31, 0.65, 0.78, 0.55, 0.70] },
      ],
      notes: ['注:数值为客观度量,不含目标线/达标线(红线 #3)'],
    },
  };
}

// ============================================================
// /evolution/propose
// ============================================================

export async function mockEvolution(): Promise<ApiResult<EvolutionResponse>> {
  await delay(300);
  const now = Date.now();
  return {
    ok: true,
    degraded: false,
    data: {
      history: [
        {
          id: 'ev-001',
          time: new Date(now - 1000 * 60 * 60 * 24 * 3).toISOString(),
          kind: 'accepted',
          title: '接受新片段 frag-998:重构利率渠道描述',
          actor: 'wiki',
          status: 'success',
        },
        {
          id: 'ev-002',
          time: new Date(now - 1000 * 60 * 60 * 24).toISOString(),
          kind: 'rolled_back',
          title: '回滚 frag-1001:反证密度超阈值',
          body: 'Krishnamurthy & Vissing-Jorgensen (2022) 反证强度 0.85 > 阈值 0.7',
          actor: 'system',
          status: 'success',
        },
      ],
      pending: [
        {
          id: 'ev-003',
          time: new Date(now - 1000 * 60 * 30).toISOString(),
          kind: 'proposed',
          title: '提议:把 frag-002 从 moderate 降级到 low',
          body: '依据:新增反证 weight=0.6,聚合反证密度从 0.4 升至 0.62',
          status: 'pending',
        },
      ],
    },
  };
}

// ============================================================
// /governance/action
// ============================================================

export async function mockGovernanceAction(
  req: GovernanceActionRequest
): Promise<ApiResult<GovernanceActionResponse>> {
  await delay(600);
  return {
    ok: true,
    degraded: false,
    data: {
      applied: true,
      audit_log_id: `audit-mock-${Date.now()}`,
    },
  };
}

// ============================================================
// /api/chat (REQ-003)
//
// 根据 query 内容触发 4 种 mode,方便前端自测 mode 视觉区分:
//   - 含 "闲聊" / "你好" → chitchat
//   - 含 "未知" / "Z 国" → no_knowledge
//   - 含 "股票" / "买" / "卖" → grounded 但 low confidence + 强免责
//   - 其他 → grounded 正常
// ============================================================

export async function mockChat(req: ChatRequest): Promise<ApiResult<ChatResponse>> {
  await delay(600);
  const q = req.message.toLowerCase();

  // chitchat
  if (q.includes('你好') || q.includes('hi') || q.includes('hello') || q.includes('闲聊')) {
    return {
      ok: true,
      degraded: false,
      data: {
        mode: 'chitchat',
        answer: '你好。我是 AII,一个把可信度暴露给你的认识论外脑。请直接提问。',
        epistemic_confidence: 0,
        confidence_basis: '闲聊回答 — 不基于知识库,仅作礼貌响应',
        citations: [],
      },
    };
  }

  // no_knowledge
  if (q.includes('未知') || q.includes('z 国') || q.includes('xyz')) {
    return {
      ok: true,
      degraded: false,
      data: {
        mode: 'no_knowledge',
        answer: '知识库中没有覆盖此问题。不要把我下面的"猜测"当作有效回答 — 我没有依据。',
        epistemic_confidence: 0,
        confidence_basis: '知识库未命中 — 0 条相关 KU',
        citations: [],
      },
    };
  }

  // grounded 金融场景 — low confidence + 强免责
  if (q.includes('股票') || q.includes('买') || q.includes('卖') || q.includes('涨')) {
    return {
      ok: true,
      degraded: false,
      data: {
        mode: 'grounded',
        answer:
          '关于这个金融问题,知识库内只有少量待验证片段。我能告诉你的是历史上类似条件下的多种情景,但**没有任何信号**强到足以做交易决定。',
        epistemic_confidence: 0.22,
        confidence_basis: '基于 2 条 KU:0 proven, 2 unverified',
        citations: [
          {
            ku_id: 'ku-mkt-091',
            grade: 'unverified',
            snippet: '2018-2024 年间,在 VIX>30 且 yield curve 倒挂的样本中,后续 60 日 SPX 中位数下行 4.2%(N=11,IQR 宽)',
          },
          {
            ku_id: 'ku-mkt-138',
            grade: 'unverified',
            snippet: '横截面动量在牛末通常显著弱化,但本次窗口数据未对齐',
          },
        ],
        disclaimer:
          '本回答不构成投资建议。AII 永远不会输出买卖指令。市场决策应基于你自己的判断 + 完整尽调。',
      },
    };
  }

  // grounded 正常
  return {
    ok: true,
    degraded: false,
    data: {
      mode: 'grounded',
      answer:
        '中央银行通过利率渠道、资产价格渠道和信贷渠道传导货币政策。其中利率渠道在 2008 年后效果显著弱化 — 这是有较强证据支持的结论。',
      epistemic_confidence: 0.78,
      confidence_basis: '基于 5 条 KU:3 proven, 2 high',
      citations: [
        {
          ku_id: 'ku-cb-001',
          grade: 'proven',
          snippet: '货币政策传导三大渠道在标准教科书(Mishkin, 2022)中明确定义,2008 后实证显示利率渠道效率下降',
        },
        {
          ku_id: 'ku-cb-014',
          grade: 'proven',
          snippet: '2008-2020 期间 Federal funds rate 与 mortgage rate 联动系数从 0.91 降到 0.63',
        },
        {
          ku_id: 'ku-cb-027',
          grade: 'high',
          snippet: 'Bernanke (2020) 综述指出 QE 替代了部分利率渠道功能,但有效性区域分化',
        },
      ],
    },
  };
}

// ============================================================
// AII-FRONTEND-DISPLAY-001 — 成果展示 mock 数据
//   规模对齐文档现状:KU 10995 / 边 8803 / KC 21 / BU 11
//   grade 几乎全 unverified(proven=1)——诚实呈现,不美化。
// ============================================================

import type {
  StatsOverviewResponse,
  StatsIngestionResponse,
  KuListRequest,
  KuListResponse,
  KuListItem,
  KuDetail,
  SubgraphRequest,
  SubgraphResponse,
  GraphSearchRequest,
  GraphSearchResponse,
  GraphNode,
  GraphEdge,
  KcListItem,
  KcDetail,
  BuListItem,
  BuDetail,
  KnowledgeType,
  RelationType,
} from '@/aii/types/api';
import type { EpistemicGrade } from '@helios/blocks';

// ── 概览统计 ──
export async function mockStatsOverview(): Promise<ApiResult<StatsOverviewResponse>> {
  await delay(250);
  return {
    ok: true, degraded: false,
    data: {
      ku_count: 10995,
      edge_count: 8803,
      kc_count: 21,
      bu_count: 11,
      // 命门:诚实分布 —— proven 仅 1,绝大多数 unverified
      grade_dist: {
        proven: 1,
        high: 42,
        moderate: 318,
        low: 1247,
        unverified: 9302,
        contradicted: 85,
      },
      merge_count: 1683,
      dedup_saved: 2822,
      relation_type_dist: {
        references: 4120,
        prerequisite_of: 1876,
        special_case_of: 1204,
        supports: 982,
        related_to: 533,
        contradicts: 88,   // 诚实亮点:AII 发现的知识冲突
      },
    },
  };
}

export async function mockStatsIngestion(): Promise<ApiResult<StatsIngestionResponse>> {
  await delay(250);
  return {
    ok: true, degraded: false,
    data: {
      total_files: 247,
      ingested: 198,
      by_medium: {
        book:  { total: 142, ingested: 121 },
        paper: { total: 83,  ingested: 64  },
        video: { total: 22,  ingested: 13  },
      },
      deep_understood: 11,
    },
  };
}

// ── KU 列表(可筛选/分页) ──
const GRADES: EpistemicGrade[] = ['proven','high','moderate','low','unverified','contradicted'];
const KTYPES: KnowledgeType[] = ['theorem','definition','concept','claim','method','observation'];
const BOOKS = [
  { id: 'sub-capital',   title: '《资本论》' },
  { id: 'sub-keynes',    title: '《就业、利息和货币通论》' },
  { id: 'sub-kahneman',  title: '《思考,快与慢》' },
  { id: 'sub-spivak',    title: '《微积分》(Spivak)' },
  { id: 'sub-sapiens',   title: '《人类简史》' },
];
const KU_TEXTS = [
  '商品的价值由生产它所需的社会必要劳动时间决定。',
  '在流动性陷阱中,货币政策对利率的影响趋于失效,需依赖财政政策。',
  '系统1快速直觉、系统2缓慢理性;多数判断由系统1主导并产生可预测偏差。',
  '若函数在闭区间上连续,则它在该区间上取得最大值与最小值(极值定理)。',
  '认知革命使智人能够通过虚构故事进行大规模灵活协作。',
  '边际效用递减:随着消费量增加,每单位带来的额外效用下降。',
  '可证伪性是科学命题区别于非科学命题的分界标准。',
  '复利的长期效应使早期储蓄的价值被显著放大。',
];

function makeKu(i: number): KuListItem {
  const book = BOOKS[i % BOOKS.length];
  // 命门:绝大多数 unverified
  const g: EpistemicGrade = i === 0 ? 'proven'
    : i % 23 === 0 ? 'contradicted'
    : i % 7 === 0 ? 'moderate'
    : i % 5 === 0 ? 'low'
    : i % 11 === 0 ? 'high'
    : 'unverified';
  return {
    id: `ku-${String(i).padStart(5,'0')}`,
    natural_text: KU_TEXTS[i % KU_TEXTS.length],
    grade: g,
    knowledge_type: KTYPES[i % KTYPES.length],
    substrate_id: book.id,
    substrate_title: book.title,
    merge_count: i % 4 === 0 ? 1 + (i % 3) : 1,  // 部分多书共有
    defeater_count: g === 'contradicted' ? 2 : g === 'moderate' ? 1 : 0,
  };
}

export async function mockKuList(req: KuListRequest): Promise<ApiResult<KuListResponse>> {
  await delay(280);
  const pageSize = req.page_size ?? 20;
  const page = req.page ?? 1;
  // 生成一个稳定的"全集"切片(模拟 10995 条)
  const TOTAL = 10995;
  const all: KuListItem[] = Array.from({ length: 240 }, (_, i) => makeKu(i));
  let filtered = all;
  if (req.grade) filtered = filtered.filter(k => k.grade === req.grade);
  if (req.type) filtered = filtered.filter(k => k.knowledge_type === req.type);
  if (req.substrate) filtered = filtered.filter(k => k.substrate_id === req.substrate);
  if (req.merged_only) filtered = filtered.filter(k => k.merge_count > 1);
  const start = (page - 1) * pageSize;
  const items = filtered.slice(start, start + pageSize);
  // total:无筛选时报真实规模,有筛选时报过滤后估算
  const total = (!req.grade && !req.type && !req.substrate && !req.merged_only)
    ? TOTAL : filtered.length;
  return {
    ok: true, degraded: false,
    data: {
      items, total, page, page_size: pageSize,
      facets: {
        grades: { proven:1, high:42, moderate:318, low:1247, unverified:9302, contradicted:85 },
        substrates: BOOKS.map((b, i) => ({ id: b.id, title: b.title, count: 2199 - i*180 })),
      },
    },
  };
}

export async function mockKuDetail(id: string): Promise<ApiResult<KuDetail>> {
  await delay(220);
  const idx = parseInt(id.replace(/\D/g,'') || '1', 10);
  const base = makeKu(idx);
  const merged = base.merge_count > 1;
  return {
    ok: true, degraded: false,
    data: {
      ...base,
      sources: merged
        ? [
            { substrate_id:'sub-capital', substrate_title:'《资本论》', text:'商品价值由社会必要劳动时间决定。', locator:'第一卷 第一章' },
            { substrate_id:'sub-keynes',  substrate_title:'《通论》',   text:'劳动时间作为价值尺度的古典命题。', locator:'第二篇' },
          ]
        : [{ substrate_id: base.substrate_id, substrate_title: base.substrate_title, text: base.natural_text, locator:'§3.2' }],
      defeaters: base.grade === 'contradicted'
        ? [{ id:'d1', text:'马歇尔的边际效用理论对劳动价值论提出系统性质疑。', weight:0.7 }]
        : [],
      edges: [
        { target_id:'ku-00007', target_text:'边际效用递减', relation_type:'contradicts', extraction_method:'llm',  grade:'low' },
        { target_id:'ku-00012', target_text:'社会必要劳动时间', relation_type:'prerequisite_of', extraction_method:'rule', grade:'unverified' },
      ],
    },
  };
}

// ── 子图(图谱) ──
export async function mockSubgraph(req: SubgraphRequest): Promise<ApiResult<SubgraphResponse>> {
  await delay(300);
  const center = req.ku_id || 'ku-00001';
  const N = Math.min(req.limit ?? 24, 40);
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const grade = (i: number): EpistemicGrade =>
    i === 0 ? 'proven' : i % 9 === 0 ? 'contradicted' : i % 6 === 0 ? 'moderate' : i % 4 === 0 ? 'low' : 'unverified';
  for (let i = 0; i < N; i++) {
    nodes.push({
      id: i === 0 ? center : `ku-${String(1000 + i).padStart(5,'0')}`,
      label: KU_TEXTS[i % KU_TEXTS.length].slice(0, 18),
      grade: grade(i),
      knowledge_type: KTYPES[i % KTYPES.length],
      degree: i === 0 ? N - 1 : 1 + (i % 4),
    });
  }
  const RELS: RelationType[] = ['references','prerequisite_of','special_case_of','supports','contradicts','related_to'];
  for (let i = 1; i < N; i++) {
    const rel = RELS[i % RELS.length];
    edges.push({
      id: `e-${i}`,
      source: nodes[0].id,
      target: nodes[i].id,
      relation_type: rel,
      // 命门:rule 实线 / llm 虚线
      extraction_method: i % 3 === 0 ? 'rule' : 'llm',
      grade: grade(i),
    });
    // 一些二跳边
    if (i > 1 && i % 5 === 0) {
      edges.push({
        id: `e-${i}-x`, source: nodes[i].id, target: nodes[i-1].id,
        relation_type: 'related_to', extraction_method: 'llm', grade: 'unverified',
      });
    }
  }
  return {
    ok: true, degraded: false,
    data: { nodes, edges, center_id: nodes[0].id, truncated: (req.limit ?? 24) < 100 },
  };
}

export async function mockGraphSearch(req: GraphSearchRequest): Promise<ApiResult<GraphSearchResponse>> {
  await delay(180);
  const q = req.q.trim();
  const matches = KU_TEXTS
    .filter(t => !q || t.includes(q))
    .slice(0, req.limit ?? 8)
    .map((t, i) => ({ id: `ku-${String(i+1).padStart(5,'0')}`, label: t.slice(0, 24), grade: (i===0?'proven':'unverified') as EpistemicGrade }));
  return { ok: true, degraded: false, data: { matches } };
}

// ── 知识簇 KC ──
const KC_DATA: KcListItem[] = [
  { id:'kc-01', community_label:'货币政策传导', summary:'围绕利率渠道、资产价格渠道与信贷渠道的知识聚合,核心争议在 2008 后利率渠道有效性。', grade:'moderate', community_size:184 },
  { id:'kc-02', community_label:'劳动价值与边际效用', summary:'古典劳动价值论与新古典边际效用论的对立簇,含多条 contradicts 边。', grade:'low', community_size:142 },
  { id:'kc-03', community_label:'认知偏差', summary:'系统1/系统2 框架下的判断偏差集合:锚定、可得性、损失厌恶等。', grade:'moderate', community_size:97 },
  { id:'kc-04', community_label:'微积分极限理论', summary:'连续性、极值定理、中值定理构成的形式化推理簇,grade 相对较高。', grade:'high', community_size:63 },
];
export async function mockKcList(): Promise<ApiResult<KcListItem[]>> {
  await delay(220);
  // 补足到 21 个(文档现状)
  const more = Array.from({ length: 17 }, (_, i) => ({
    id:`kc-${String(i+5).padStart(2,'0')}`,
    community_label:`主题簇 ${i+5}`,
    summary:'AII 基于社区检测聚合的知识簇,摘要为综合表述。',
    grade:(i%3===0?'low':'unverified') as EpistemicGrade,
    community_size: 80 - i*3,
  }));
  return { ok:true, degraded:false, data: [...KC_DATA, ...more] };
}
export async function mockKcDetail(id: string): Promise<ApiResult<KcDetail>> {
  await delay(200);
  const base = KC_DATA.find(k => k.id === id) ?? KC_DATA[0];
  return {
    ok:true, degraded:false,
    data: {
      ...base, id,
      source_ku_ids: ['ku-00001','ku-00007','ku-00012','ku-00019'],
      members: [
        { id:'ku-00001', natural_text:'商品的价值由社会必要劳动时间决定。', grade:'proven' },
        { id:'ku-00007', natural_text:'边际效用递减规律。', grade:'low' },
        { id:'ku-00012', natural_text:'社会必要劳动时间的定义。', grade:'unverified' },
      ],
    },
  };
}

// ── 书级理解 BU ──
const BU_DATA: BuListItem[] = [
  { id:'bu-01', substrate_id:'sub-capital',  book_title:'《资本论》',       summary:'AII 综合:以劳动价值论为核心,推导剩余价值与资本积累规律的政治经济学体系。', grade:'low',        main_claim_count:6 },
  { id:'bu-02', substrate_id:'sub-keynes',   book_title:'《通论》',         summary:'AII 综合:挑战古典充分就业假设,提出有效需求不足导致非自愿失业。', grade:'moderate', main_claim_count:5 },
  { id:'bu-03', substrate_id:'sub-kahneman', book_title:'《思考,快与慢》', summary:'AII 综合:双系统认知框架及其引发的系统性判断偏差。', grade:'moderate', main_claim_count:7 },
];
export async function mockBuList(): Promise<ApiResult<BuListItem[]>> {
  await delay(220);
  const more = Array.from({ length: 8 }, (_, i) => ({
    id:`bu-${String(i+4).padStart(2,'0')}`,
    substrate_id:`sub-${i+4}`,
    book_title:`书籍 ${i+4}`,
    summary:'AII 综合的书级理解摘要。',
    grade:(i%2===0?'unverified':'low') as EpistemicGrade,
    main_claim_count: 3 + (i%4),
  }));
  return { ok:true, degraded:false, data: [...BU_DATA, ...more] };
}
export async function mockBuDetail(id: string): Promise<ApiResult<BuDetail>> {
  await delay(240);
  const base = BU_DATA.find(b => b.id === id) ?? BU_DATA[0];
  return {
    ok:true, degraded:false,
    data: {
      ...base, id,
      main_claims: [
        { id:'mc1', text:'商品价值的实体是抽象人类劳动。', stance_marker:'《资本论》主张', claim_grade:'low' },
        { id:'mc2', text:'资本家无偿占有工人创造的剩余价值。', stance_marker:'《资本论》主张', claim_grade:'low' },
        { id:'mc3', text:'资本积累必然导致利润率趋于下降。', stance_marker:'《资本论》主张', claim_grade:'contradicted' },
      ],
      argument_structure: [
        {
          id:'arg1', thesis:'剩余价值来源于劳动力商品的特殊使用价值。', thesis_grade:'low',
          evidence: [
            { text:'劳动力价值由再生产其所需生活资料决定。', grade:'moderate' },
            { text:'劳动过程创造的价值大于劳动力自身价值。', grade:'low' },
            { text:'(经验证据薄弱)历史工资数据的解释力存疑。', grade:'unverified' },
          ],
        },
        {
          id:'arg2', thesis:'利润率下降是资本有机构成提高的结果。', thesis_grade:'contradicted',
          evidence: [
            { text:'技术进步提高不变资本占比。', grade:'moderate' },
            { text:'(反证)反事实:技术也提升剩余价值率,可抵消。', grade:'low' },
          ],
        },
      ],
      structure: [
        { title:'第一卷 资本的生产过程', children:[{ title:'商品与货币' }, { title:'剩余价值的生产' }] },
        { title:'第二卷 资本的流通过程' },
        { title:'第三卷 资本主义生产的总过程' },
      ],
      key_concepts: [
        { ku_id:'ku-00001', label:'社会必要劳动时间', grade:'proven' },
        { ku_id:'ku-00019', label:'剩余价值', grade:'low' },
        { ku_id:'ku-00031', label:'资本有机构成', grade:'unverified' },
      ],
    },
  };
}
