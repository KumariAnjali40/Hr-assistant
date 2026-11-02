import { useState } from "react";
import Chat from "./Chat";
import Admin from "./Admin";
import { isHR, logout, username } from "./auth";

export default function App() {
  const [tab, setTab] = useState("chat");
  return (
    <div className="shell">
      <header className="top">
        <strong className="brand">HR Assistant</strong>
        <nav>
          <button className={tab === "chat" ? "tab on" : "tab"} onClick={() => setTab("chat")}>Chat</button>
          {isHR() && <button className={tab === "admin" ? "tab on" : "tab"} onClick={() => setTab("admin")}>Policies</button>}
        </nav>
        <span className="who">{username()}</span>
        <button className="link" onClick={logout}>Sign out</button>
      </header>
      {tab === "chat" ? <Chat /> : <Admin />}
    </div>
  );
}
