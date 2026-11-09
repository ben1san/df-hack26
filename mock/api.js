/* サーバを唯一の正にする継ぎ目。フレームワークの代わりではなく、
   フレームワークでも自分で書く部分（非同期・失敗時の巻き戻し・購読）だけを持つ。 */
(function (g) {
  const S = {
    wid: 'w1', mon: '2026-11', base: '',
    ward: null, month: null, current: {}, proposal: {},
    rules: [], edits: [], repeats: [], deaths: [], nkeys: 0,
    nightAverage: null, solving: false, error: null,
  };
  const subs = [];
  const emit = () => subs.forEach(f => f(S));

  async function call(path, body, method) {
    const r = await fetch(S.base + path, {
      method: method || (body === undefined ? 'GET' : 'POST'),
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.status);
    return r.json();
  }

  /* 行番号 ↔ nurse_id。既存の draw() は行番号で引くので対応表を持つ */
  const idx = {};
  const rebuildIdx = () => (S.ward.nurses.forEach((n, i) => { idx[n.id] = i; }), idx);
  const rowOf = id => idx[id];

  const api = {
    S, idx, rowOf,
    on(f) { subs.push(f); return () => subs.splice(subs.indexOf(f), 1); },

    /* 画面が1回で取る。sessionStorage の代わり */
    async boot(mon) {
      if (mon) S.mon = mon;
      const b = await call(`/api/ward/${S.wid}/month/${S.mon}`);
      Object.assign(S, {
        ward: b.ward, month: b.month, current: b.current, proposal: b.month.proposal,
        rules: b.rules, edits: b.edits, repeats: b.repeats, deaths: b.deaths,
        nkeys: b.n_keys, error: null,
      });
      rebuildIdx(); emit(); return S;
    },

    /* 求解は常にサーバ。夜勤 → 日勤の二段階 */
    async solve(stage, opts) {
      S.solving = true; S.error = null; emit();
      try {
        const r = await call(`/api/ward/${S.wid}/month/${S.mon}/solve`,
          Object.assign({ stage: stage || 'night' }, opts || {}));
        S.nightAverage = r.night_average;
        if (r.status === 'INFEASIBLE') { S.error = r; return r; }
        S.proposal = r.proposal;
        await api.boot();                 /* 現状は提案＋編集ログの射影。サーバに作らせる */
        return r;
      } finally { S.solving = false; emit(); }
    },

    /* 手修正。何も聞かない。楽観的に描いて、失敗したら戻す */
    async edit(nurseId, day, to) {
      const row = S.current[nurseId] || (S.current[nurseId] = []);
      const prev = row[day - 1];
      row[day - 1] = to; emit();                       /* 先に描く */
      try {
        const r = await call(`/api/ward/${S.wid}/month/${S.mon}/edits`,
          { nurse_id: nurseId, day, to });
        S.current = r.current; S.edits.push(r.edit); emit();
        return r;
      } catch (e) {
        row[day - 1] = prev; S.error = String(e); emit();   /* 巻き戻す */
        throw e;
      }
    },

    /* セルを指して言う。範囲3通りが返る。選ぶのは師長 */
    translate(nurseId, day, weekday, kind, text) {
      return call(`/api/ward/${S.wid}/translate`,
        { nurse_id: nurseId, month: S.mon, day, weekday, kind, text });
    },

    async confirm(rule, expiresOn) {
      const r = await call(`/api/ward/${S.wid}/rules`,
        { rule, expires_on: expiresOn || null, approved_by: '師長' });
      await api.boot(); return r;
    },

    async stopRule(id, stopped) {
      const r = await call(`/api/ward/${S.wid}/rules/${id}`, { stopped }, 'PATCH');
      await api.boot(); return r;
    },

    /* 月送り。段階4は専用画面を持たず、ここの副作用で起きる */
    async nextMonth(mon, days, firstWeekday) {
      S.mon = mon;
      await api.solve('night', { days, first_weekday: firstWeekday });
      return { deaths: S.deaths, repeats: S.repeats.filter(r => r.fired) };
    },
  };
  g.RX = api;
})(typeof window !== 'undefined' ? window : globalThis);
