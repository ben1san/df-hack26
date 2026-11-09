import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toast } from './components/Toast'
import { Import } from './screens/Import'
import { WardSetup } from './screens/WardSetup'
import { NurseList } from './screens/NurseList'
import { PrevMonth } from './screens/PrevMonth'
import { Optional } from './screens/Optional'
import { Derive } from './screens/Derive'
import { Roster } from './screens/Roster'

/* HashRouter を使う。SPAのパス直打ちでサーバ側のフォールバック設定が要らなくなり、
   Cloud Run の StaticFiles 配信のままで再読み込みが壊れない。 */
export function App() {
  return (
    <HashRouter>
      <Toast />
      <Routes>
        <Route path="/" element={<Import />} />
        <Route path="/setup/ward" element={<WardSetup />} />
        <Route path="/setup/nurses" element={<NurseList />} />
        <Route path="/setup/prev" element={<PrevMonth />} />
        <Route path="/setup/optional" element={<Optional />} />
        <Route path="/setup/derive" element={<Derive />} />
        <Route path="/roster" element={<Roster />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  )
}
