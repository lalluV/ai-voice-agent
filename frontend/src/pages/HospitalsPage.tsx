import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Tenant, type TenantPayload } from "../api";

const emptyForm: TenantPayload = {
  tenant_id: "",
  name: "",
  plivo_numbers: [],
  hms_base_url: "https://hms-server.lalluvemula.cloud/api",
  hms_subdomain: "",
  hms_auth_token: "",
  ai_provider: "gemini",
  voice_name: "Aoede",
  prompt_version: "v1",
  transfer_number: "",
  hospital_blurb: "",
  enabled: true,
};

export function HospitalsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setTenants(await api.listTenants());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load hospitals");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function toggleEnabled(t: Tenant) {
    try {
      await api.updateTenant(t.tenant_id, { enabled: !t.enabled });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function remove(t: Tenant) {
    if (!confirm(`Remove hospital "${t.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteTenant(t.tenant_id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Hospitals</h2>
          <p className="muted">Onboard Plivo DIDs and HMS credentials per clinic.</p>
        </div>
        <Link className="btn primary" to="/hospitals/new">
          Onboard hospital
        </Link>
      </div>
      {error ? <div className="error">{error}</div> : null}
      {loading ? <p className="muted">Loading…</p> : null}
      {!loading && tenants.length === 0 ? (
        <p className="muted">No hospitals yet. Onboard the first clinic to start taking calls.</p>
      ) : null}
      {tenants.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>Hospital</th>
              <th>Plivo numbers</th>
              <th>HMS</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.tenant_id}>
                <td>
                  <strong>{t.name}</strong>
                  <div className="muted">{t.tenant_id}</div>
                </td>
                <td>{t.plivo_numbers.join(", ") || "—"}</td>
                <td>
                  <div>{t.hms_subdomain}</div>
                  <div className="muted">
                    token {t.has_hms_token ? "set" : "missing"} · voice {t.voice_name}
                  </div>
                </td>
                <td>
                  <span className={`badge ${t.enabled ? "on" : "off"}`}>
                    {t.enabled ? "Enabled" : "Disabled"}
                  </span>
                </td>
                <td>
                  <div className="row-actions">
                    <Link className="btn ghost" to={`/hospitals/${t.tenant_id}`}>
                      Edit
                    </Link>
                    <button className="btn" type="button" onClick={() => void toggleEnabled(t)}>
                      {t.enabled ? "Disable" : "Enable"}
                    </button>
                    <button className="btn danger" type="button" onClick={() => void remove(t)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

export function HospitalFormPage() {
  const { tenantId } = useParams();
  const isNew = !tenantId || tenantId === "new";
  const navigate = useNavigate();
  const [form, setForm] = useState<TenantPayload>(emptyForm);
  const [numbersText, setNumbersText] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const title = useMemo(
    () => (isNew ? "Onboard hospital" : `Edit ${form.name || tenantId}`),
    [isNew, form.name, tenantId],
  );

  useEffect(() => {
    if (isNew) return;
    void (async () => {
      try {
        const t = await api.getTenant(tenantId!);
        setForm({
          tenant_id: t.tenant_id,
          name: t.name,
          plivo_numbers: t.plivo_numbers,
          hms_base_url: t.hms_base_url,
          hms_subdomain: t.hms_subdomain,
          hms_auth_token: "",
          ai_provider: t.ai_provider,
          voice_name: t.voice_name,
          prompt_version: t.prompt_version,
          transfer_number: t.transfer_number ?? "",
          hospital_blurb: t.hospital_blurb ?? "",
          enabled: t.enabled,
        });
        setNumbersText(t.plivo_numbers.join(", "));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load hospital");
      }
    })();
  }, [isNew, tenantId]);

  function setField<K extends keyof TenantPayload>(key: K, value: TenantPayload[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    const numbers = numbersText
      .split(/[,\n]/)
      .map((n) => n.trim())
      .filter(Boolean);
    try {
      if (isNew) {
        if (!form.hms_auth_token?.trim()) {
          throw new Error("HMS auth token is required for new hospitals");
        }
        await api.createTenant({
          ...form,
          plivo_numbers: numbers,
          transfer_number: form.transfer_number || null,
          hospital_blurb: form.hospital_blurb || null,
        });
      } else {
        const patch: Partial<TenantPayload> = {
          name: form.name,
          plivo_numbers: numbers,
          hms_base_url: form.hms_base_url,
          hms_subdomain: form.hms_subdomain,
          ai_provider: form.ai_provider,
          voice_name: form.voice_name,
          prompt_version: form.prompt_version,
          transfer_number: form.transfer_number || null,
          hospital_blurb: form.hospital_blurb || null,
          enabled: form.enabled,
        };
        if (form.hms_auth_token?.trim()) {
          patch.hms_auth_token = form.hms_auth_token.trim();
        }
        if (form.gemini_api_key?.trim()) {
          patch.gemini_api_key = form.gemini_api_key.trim();
        }
        await api.updateTenant(tenantId!, patch);
      }
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          <p className="muted">
            Map Plivo DID → hospital HMS tenant. Token is stored server-side and never shown again.
          </p>
        </div>
        <Link className="btn ghost" to="/">
          Back
        </Link>
      </div>
      {error ? <div className="error">{error}</div> : null}
      <form className="grid" onSubmit={onSubmit}>
        <div className="grid two">
          <label>
            Tenant ID
            <input
              value={form.tenant_id}
              disabled={!isNew}
              required
              onChange={(e) => setField("tenant_id", e.target.value.trim())}
              placeholder="srichakra"
            />
          </label>
          <label>
            Hospital name
            <input
              value={form.name}
              required
              onChange={(e) => setField("name", e.target.value)}
              placeholder="Sri Chakra Diagnostics"
            />
          </label>
          <label>
            Plivo numbers
            <input
              value={numbersText}
              onChange={(e) => setNumbersText(e.target.value)}
              placeholder="+918035017773, +91..."
              required
            />
          </label>
          <label>
            Transfer number
            <input
              value={form.transfer_number ?? ""}
              onChange={(e) => setField("transfer_number", e.target.value)}
              placeholder="+91 receptionist"
            />
          </label>
          <label>
            HMS base URL
            <input
              value={form.hms_base_url}
              required
              onChange={(e) => setField("hms_base_url", e.target.value)}
            />
          </label>
          <label>
            HMS subdomain
            <input
              value={form.hms_subdomain}
              required
              onChange={(e) => setField("hms_subdomain", e.target.value.trim())}
              placeholder="srichakra"
            />
          </label>
          <label>
            HMS auth token (JWT)
            <input
              type="password"
              value={form.hms_auth_token ?? ""}
              onChange={(e) => setField("hms_auth_token", e.target.value)}
              placeholder={isNew ? "Required" : "Leave blank to keep existing"}
              required={isNew}
            />
          </label>
          <label>
            Gemini API key (optional override)
            <input
              type="password"
              value={form.gemini_api_key ?? ""}
              onChange={(e) => setField("gemini_api_key", e.target.value)}
              placeholder="Leave blank to use server default"
            />
          </label>
          <label>
            Voice
            <input
              value={form.voice_name ?? "Aoede"}
              onChange={(e) => setField("voice_name", e.target.value)}
            />
          </label>
          <label>
            Prompt version
            <input
              value={form.prompt_version ?? "v1"}
              onChange={(e) => setField("prompt_version", e.target.value)}
            />
          </label>
        </div>
        <label>
          Hospital blurb (spoken context)
          <textarea
            value={form.hospital_blurb ?? ""}
            onChange={(e) => setField("hospital_blurb", e.target.value)}
            placeholder="Short description the agent can use"
          />
        </label>
        <label style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          <input
            type="checkbox"
            checked={!!form.enabled}
            onChange={(e) => setField("enabled", e.target.checked)}
          />
          Enabled for inbound calls
        </label>
        <div className="actions">
          <button className="btn primary" type="submit" disabled={saving}>
            {saving ? "Saving…" : isNew ? "Create hospital" : "Save changes"}
          </button>
        </div>
      </form>
    </section>
  );
}
