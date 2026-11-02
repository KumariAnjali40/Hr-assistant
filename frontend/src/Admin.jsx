import { useEffect, useState } from "react";
import { deletePolicy, listPolicies, uploadPolicy } from "./api";

const ROLE_SETS = { "Everyone": "employee,manager,hr", "Managers and HR": "manager,hr", "HR only": "hr" };

export default function Admin() {
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => listPolicies().then(setRows).catch((e) => setErr(e.message));
  useEffect(() => {
    load();
    const t = setInterval(load, 4000); // poll ingestion status
    return () => clearInterval(t);
  }, []);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await uploadPolicy(new FormData(e.target));
      e.target.reset();
      load();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin">
      <h2>Policy documents</h2>
      <form onSubmit={submit} className="upload">
        <input name="file" type="file" accept=".pdf,.docx,.txt,.md" required />
        <input name="name" placeholder="Policy name (e.g. Leave Policy)" required />
        <input name="version" placeholder="Version" required size={8} />
        <select name="allowed_roles">{Object.entries(ROLE_SETS).map(([k, v]) => <option key={k} value={v}>Visible to: {k}</option>)}</select>
        <button className="primary" disabled={busy}>{busy ? "Uploading…" : "Upload and index"}</button>
      </form>
      {err && <p className="error" role="alert">{err}</p>}
      <table>
        <thead><tr><th>Policy</th><th>Version</th><th>Visible to</th><th>Status</th><th>Chunks</th><th /></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.name}<div className="muted">{r.filename}</div></td>
              <td>{r.version}</td>
              <td>{r.roles.join(", ")}</td>
              <td><span className={`pill ${r.status}`}>{r.status}</span>{r.error && <div className="muted">{r.error}</div>}</td>
              <td>{r.chunks}</td>
              <td><button className="link" onClick={() => confirm(`Delete ${r.name} v${r.version}?`) && deletePolicy(r.id).then(load)}>Delete</button></td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={6} className="muted">No documents yet. Upload a policy to start answering questions from it.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
