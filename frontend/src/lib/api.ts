/* API 6本。表を上書きする関数は存在しない（サーバ側にも無い）。 */
import type {
  Bootstrap, Candidate, Edit, Grid, Rule, SolveResult, Stage, TranslateResult, Ward,
} from './types'

const WID = 'w1'

class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}

async function call<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const res = await fetch(path, {
    method: method ?? (body === undefined ? 'GET' : 'POST'),
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().then(j => j.detail).catch(() => null)
    throw new ApiError(detail ?? `HTTP ${res.status}`, res.status)
  }
  return res.json() as Promise<T>
}

export const api = {
  /** 1 画面が1回で取るもの。ブラウザは Firestore を直接触らない */
  bootstrap: (month: string) =>
    call<Bootstrap>(`/api/ward/${WID}/month/${month}`),

  /** 2 求解は常にソルバー。夜勤 → 日勤の二段階 */
  solve: (month: string, stage: Stage, opts?: { days?: number; first_weekday?: number; seed?: number }) =>
    call<SolveResult>(`/api/ward/${WID}/month/${month}/solve`, { stage, ...opts }),

  /** 3 手修正。1セル1件、追記のみ */
  addEdit: (month: string, nurse_id: string, day: number, to: string | null) =>
    call<{ edit: Edit; current: Grid; rejected: number }>(
      `/api/ward/${WID}/month/${month}/edits`, { nurse_id, day, to }),

  /** 4 確定（来歴つき）／止める・延ばす */
  confirmRule: (rule: Rule, expires_on: string | null) =>
    call<{ rule: Rule }>(`/api/ward/${WID}/rules`,
      { rule, expires_on, approved_by: '師長' }),
  patchRule: (id: string, body: { stopped?: boolean; expires_on?: string | null }) =>
    call<{ rule: Rule }>(`/api/ward/${WID}/rules/${id}`, body, 'PATCH'),

  /** 5 セル1つ ＋ 言葉 → 制約候補1本。範囲は師長が選ぶ */
  translate: (input: {
    nurse_id: string; month: string; day: number; weekday: number; kind: string; text: string
  }) => call<TranslateResult>(`/api/ward/${WID}/translate`, input),

  /** 6 段階0の出口 */
  putWard: (ward: Ward) => call<{ ward_id: string }>('/api/ward', ward),

  /** 段階0 過去の表を取り込む。手で作られたものなので提案は持たない */
  importSample: () =>
    call<{ month: string; nurses: number; days: number }>(`/api/ward/${WID}/import/sample`, {}),
  importMonth: (body: {
    month: string; days: number; first_weekday: number; cells: Record<string, (string | null)[]>
  }) => call<{ month: string }>(`/api/ward/${WID}/import`, body),

  /** 段階0 数えた事実と選択肢。作りはしない */
  candidates: (month: string) =>
    call<{ month: string; candidates: Candidate[] }>(
      `/api/ward/${WID}/candidates?month=${encodeURIComponent(month)}`),
}

export { ApiError }
