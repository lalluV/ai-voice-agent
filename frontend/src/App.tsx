import { useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { clearAdminKey, getAdminKey } from "./api";
import { CallLogsPage } from "./pages/CallLogsPage";
import { HospitalFormPage, HospitalsPage } from "./pages/HospitalsPage";
import { LoginPage } from "./pages/LoginPage";

function Shell({ onSignOut }: { onSignOut: () => void }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <strong>Healeka Voice</strong>
          <span>Multi-hospital AI receptionist console</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>
            Hospitals
          </NavLink>
          <NavLink to="/calls">Call logs</NavLink>
          <button className="btn ghost" type="button" onClick={onSignOut}>
            Sign out
          </button>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<HospitalsPage />} />
        <Route path="/hospitals/new" element={<HospitalFormPage />} />
        <Route path="/hospitals/:tenantId" element={<HospitalFormPage />} />
        <Route path="/calls" element={<CallLogsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(() => !!getAdminKey());

  if (!authed) {
    return <LoginPage onAuthed={() => setAuthed(true)} />;
  }
  return (
    <Shell
      onSignOut={() => {
        clearAdminKey();
        setAuthed(false);
      }}
    />
  );
}
