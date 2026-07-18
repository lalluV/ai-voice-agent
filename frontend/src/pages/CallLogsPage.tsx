import { useEffect, useState } from "react";
import { api, type CallLog, type Tenant } from "../api";

export function CallLogsPage() {
  const [logs, setLogs] = useState<CallLog[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load(filter?: string) {
    setLoading(true);
    setError("");
    try {
      const [t, l] = await Promise.all([
        api.listTenants(),
        api.listCallLogs(filter || undefined),
      ]);
      setTenants(t);
      setLogs(l);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load call logs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Call logs</h2>
          <p className="muted">Recent voice sessions stored in the voice-agent Mongo DB.</p>
        </div>
        <div className="actions">
          <select
            value={tenantId}
            onChange={(e) => {
              const v = e.target.value;
              setTenantId(v);
              void load(v);
            }}
          >
            <option value="">All hospitals</option>
            {tenants.map((t) => (
              <option key={t.tenant_id} value={t.tenant_id}>
                {t.name}
              </option>
            ))}
          </select>
          <button className="btn" type="button" onClick={() => void load(tenantId)}>
            Refresh
          </button>
        </div>
      </div>
      {error ? <div className="error">{error}</div> : null}
      {loading ? <p className="muted">Loading…</p> : null}
      {!loading && logs.length === 0 ? (
        <p className="muted">No calls logged yet.</p>
      ) : null}
      {logs.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>When</th>
              <th>Hospital</th>
              <th>From → To</th>
              <th>Duration</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.session_id}>
                <td>{new Date(l.started_at).toLocaleString()}</td>
                <td>{l.tenant_id}</td>
                <td>
                  {l.from_number || "—"} → {l.to_number || "—"}
                </td>
                <td>
                  {l.duration_seconds != null ? `${Math.round(l.duration_seconds)}s` : "—"}
                  <div className="muted">
                    tools {l.tool_call_count} · interrupts {l.interruption_count}
                  </div>
                </td>
                <td>
                  <span className={`badge ${l.end_reason === "error" ? "off" : "on"}`}>
                    {l.end_reason || l.status}
                  </span>
                  {l.error_message ? (
                    <div className="muted">{l.error_message.slice(0, 80)}</div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
