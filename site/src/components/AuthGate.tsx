import { useState } from "react";
import { supabase } from "../lib/supabase";

export function AuthGate() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    setError(null);
    const { error: err } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: window.location.href },
    });
    setLoading(false);
    if (err) {
      setError(err.message);
    } else {
      setSent(true);
    }
  }

  return (
    <div className="auth-gate">
      <div className="auth-gate-card">
        <h2 className="auth-gate-title">Survivor Pools</h2>
        {sent ? (
          <div className="auth-gate-sent">
            <p>Check <strong>{email}</strong> for a sign-in link.</p>
            <p className="auth-gate-hint">Click the link in the email to load your pools on any device.</p>
          </div>
        ) : (
          <form className="auth-gate-form" onSubmit={handleSubmit}>
            <p className="auth-gate-desc">Sign in to manage your private survivor picks across any device.</p>
            <label className="auth-gate-label" htmlFor="auth-email">Email address</label>
            <input
              id="auth-email"
              className="auth-gate-input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              required
            />
            {error && <p className="auth-gate-error">{error}</p>}
            <button className="auth-gate-btn" type="submit" disabled={loading}>
              {loading ? "Sending…" : "Send sign-in link"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
