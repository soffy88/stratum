// 书名清洗 + 科目分类（纯前端，依赖 title + meta_json.author，无额外 API 调用）

const ZLIB_RE = /\s+\([^)]*(?:z-lib|z-library|1lib|zlibrary)[^)]*\)/gi;

export function cleanTitle(raw: string | null | undefined): string {
  if (!raw) return '';
  let s = raw.replace(ZLIB_RE, '').trim();
  // 删末尾人名/机构括号，保护版本号 / 上下册
  s = s.replace(/\s+[\(（]([^)）]{1,40})[\)）]\s*$/, (_m, inner: string) => {
    if (/[0-9]|第.{1,3}[版卷册]|^[上下]册?$|《|》/.test(inner)) return _m;
    return '';
  });
  return s.trim();
}

export type Subject = '数学' | '科学' | '经济金融' | '哲学' | '社科心理' | '量化与AI';
export const ALL_SUBJECTS: Subject[] = ['数学', '科学', '经济金融', '哲学', '社科心理', '量化与AI'];

type Rule = [Subject, string[], string[]];
const RULES: Rule[] = [
  ['数学', [
    '数学','微积分','代数','拓扑','泛函','分析学','实分析','复分析','概率论','统计学',
    '几何','数论','集合论','线性代数','离散数学','组合数学','数理逻辑','运筹学',
    '方程','矩阵','证明','定理','公理','数列','极限','最优化','优化理论',
  ], [
    'calculus','algebra','topology','analysis','mathematics','mathematical',
    'stochastic process','random process','discrete math','linear algebra',
    'differential equation','probability theory','number theory','geometry',
    'combinatorics','optimization','theorem','matrix',
  ]],
  ['科学', [
    '物理','化学','生物','天文','力学','量子','热力学','神经科学','认知科学',
    '进化','基因','细胞','宇宙','相对论',
  ], [
    'physics','chemistry','biology','astronomy','neuroscience','cognitive science',
    'quantum','thermodynamics','evolution','genetics','relativity',
  ]],
  ['经济金融', [
    '经济','金融','货币','财政','宏观','微观','资产','投资','银行','股票',
    '债券','利率','贸易','财富','市场','价格','供给','需求','通货膨胀',
    '贫穷','增长','资本','套利','期权','期货','风险管理',
    '经济學','金融學',
  ], [
    'economics','finance','monetary','fiscal','asset','investment',
    'portfolio','equity','interest rate','bond','stock market',
    'econometrics','wealth','inflation','poverty','federal reserve',
  ]],
  ['哲学', [
    '哲学','伦理','认识论','形而上','逻辑学','道德','真理','存在','意识','知识论',
    '辩证','现象学','维特根斯坦','康德','黑格尔','柏拉图','亚里士多德','波兰尼','尼采',
    '孔子','老子','庄子','孟子',
    '哲學','倫理','邏輯',
  ], [
    'philosophy','ethics','epistemology','metaphysics','kant','hegel',
    'plato','aristotle','wittgenstein','nietzsche','phenomenology','ontology','morality',
  ]],
  ['社科心理', [
    '社会学','心理学','行为学','人类学','政治学','认知偏差','偏见','文化',
    '记忆','情绪','决策','习惯','影响力','说服','沟通','组织行为',
    '领导力','学习方法','教育','行为经济学',
    '行為經濟學','心理學','社會學',
  ], [
    'psychology','sociology','anthropology','political science',
    'behavioral economics','cognitive bias','decision making',
    'persuasion','communication','leadership','learning','education',
  ]],
  ['量化与AI', [
    '机器学习','深度学习','人工智能','算法交易','量化投资','量化金融','神经网络',
    '自然语言处理','强化学习','数据科学','计算机视觉','大语言模型',
  ], [
    'machine learning','deep learning','artificial intelligence','neural network',
    'quantitative finance','algorithmic trading','natural language processing',
    'reinforcement learning','data science','computer vision',
    'large language model','transformer',
  ]],
];

export function classifySubstrate(title: string, author?: string): Subject[] {
  const text = (cleanTitle(title) + ' ' + (author ?? '')).toLowerCase();
  const matched: Subject[] = [];
  for (const [subj, zhKws, enKws] of RULES) {
    if (zhKws.some(kw => text.includes(kw)) || enKws.some(kw => text.includes(kw))) {
      matched.push(subj);
    }
  }
  return matched;
}
