/* 状態はここだけ。sessionStorage を使わない — サーバが唯一の正。
   段階0のウィザードだけは確定前なのでクライアントに持つ。 */
import { create } from 'zustand'
import { api } from './api'
import type {
  Death, Edit, Grid, Month, Repeat, Rule, ShiftKind, SolveResult, Stage, Ward,
} from './types'

/** 段階0。POST /api/ward を押すまでサーバに出ない */
export interface Setup {
  wardName: string
  kinds: ShiftKind[]
  nurses: { name: string; qual: string }[]
  nightBandStart: number
  youshiki9: boolean
  prevTail: Grid
  staffing: { kind: string; atLeast: number; days: string }[]
  importedMonth: string | null
}

export const DEFAULT_KINDS: ShiftKind[] = [
  { id: '日', name: '日勤', hours: 8, night_hours: 0, crosses_midnight: false, is_off: false, counts_as_staff: true },
  { id: '準', name: '準夜勤', hours: 8.5, night_hours: 8.5, crosses_midnight: true, is_off: false, counts_as_staff: true },
  { id: '深', name: '深夜勤', hours: 8.5, night_hours: 7.5, crosses_midnight: true, is_off: false, counts_as_staff: true },
  { id: '休', name: '公休', hours: 0, night_hours: 0, crosses_midnight: false, is_off: true, counts_as_staff: true },
  { id: '研', name: '研修', hours: 8, night_hours: 0, crosses_midnight: false, is_off: false, counts_as_staff: false },
]

interface State {
  month: string
  ward: Ward | null
  monthData: Month | null
  proposal: Grid
  current: Grid
  rules: Rule[]
  edits: Edit[]
  repeats: Repeat[]
  deaths: Death[]
  nKeys: number
  nightAverage: number | null
  unsat: SolveResult | null
  stage: Stage
  solving: boolean
  booted: boolean
  note: string | null
  setup: Setup

  notify: (s: string | null) => void
  patchSetup: (p: Partial<Setup>) => void
  boot: (month?: string) => Promise<void>
  solve: (stage: Stage, opts?: { days?: number; first_weekday?: number }) => Promise<SolveResult>
  edit: (nurseId: string, day: number, to: string | null) => Promise<void>
  confirm: (rule: Rule, expiresOn: string | null) => Promise<void>
  stopRule: (id: string, stopped: boolean) => Promise<void>
  goMonth: (month: string, days: number, firstWeekday: number) => Promise<void>
}

const EMPTY_SETUP: Setup = {
  wardName: '', kinds: DEFAULT_KINDS, nurses: [], nightBandStart: 16,
  youshiki9: true, prevTail: {}, staffing: [], importedMonth: null,
}

export const useStore = create<State>((set, get) => ({
  month: '2026-11',
  ward: null, monthData: null,
  proposal: {}, current: {},
  rules: [], edits: [], repeats: [], deaths: [],
  nKeys: 0, nightAverage: null, unsat: null,
  stage: 'night', solving: false, booted: false, note: null,
  setup: EMPTY_SETUP,

  notify: note => {
    set({ note })
    if (note) setTimeout(() => get().note === note && set({ note: null }), 2600)
  },
  patchSetup: p => set(s => ({ setup: { ...s.setup, ...p } })),

  async boot(month) {
    const m = month ?? get().month
    const b = await api.bootstrap(m)
    set({
      month: m, ward: b.ward, monthData: b.month,
      proposal: b.month.proposal, current: b.current,
      rules: b.rules, edits: b.edits, repeats: b.repeats, deaths: b.deaths,
      nKeys: b.n_keys, booted: true,
    })
  },

  async solve(stage, opts) {
    set({ solving: true, unsat: null })
    try {
      const r = await api.solve(get().month, stage, opts)
      set({ nightAverage: r.night_average, stage })
      if (r.status === 'INFEASIBLE') { set({ unsat: r }); return r }
      await get().boot()           // 現状は提案＋編集ログの射影。サーバに作らせる
      return r
    } finally { set({ solving: false }) }
  },

  /** 何も聞かない。先に描いて、失敗したら戻す */
  async edit(nurseId, day, to) {
    const before = get().current
    const row = [...(before[nurseId] ?? [])]
    row[day - 1] = to
    set({ current: { ...before, [nurseId]: row } })
    try {
      const r = await api.addEdit(get().month, nurseId, day, to)
      set(s => ({ current: r.current, edits: [...s.edits, r.edit] }))
    } catch (e) {
      set({ current: before })                              // 巻き戻す
      get().notify(`戻しました — ${(e as Error).message}`)
      throw e
    }
  },

  async confirm(rule, expiresOn) {
    await api.confirmRule(rule, expiresOn)
    await get().boot()
    get().notify(`決まりになりました — ${rule.label}`)
  },

  async stopRule(id, stopped) {
    try {
      await api.patchRule(id, { stopped })
      await get().boot()
    } catch (e) { get().notify((e as Error).message) }
  },

  /** 月送り。段階4は専用画面を持たず、ここの副作用で起きる */
  async goMonth(month, days, firstWeekday) {
    set({ month })
    await get().solve('night', { days, first_weekday: firstWeekday })
    const { deaths, repeats } = get()
    const fired = repeats.filter(r => r.fired)
    if (deaths.length) get().notify(`${deaths.length}本の決まりが止まりました`)
    else if (fired.length) get().notify(`${fired.length}件、毎月直している所があります`)
  },
}))

/* ---- 導出。コンポーネントは数えない ---- */
export const weekdayOf = (m: Month | null, day: number) =>
  m ? (m.first_weekday + day - 1) % 7 : 0

/** 棄却 ＝ 提案があって現状が違うセル */
export const nightHours = (ward: Ward | null, grid: Grid, nurseId: string) =>
  !ward ? 0 : (grid[nurseId] ?? []).reduce((a, c) => {
    const k = ward.shift_kinds.find(x => x.id === c)
    return a + (k?.night_hours ?? 0)
  }, 0)

export const perDay = (ward: Ward | null, grid: Grid, day: number, kindId: string) =>
  !ward ? 0 : ward.nurses.filter(n => grid[n.id]?.[day - 1] === kindId).length

