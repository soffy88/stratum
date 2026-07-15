"use client";

// AII 学习助手模块 — 学习档案详情: 诊断 → 计划 → 学习循环(提交任务/裁判) → 监督(复习队列/卡点库)。
import { useEffect, useState, useCallback, use as usePromise } from "react";

interface DiagnoseQuestion { id: number; topic: string; question: string; }
interface DiagnoseVerdict {
  per_question?: { id: number; level: string; issues: string }[];
  real_starting_point?: string;
  gaps?: string[];
}
interface PlanStage {
  stage: number; content: string; tasks: string; deliverable: string; acceptance: string; est_weeks: string;
}
interface PlanCapability { capability: string; priority: number; skippable: boolean; }
interface Plan {
  plan_id: number;
  stages: PlanStage[];
  capabilities: PlanCapability[];
  reality_check?: string;
  first_week_plan?: string;
  tools?: string;
  common_mistakes?: string;
  today_task?: string;
  status: string;
}
interface ProgressPoint {
  point_id: number; point_name: string; grade: string; verified_by: string | null;
  mastery_score: number; knowledge_type: string | null;
  next_review_at: string | null; last_tested_at: string | null;
  attempts: { ts: string; type: string; passed: boolean; verdict: { issues?: string[]; feedback?: string } }[];
}
interface StuckItem {
  stuck_id: number; point_name: string; stuck_pattern: string; occurrences: number; resolved: boolean;
  error_type: string | null;
}
interface NextObjective {
  done?: boolean; empty?: boolean; waiting?: boolean; reason?: string;
  action?: "code" | "feynman" | "derivation" | "quiz";
  prompt?: string; quiz_question?: string; next_review_at?: string | null;
  objective?: { point_id: number; point_name: string; knowledge_type: string | null; grade: string; mastery_score: number };
}
const ERROR_LABEL: Record<string, string> = {
  knowledge_structural: "知识结构缺失", understanding_deviation: "理解偏差",
  application_error: "应用错误", metacognitive: "元认知",
};
interface KuRow {
  ku_id: string; point: string | null; natural_text_zh: string | null;
  natural_text: string | null; zh_grade: string | null; sources: string[];
}
interface Profile {
  profile_id: number; subject: string; goal: string; main_textbook: string;
  real_starting_point: DiagnoseVerdict | null; gaps: string[] | null;
}
interface Detail {
  profile: Profile; plan: Plan | null; progress: ProgressPoint[]; stuck: StuckItem[];
}

const GRADE_COLOR: Record<string, string> = {
  unverified: "text-gray-400", learning: "text-amber-600", verified: "text-green-600",
};

export default function LearningProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = usePromise(params);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [err, setErr] = useState(false);
  const [busy, setBusy] = useState("");

  // 诊断流程状态
  const [questions, setQuestions] = useState<DiagnoseQuestion[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [diagnoseResult, setDiagnoseResult] = useState<DiagnoseVerdict | null>(null);

  // 新任务表单
  const [newPointName, setNewPointName] = useState("");
  const [activePointId, setActivePointId] = useState<number | null>(null);
  const [submission, setSubmission] = useState("");
  const [submissionType, setSubmissionType] = useState<"auto" | "derivation" | "feynman" | "code">("auto");
  const [expectedStdout, setExpectedStdout] = useState("");
  const [lastVerdict, setLastVerdict] = useState<any>(null);

  // 自动生成知识点 (P1.2)
  const [genScope, setGenScope] = useState("");

  // 托管答案速测 (P1.3)
  const [quizPointId, setQuizPointId] = useState<number | null>(null);
  const [quizQuestion, setQuizQuestion] = useState("");
  const [quizAnswer, setQuizAnswer] = useState("");
  const [quizVerdict, setQuizVerdict] = useState<any>(null);

  // 主动督学 (P2.2)
  // 统一学习教练对话入口 (3O oskill learning_coach_turn)
  interface CoachMsg { role: "coach" | "student"; text: string; verdict?: any; objective?: string; kt?: string | null; }
  const [coachMsgs, setCoachMsgs] = useState<CoachMsg[]>([]);
  const [coachInput, setCoachInput] = useState("");
  const [coachAction, setCoachAction] = useState<string>("");  // 上一回合的 action, 决定下次是否交裁判
  const coachAwaitingAnswer = coachAction === "present" || coachAction === "remediate";

  // KU 中文显示 / 知识底座 (§1.4)
  const [kuPointId, setKuPointId] = useState<number | null>(null);
  const [kuRows, setKuRows] = useState<KuRow[] | null>(null);
  const [kuShowEn, setKuShowEn] = useState<Record<string, boolean>>({});
  const [correctingKu, setCorrectingKu] = useState<string | null>(null);
  const [correctText, setCorrectText] = useState("");

  const load = useCallback(() => {
    fetch(`/api/aii/api/learning/profiles/${id}`)
      .then((r) => r.json())
      .then((d) => { setDetail(d?.data ?? null); setErr(false); })
      .catch(() => setErr(true));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const generateDiagnose = async () => {
    setBusy("diagnose-gen");
    try {
      const r = await fetch(`/api/aii/api/learning/profiles/${id}/diagnose/generate`, { method: "POST" });
      const d = await r.json();
      setQuestions(d?.data?.questions ?? []);
      setAnswers({});
    } finally { setBusy(""); }
  };

  const submitDiagnose = async () => {
    if (!questions) return;
    setBusy("diagnose-submit");
    try {
      const r = await fetch(`/api/aii/api/learning/profiles/${id}/diagnose/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions, answers }),
      });
      const d = await r.json();
      setDiagnoseResult(d?.data ?? null);
      load();
    } finally { setBusy(""); }
  };

  const generatePlan = async () => {
    setBusy("plan-gen");
    try {
      await fetch(`/api/aii/api/learning/profiles/${id}/plan/generate`, { method: "POST" });
      load();
    } finally { setBusy(""); }
  };

  const createTask = async () => {
    if (!newPointName.trim()) return;
    setBusy("task-create");
    try {
      const r = await fetch(`/api/aii/api/learning/profiles/${id}/progress`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ point_name: newPointName }),
      });
      const d = await r.json();
      setActivePointId(d?.data?.point_id ?? null);
      setNewPointName("");
      load();
    } finally { setBusy(""); }
  };

  const submitTask = async () => {
    if (!activePointId || !submission.trim()) return;
    setBusy("task-submit");
    setLastVerdict(null);
    try {
      const r = await fetch(`/api/aii/api/learning/progress/${activePointId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submission,
          submission_type: submissionType === "auto" ? null : submissionType,
          expected_stdout: submissionType === "code" && expectedStdout ? expectedStdout : null,
        }),
      });
      const d = await r.json();
      setLastVerdict(d?.data ?? null);
      setSubmission("");
      load();
    } finally { setBusy(""); }
  };

  const resolveStuck = async (stuckId: number) => {
    await fetch(`/api/aii/api/learning/stuck/${stuckId}/resolve`, { method: "POST" });
    load();
  };

  const fetchKus = async (pointId: number) => {
    if (kuPointId === pointId) { setKuPointId(null); setKuRows(null); return; }  // 再点收起
    setKuPointId(pointId); setKuRows(null); setBusy("kus");
    try {
      const r = await fetch(`/api/aii/api/learning/progress/${pointId}/kus`);  // 首次会按需翻译, 可能慢
      const d = await r.json();
      setKuRows(d?.data ?? []);
    } finally { setBusy(""); }
  };

  const correctKuZh = async (kuId: string) => {
    if (!correctText.trim()) return;
    setBusy("correct");
    try {
      await fetch(`/api/aii/api/learning/kus/${kuId}/correct-zh`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ corrected_zh: correctText }),
      });
      // 本地更新这条 KU 的显示(译文+grade), 不重新触发翻译
      setKuRows((rows) => rows?.map((k) => k.ku_id === kuId ? { ...k, natural_text_zh: correctText, zh_grade: "verified" } : k) ?? null);
      setCorrectingKu(null); setCorrectText("");
    } finally { setBusy(""); }
  };

  const generatePoints = async () => {
    // 输入章节号(如 "1,2" 或 "1-3"), 解析成章节数组
    const chapters = Array.from(new Set(
      genScope.split(/[,，、\s]+/).flatMap((tok) => {
        const range = tok.match(/^(\d+)-(\d+)$/);
        if (range) { const a = +range[1]!, b = +range[2]!; return Array.from({ length: b - a + 1 }, (_, i) => a + i); }
        const n = parseInt(tok, 10); return isNaN(n) ? [] : [n];
      })
    ));
    if (!chapters.length) return;
    setBusy("gen-points");
    try {
      await fetch(`/api/aii/api/learning/profiles/${id}/generate-points`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapters }),
      });
      setGenScope("");
      load();
    } finally { setBusy(""); }
  };

  const coachTurn = async (studentText: string | null, submitAnswer: boolean) => {
    setBusy("coach");
    const history = coachMsgs.map((m) => ({ role: m.role === "coach" ? "assistant" : "user", content: m.text }));
    const nextMsgs = studentText ? [...coachMsgs, { role: "student" as const, text: studentText }] : coachMsgs;
    if (studentText) setCoachMsgs(nextMsgs);
    setCoachInput("");
    try {
      const r = await fetch(`/api/aii/api/learning/profiles/${id}/tutor/turn`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_input: studentText, submit_answer: submitAnswer, history }),
      });
      const d = await r.json();
      const data = d?.data ?? {};
      setCoachAction(data.action ?? "");
      setCoachMsgs((m) => [...m, {
        role: "coach", text: data.message ?? "(无回复)",
        verdict: data.verdict, objective: data.objective?.point_name, kt: data.knowledge_type,
      }]);
      load();  // 刷新进度表/掌握度
    } finally { setBusy(""); }
  };

  const poseQuiz = async (pointId: number) => {
    setBusy("quiz-pose");
    setQuizVerdict(null); setQuizAnswer(""); setQuizQuestion("");
    try {
      const r = await fetch(`/api/aii/api/learning/progress/${pointId}/quiz`, { method: "POST" });
      const d = await r.json();
      setQuizPointId(pointId);
      setQuizQuestion(d?.data?.question ?? "");
    } finally { setBusy(""); }
  };

  const answerQuiz = async () => {
    if (!quizPointId || !quizAnswer.trim()) return;
    setBusy("quiz-answer");
    try {
      const r = await fetch(`/api/aii/api/learning/progress/${quizPointId}/quiz-answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: quizAnswer }),
      });
      const d = await r.json();
      setQuizVerdict(d?.data ?? null);
      load();
    } finally { setBusy(""); }
  };

  if (err) return <div className="p-6 text-red-600 text-sm">无法连接 AII 后端 /api/learning/profiles/{id}</div>;
  if (!detail) return <div className="p-6 text-[var(--color-muted)]">加载中…</div>;

  const { profile, plan, progress, stuck } = detail;
  const dueReview = progress.filter((p) => p.next_review_at && new Date(p.next_review_at) <= new Date());

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold">{profile.subject}</h1>
        {profile.goal && <p className="text-sm text-[var(--color-muted)] mt-1">{profile.goal}</p>}
        <p className="text-xs text-[var(--color-muted)] mt-1 font-mono">{profile.main_textbook}</p>
      </div>

      {/* ── 诊断 ── */}
      {!profile.real_starting_point ? (
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-medium mb-2">① 诊断真实起点</h2>
          <p className="text-sm text-[var(--color-muted)] mb-3">
            不信自评——出诊断题实测你真实的前置能力水位。回答时不要查资料/不用AI，卡住的地方直接写&quot;不懂&quot;。
          </p>
          {!questions ? (
            <button
              disabled={!!busy}
              onClick={generateDiagnose}
              className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
            >
              {busy === "diagnose-gen" ? "出题中…" : "开始诊断"}
            </button>
          ) : (
            <div className="space-y-4">
              {questions.map((q) => (
                <div key={q.id}>
                  <div className="text-sm font-medium mb-1">
                    {q.id}. [{q.topic}] {q.question}
                  </div>
                  <textarea
                    value={answers[q.id] ?? ""}
                    onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                    placeholder="你的回答(不会就写'不懂')…"
                    rows={2}
                    className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-transparent"
                  />
                </div>
              ))}
              <button
                disabled={!!busy}
                onClick={submitDiagnose}
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
              >
                {busy === "diagnose-submit" ? "裁判判定中…" : "提交诊断"}
              </button>
              {diagnoseResult && (
                <div className="mt-3 p-3 rounded bg-[var(--color-border)]/30 text-sm">
                  <div className="font-medium mb-1">真实起点评估</div>
                  <p className="text-[var(--color-muted)]">{diagnoseResult.real_starting_point}</p>
                  {diagnoseResult.gaps && diagnoseResult.gaps.length > 0 && (
                    <ul className="list-disc pl-5 mt-2 text-[var(--color-muted)]">
                      {diagnoseResult.gaps.map((g, i) => <li key={i}>{g}</li>)}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-medium mb-2">① 真实起点(已诊断)</h2>
          <p className="text-sm text-[var(--color-muted)]">
            {profile.real_starting_point.real_starting_point}
          </p>
          {profile.gaps && profile.gaps.length > 0 && (
            <ul className="list-disc pl-5 mt-2 text-sm text-[var(--color-muted)]">
              {profile.gaps.map((g, i) => <li key={i}>{g}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* ── 计划 ── */}
      {profile.real_starting_point && (
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-medium mb-2">② 学习计划</h2>
          {!plan ? (
            <button
              disabled={!!busy}
              onClick={generatePlan}
              className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
            >
              {busy === "plan-gen" ? "生成中…" : "生成学习计划"}
            </button>
          ) : (
            <div className="space-y-3 text-sm">
              {plan.reality_check && (
                <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30">
                  <span className="font-medium">目标现实性评估：</span>{plan.reality_check}
                </div>
              )}
              {plan.today_task && (
                <div className="p-2 rounded bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30">
                  <span className="font-medium">今天可执行任务：</span>{plan.today_task}
                </div>
              )}
              <div className="flex flex-col gap-1">
                {plan.stages?.map((s) => (
                  <div key={s.stage} className="border border-[var(--color-border)] rounded p-2">
                    <div className="font-medium">阶段{s.stage}: {s.content} <span className="text-xs text-[var(--color-muted)]">({s.est_weeks}周)</span></div>
                    <div className="text-xs text-[var(--color-muted)] mt-1">成果: {s.deliverable} · 验收: {s.acceptance}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── 复习队列 ── */}
      {dueReview.length > 0 && (
        <div className="border border-amber-500/50 bg-amber-500/10 rounded-lg p-4">
          <h2 className="font-medium mb-2">⏰ 该复习了({dueReview.length})</h2>
          <ul className="text-sm space-y-1">
            {dueReview.map((p) => (
              <li key={p.point_id}>{p.point_name} <span className="text-xs text-[var(--color-muted)]">(上次: {p.last_tested_at?.slice(0, 10)})</span></li>
            ))}
          </ul>
        </div>
      )}

      {/* ── AI 学习教练 (统一入口, 3O oskill 驱动) ── */}
      {plan && (
        <div className="border border-[var(--color-primary)]/40 bg-[var(--color-primary)]/5 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-medium">🎓 AI 学习教练</h2>
            {coachMsgs.length === 0 && (
              <button disabled={!!busy} onClick={() => coachTurn(null, false)}
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40">
                {busy === "coach" ? "…" : "开始学习"}
              </button>
            )}
          </div>
          {coachMsgs.length === 0 && (
            <p className="text-sm text-[var(--color-muted)]">点&quot;开始学习&quot;，教练会按你的掌握状态带你逐个知识点学：讲清→布置任务→裁判判定真掌握→推进。用对话就行。</p>
          )}
          {coachMsgs.length > 0 && (
            <div className="space-y-2">
              <div className="max-h-96 overflow-y-auto space-y-2 pr-1">
                {coachMsgs.map((m, i) => (
                  <div key={i} className={`flex ${m.role === "student" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] px-3 py-2 rounded-lg text-sm ${m.role === "student" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-card,white)] border border-[var(--color-border)]"}`}>
                      {m.role === "coach" && m.objective && (
                        <div className="text-[10px] text-[var(--color-muted)] mb-1 font-mono">目标: {m.objective}{m.kt ? ` · ${m.kt}` : ""}</div>
                      )}
                      <div className="whitespace-pre-wrap">{m.text}</div>
                      {m.verdict && (
                        <div className={`mt-1 text-[10px] px-1.5 py-0.5 rounded inline-block ${m.verdict.passed ? "bg-green-500/20 text-green-700" : "bg-red-500/15 text-red-700"}`}>
                          {m.verdict.passed ? "✓ 通过" : "✗ 未过"} · {m.verdict.grade} · 掌握度 {Math.round((m.verdict.mastery_score ?? 0) * 100)}%
                          {m.verdict.error_label ? ` · ${m.verdict.error_label}` : ""}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {busy === "coach" && <div className="text-xs text-[var(--color-muted)]">教练思考中…（首次讲解会翻译知识点，可能要几十秒）</div>}
              </div>
              {coachAction !== "done" && (
                <div className="space-y-1.5">
                  {coachAwaitingAnswer && (
                    <div className="text-[11px] text-amber-600">↓ 这是要判分的作答——独立写，裁判会判你是否真掌握（不能撒谎）</div>
                  )}
                  <textarea
                    value={coachInput}
                    onChange={(e) => setCoachInput(e.target.value)}
                    placeholder={coachAwaitingAnswer ? "写出你的作答/讲解/推导/代码…" : "回复教练…"}
                    rows={coachAwaitingAnswer ? 4 : 2}
                    className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-transparent"
                  />
                  <div className="flex gap-2">
                    <button
                      disabled={!!busy || !coachInput.trim()}
                      onClick={() => coachTurn(coachInput, coachAwaitingAnswer)}
                      className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
                    >{busy === "coach" ? "…" : coachAwaitingAnswer ? "提交作答(交裁判)" : "发送"}</button>
                    {coachAwaitingAnswer && (
                      <button disabled={!!busy} onClick={() => coachTurn(coachInput || "我先问个问题：", false)}
                        className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)] disabled:opacity-40"
                        title="不判分, 只问教练">问教练</button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── 学习循环: 提交任务 ── */}
      {plan && (
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-medium mb-2">③ 手动提交任务(裁判判定)</h2>
          <div className="mb-3 p-2.5 rounded bg-[var(--color-border)]/25">
            <div className="text-xs text-[var(--color-muted)] mb-1.5">按主教材章节结构生成学习点(逐小节, 书中顺序, KU挂到对应小节)：</div>
            <div className="flex gap-2">
              <input
                value={genScope}
                onChange={(e) => setGenScope(e.target.value)}
                placeholder="章节号, 如: 1,2 或 1-3"
                className="flex-1 px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-transparent"
              />
              <button
                disabled={!!busy || !genScope.trim()}
                onClick={generatePoints}
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40 shrink-0"
              >{busy === "gen-points" ? "生成中…" : "自动生成"}</button>
            </div>
          </div>
          <div className="flex gap-2 mb-3">
            <input
              value={newPointName}
              onChange={(e) => setNewPointName(e.target.value)}
              placeholder="或手动新建知识点(如: 数列极限唯一性证明)"
              className="flex-1 px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-transparent"
            />
            <button
              disabled={!!busy || !newPointName.trim()}
              onClick={createTask}
              className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)] disabled:opacity-40"
            >新建知识点</button>
          </div>
          {activePointId && (
            <div className="space-y-2">
              <div className="flex gap-3 text-sm flex-wrap">
                <label className="flex items-center gap-1">
                  <input type="radio" checked={submissionType === "auto"} onChange={() => setSubmissionType("auto")} />
                  自动(按知识类型)
                </label>
                <label className="flex items-center gap-1">
                  <input type="radio" checked={submissionType === "derivation"} onChange={() => setSubmissionType("derivation")} />
                  推导/证明(严格裁判)
                </label>
                <label className="flex items-center gap-1">
                  <input type="radio" checked={submissionType === "feynman"} onChange={() => setSubmissionType("feynman")} />
                  讲解(Feynman门)
                </label>
                <label className="flex items-center gap-1">
                  <input type="radio" checked={submissionType === "code"} onChange={() => setSubmissionType("code")} />
                  代码(真实执行)
                </label>
              </div>
              <textarea
                value={submission}
                onChange={(e) => setSubmission(e.target.value)}
                placeholder={submissionType === "code" ? "粘贴Python代码…" : "写出你的独立推导/证明…(自动模式会按该点的知识类型选裁判)"}
                rows={6}
                className="w-full px-3 py-2 text-sm font-mono rounded border border-[var(--color-border)] bg-transparent"
              />
              {submissionType === "code" && (
                <input
                  value={expectedStdout}
                  onChange={(e) => setExpectedStdout(e.target.value)}
                  placeholder="期望的stdout输出(可选, 不填只看代码能否正常跑完)"
                  className="w-full px-3 py-2 text-sm font-mono rounded border border-[var(--color-border)] bg-transparent"
                />
              )}
              <button
                disabled={!!busy || !submission.trim()}
                onClick={submitTask}
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
              >
                {busy === "task-submit" ? "裁判判定中…" : "提交给裁判"}
              </button>
              {lastVerdict && (
                <div className={`p-3 rounded text-sm border ${lastVerdict.passed ? "border-green-500/40 bg-green-500/10" : "border-red-500/40 bg-red-500/10"}`}>
                  <div className="font-medium flex items-center gap-2 flex-wrap">
                    <span>{lastVerdict.passed ? "✓ 本次通过" : "✗ 未通过"}</span>
                    <span className="text-xs font-normal px-1.5 py-0.5 rounded bg-[var(--color-border)]/50">裁判: {lastVerdict.judge}</span>
                    <span className="text-xs font-normal px-1.5 py-0.5 rounded bg-[var(--color-border)]/50">掌握度 {Math.round((lastVerdict.mastery_score ?? 0) * 100)}%</span>
                    <span className={`text-xs font-normal px-1.5 py-0.5 rounded ${lastVerdict.grade === "verified" ? "bg-green-500/20 text-green-700" : "bg-amber-500/15 text-amber-700"}`}>{lastVerdict.grade}</span>
                    {lastVerdict.error_type && <span className="text-xs font-normal px-1.5 py-0.5 rounded bg-red-500/15 text-red-700">{ERROR_LABEL[lastVerdict.error_type] ?? lastVerdict.error_type}</span>}
                  </div>
                  {lastVerdict.reason && <p className="mt-1 text-[var(--color-muted)]">{lastVerdict.reason}</p>}
                  {lastVerdict.remediation && <p className="mt-1 text-[var(--color-muted)]">补救: {lastVerdict.remediation}</p>}
                  {lastVerdict.verdict?.issues?.length > 0 && (
                    <ul className="list-disc pl-5 mt-1">
                      {lastVerdict.verdict.issues.map((x: string, i: number) => <li key={i}>{x}</li>)}
                    </ul>
                  )}
                  {lastVerdict.verdict?.feedback && <p className="mt-1 text-[var(--color-muted)]">{lastVerdict.verdict.feedback}</p>}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── 进度表 ── */}
      {progress.length > 0 && (
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-medium mb-2">④ 进度表</h2>
          <div className="space-y-1 text-sm">
            {progress.map((p) => (
              <div key={p.point_id} className="flex items-center gap-2 py-1.5 border-b border-[var(--color-border)]/50 last:border-0">
                <span className="truncate flex-1">{p.point_name}</span>
                {p.knowledge_type && (
                  <span className="text-[10px] shrink-0 px-1.5 py-0.5 rounded bg-[var(--color-border)]/40 text-[var(--color-muted)] font-mono">{p.knowledge_type}</span>
                )}
                <button
                  onClick={() => fetchKus(p.point_id)}
                  disabled={!!busy}
                  className={`text-[11px] shrink-0 px-1.5 py-0.5 rounded border disabled:opacity-40 ${kuPointId === p.point_id ? "border-[var(--color-primary)] text-[var(--color-primary)]" : "border-[var(--color-border)]"}`}
                  title="看这个知识点的 B仓 KU 底座(中文译文+英文原文+多出处)"
                >底座</button>
                <button
                  onClick={() => poseQuiz(p.point_id)}
                  disabled={!!busy}
                  className="text-[11px] shrink-0 px-1.5 py-0.5 rounded border border-[var(--color-border)] disabled:opacity-40"
                  title="出一道题, 标准答案存服务端, 判分不放水"
                >速测</button>
                <div className="w-16 h-1.5 rounded bg-[var(--color-border)] overflow-hidden shrink-0" title={`掌握度 ${Math.round((p.mastery_score ?? 0) * 100)}%`}>
                  <div className={`h-full ${p.grade === "verified" ? "bg-green-500" : "bg-amber-500"}`} style={{ width: `${Math.min(100, Math.round((p.mastery_score ?? 0) * 100))}%` }} />
                </div>
                <span className={`text-xs shrink-0 w-16 text-right ${GRADE_COLOR[p.grade] ?? ""}`}>{p.grade}</span>
              </div>
            ))}
          </div>

          {/* ── 知识底座 (§1.4): B仓 KU 中文显示 ── */}
          {kuPointId !== null && (
            <div className="mt-3 p-3 rounded border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5">
              <div className="text-xs text-[var(--color-muted)] mb-2">知识底座(B仓去重增强 KU · 中文译文术语受控 · 原文永不丢)</div>
              {busy === "kus" && !kuRows && <p className="text-sm text-[var(--color-muted)]">加载中…(首次会本地翻译，可能要几十秒)</p>}
              {kuRows && kuRows.length === 0 && <p className="text-sm text-[var(--color-muted)]">这个知识点没有挂靠 B仓 KU。</p>}
              <div className="space-y-3">
                {kuRows?.map((k) => (
                  <div key={k.ku_id} className="text-sm border-b border-[var(--color-border)]/40 pb-2 last:border-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      {k.point && <span className="font-medium">{k.point}</span>}
                      {k.zh_grade && <span className={`text-[10px] px-1.5 py-0.5 rounded ${k.zh_grade === "verified" ? "bg-green-500/20 text-green-700" : "bg-amber-500/15 text-amber-700"}`}>译文 {k.zh_grade}</span>}
                      {k.sources.length > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-border)]/40 text-[var(--color-muted)] font-mono">{k.sources.length} 出处</span>}
                    </div>
                    <p>{kuShowEn[k.ku_id] ? k.natural_text : k.natural_text_zh}</p>
                    <div className="flex gap-3 mt-1 text-xs">
                      <button className="text-[var(--color-primary)]" onClick={() => setKuShowEn((s) => ({ ...s, [k.ku_id]: !s[k.ku_id] }))}>
                        {kuShowEn[k.ku_id] ? "看中文译文" : "看英文原文"}
                      </button>
                      <button className="text-[var(--color-muted)]" onClick={() => { setCorrectingKu(correctingKu === k.ku_id ? null : k.ku_id); setCorrectText(k.natural_text_zh ?? ""); }}>
                        译文有误?修正
                      </button>
                    </div>
                    {correctingKu === k.ku_id && (
                      <div className="mt-1.5">
                        <textarea value={correctText} onChange={(e) => setCorrectText(e.target.value)} rows={2}
                          className="w-full px-2 py-1.5 text-sm rounded border border-[var(--color-border)] bg-transparent" />
                        <button disabled={!!busy} onClick={() => correctKuZh(k.ku_id)}
                          className="mt-1 px-2 py-1 text-xs rounded bg-[var(--color-primary)] text-white disabled:opacity-40">保存(升为 verified)</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {quizQuestion && (
            <div className="mt-3 p-3 rounded border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5 text-sm">
              <div className="font-medium mb-1">速测题(标准答案已存服务端)</div>
              <p className="mb-2">{quizQuestion}</p>
              <textarea
                value={quizAnswer}
                onChange={(e) => setQuizAnswer(e.target.value)}
                placeholder="你的作答…"
                rows={2}
                className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-transparent"
              />
              <button
                disabled={!!busy || !quizAnswer.trim()}
                onClick={answerQuiz}
                className="mt-2 px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
              >{busy === "quiz-answer" ? "判分中…" : "提交作答"}</button>
              {quizVerdict && (
                <div className={`mt-2 p-2 rounded border ${quizVerdict.passed ? "border-green-500/40 bg-green-500/10" : "border-red-500/40 bg-red-500/10"}`}>
                  <span className="font-medium">{quizVerdict.passed ? "✓ 通过" : "✗ 未通过"}</span>
                  <span className="text-xs ml-2 text-[var(--color-muted)]">{quizVerdict.grade} · 掌握度 {Math.round((quizVerdict.mastery_score ?? 0) * 100)}%</span>
                  {quizVerdict.verdict?.issues?.length > 0 && (
                    <ul className="list-disc pl-5 mt-1">{quizVerdict.verdict.issues.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── 卡点库 ── */}
      {stuck.filter((s) => !s.resolved).length > 0 && (
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-medium mb-2">⑤ 卡点库</h2>
          <div className="space-y-2 text-sm">
            {stuck.filter((s) => !s.resolved).map((s) => (
              <div key={s.stuck_id} className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium flex items-center gap-2">
                    {s.point_name} <span className="text-xs text-amber-600">×{s.occurrences}</span>
                    {s.error_type && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-700 font-mono">{ERROR_LABEL[s.error_type] ?? s.error_type}</span>}
                  </div>
                  <div className="text-xs text-[var(--color-muted)]">{s.stuck_pattern}</div>
                </div>
                <button
                  onClick={() => resolveStuck(s.stuck_id)}
                  className="text-xs px-2 py-1 rounded border border-[var(--color-border)] shrink-0"
                >已解决</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
