import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { deleteConversation, getMessages, listConversations, sendFeedback, streamChat } from "./api";

const TOOL_LABELS = {
  search_policy: "Searching policies…",
  get_my_leave_balance: "Checking your leave balance…",
  get_my_next_payday: "Checking the payroll schedule…",
  create_hr_ticket: "Raising an HR ticket…",
};
const SUGGESTIONS = ["How many casual leaves do I get?", "What's my leave balance?", "When is salary credited?"];

export default function Chat() {
  const [convs, setConvs] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const endRef = useRef(null);
  const abortRef = useRef(null);

  const refresh = () => listConversations().then(setConvs).catch(() => {});
  useEffect(() => { refresh(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, status]);

  const patchLast = (fn) => setMessages((ms) => ms.map((m, i) => (i === ms.length - 1 ? fn(m) : m)));

  async function open(id) {
    setActiveId(id);
    setMessages(id ? await getMessages(id) : []);
  }

  async function remove(id) {
    await deleteConversation(id);
    if (id === activeId) open(null);
    refresh();
  }

  async function send(text) {
    text = (text ?? input).trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "", sources: [] }]);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      for await (const { event, data } of streamChat(text, activeId, ctrl.signal)) {
        if (event === "meta") setActiveId(data.conversation_id);
        else if (event === "tool") setStatus(TOOL_LABELS[data.name] || "Working…");
        else if (event === "token") { setStatus(""); patchLast((m) => ({ ...m, content: m.content + data.text })); }
        else if (event === "sources") patchLast((m) => ({ ...m, sources: data.sources }));
        else if (event === "done") patchLast((m) => ({ ...m, id: data.message_id }));
        else if (event === "error") patchLast((m) => ({ ...m, content: data.message, error: true }));
      }
    } catch (e) {
      if (e.name !== "AbortError") patchLast((m) => ({ ...m, content: e.message || "Request failed", error: true }));
    } finally {
      setBusy(false);
      setStatus("");
      refresh();
    }
  }

  async function rate(m, rating) {
    await sendFeedback(m.id, rating).catch(() => {});
    setMessages((ms) => ms.map((x) => (x.id === m.id ? { ...x, rated: rating } : x)));
  }

  return (
    <div className="chat">
      <aside className="side">
        <button className="primary" onClick={() => open(null)}>New chat</button>
        <ul>
          {convs.map((c) => (
            <li key={c.id} className={c.id === activeId ? "on" : ""}>
              <button className="conv" onClick={() => open(c.id)}>{c.title}</button>
              <button className="x" aria-label={`Delete ${c.title}`} onClick={() => remove(c.id)}>×</button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="main">
        <div className="log" aria-live="polite">
          {messages.length === 0 && (
            <div className="empty">
              <h2>Ask about leave, payroll or company policy</h2>
              <div className="chips">{SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}</div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={m.id || i} className={`msg ${m.role}${m.error ? " err" : ""}`}>
              {m.role === "assistant" ? <ReactMarkdown>{m.content || (busy && i === messages.length - 1 ? "…" : "")}</ReactMarkdown> : m.content}
              {m.sources?.length > 0 && (
                <div className="sources">
                  {m.sources.map((s, k) => <span key={k}>{s.policy} v{s.version}{s.page != null ? `, p.${s.page + 1}` : ""}</span>)}
                </div>
              )}
              {m.id && m.role === "assistant" && (
                <div className="rate">
                  <button disabled={m.rated} className={m.rated === 1 ? "on" : ""} onClick={() => rate(m, 1)} aria-label="Helpful">Helpful</button>
                  <button disabled={m.rated} className={m.rated === -1 ? "on" : ""} onClick={() => rate(m, -1)} aria-label="Not helpful">Not helpful</button>
                </div>
              )}
            </div>
          ))}
          {status && <div className="status">{status}</div>}
          <div ref={endRef} />
        </div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your HR question" maxLength={2000} aria-label="Message" />
          {busy ? <button type="button" onClick={() => abortRef.current?.abort()}>Stop</button> : <button className="primary" disabled={!input.trim()}>Send</button>}
        </form>
      </main>
    </div>
  );
}
