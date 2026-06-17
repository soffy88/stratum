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
} from '@/types/api';

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
