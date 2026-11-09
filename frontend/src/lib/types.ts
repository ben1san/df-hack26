/* app/dsl.py の写し。片側を変えたらこちらも変える。
   将来は openapi-typescript で /openapi.json から生成する（いまは手で合わせている） */

export type Strength = '絶対' | '強く' | 'できれば'
export type OriginKind =
  | '法令' | 'ガイドライン' | '段階0逆算' | '反復検出' | '師長の言葉' | '手入力'

export interface ShiftKind {
  id: string; name: string
  hours: number; night_hours: number
  crosses_midnight: boolean; is_off: boolean; counts_as_staff: boolean
}
export interface Nurse { id: string; name: string; qual: string; groups: string[] }
export interface Ward {
  id: string; name: string
  shift_kinds: ShiftKind[]; nurses: Nurse[]
  night_band_start: number; night_average_cap: number
  day_groups: Record<string, number[]>
}

export interface PeopleSel { ids?: string[] | null; quals?: string[] | null; groups?: string[] | null }
export interface DaySel { weekdays?: number[] | null; dates?: number[] | null; named?: string | null }
export interface ShiftSel { ids?: string[] | null }

export interface Origin {
  kind: OriginKind
  detected_from: string[]
  evidence?: string | null
  approved_by?: string | null
  approved_at?: string | null
  source_url?: string | null
}
export interface Lifecycle {
  expires_on?: string | null
  last_fired_on?: string | null
  stopped: boolean
}

interface RuleBase {
  id: string; label: string; strength: Strength
  origin: Origin; lifecycle: Lifecycle; locked: boolean
}
export type Rule =
  | (RuleBase & { type: 'oneShiftPerDay' })
  | (RuleBase & { type: 'staffing'; shifts: ShiftSel; people: PeopleSel; days: DaySel
                  at_least?: number | null; at_most?: number | null })
  | (RuleBase & { type: 'request'; people: PeopleSel; days: DaySel; shifts: ShiftSel; want: boolean })
  | (RuleBase & { type: 'succession'; people: PeopleSel; pattern?: ShiftSel[] | null
                  forbid: boolean; max_run?: number | null })
  | (RuleBase & { type: 'count'; people: PeopleSel; shifts: ShiftSel; days: DaySel
                  unit: '回' | '時間'; at_least?: number | null; at_most?: number | null })
  | (RuleBase & { type: 'wardNightAverage'; cap: number; min_night_hours_to_count: number })

/** 手修正1件。追記のみ。from はソルバが置いたもの */
export interface Edit {
  id: string; nurse_id: string; day: number
  from?: string | null; to?: string | null
  at: string; synthetic: boolean
}

/** 表 ＝ 提案 ＋ 編集ログ。1本の配列で持つと「棄却」が定義できない */
export type Grid = Record<string, (string | null)[]>
export interface Month {
  month: string; days: number; first_weekday: number
  proposal: Grid; current: Grid
  rules_snapshot: string[]; solved_at?: string | null
}

export interface Repeat {
  nurse_id: string; nurse: string | null; weekday: number
  kind_id: string; kind: string
  months: string[]; streak: number; threshold: number; fired: boolean
  edit_ids: string[]; evidence: string
  /** 一度答えた反復は、もう聞かない */
  answered: boolean
  /** 発火したときだけ入る。範囲3通り。選ぶのは師長 */
  candidates: { scope: Scope; rule: Rule }[]
}
export interface Death { rule_id: string; label: string; why: string }
export interface Broken { rule_id: string; label: string; count: number; detail?: string | null }

export interface Bootstrap {
  ward: Ward; month: Month; current: Grid
  rules: Rule[]; edits: Edit[]
  n_keys: number; repeats: Repeat[]; deaths: Death[]
}
export interface SolveResult {
  status: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'UNKNOWN' | 'MODEL_INVALID'
  stage: Stage; wall_ms: number
  proposal: Grid; night_average: number | null
  infeasible_rules: Broken[]; relaxation: Broken[]; soft_broken: Broken[]
}
export type Stage = 'night' | 'day'

export interface RuleDraft {
  type: 'request' | 'succession' | 'count'
  shift_ids: string[]; want?: boolean | null
  after_shift_ids: string[]; max_run?: number | null
  at_least?: number | null; at_most?: number | null
  label_ja: string
}
export type Scope = 'one' | 'allwd' | 'allp'
export interface TranslateResult {
  route: string; draft: RuleDraft
  candidates: { scope: Scope; rule: Rule }[]
}

/* 段階0の候補。選択肢の形が候補ごとに違う */
export type QKind = 'yesno' | 'boundary' | 'term'
export interface Choice {
  label: string
  rule: Rule | null          // null は「作らない」
  expires_on: string | null
}
export interface Candidate {
  id: string; question: string; evidence: string; kind: QKind; choices: Choice[]
}

export const QKIND_LABEL: Record<QKind, string> = {
  yesno: '決まりかどうか', boundary: '境界の値', term: 'いつまで',
}

export const WD = ['日', '月', '火', '水', '木', '金', '土'] as const
export const SCOPE_LABEL: Record<Scope, string> = {
  one: 'この人の、この曜日だけ',
  allwd: 'この人は、いつでも',
  allp: 'この曜日は、全員',
}
