import { useState, type FormEvent } from "react";
import { api, setAdminKey } from "../api";

type Props = { onAuthed: () => void };

export function LoginPage({ onAuthed }: Props) {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      setAdminKey(key.trim());
      await api.listTenants();
      onAuthed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="panel login-card" onSubmit={onSubmit}>
        <h1>Healeka Voice</h1>
        <p className="muted">
          Hospital onboarding console for the AI receptionist. Sign in with your
          admin API key.
        </p>
        {error ? <div className="error">{error}</div> : null}
        <div className="grid" style={{ marginTop: 18 }}>
          <label>
            Admin API key
            <input
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="ADMIN_API_KEY from server .env"
              required
              autoFocus
            />
          </label>
          <button className="btn primary" type="submit" disabled={loading}>
            {loading ? "Checking…" : "Enter console"}
          </button>
        </div>
      </form>
    </div>
  );
}
