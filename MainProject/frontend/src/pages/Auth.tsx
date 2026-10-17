import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { Button, ErrorNote, Field, inputCls } from "../components/ui";
import { useAuth } from "../lib/auth";

export default function Auth({ mode }: { mode: "login" | "signup" }) {
  const { user, login, signup } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const from = (loc.state as { from?: string } | null)?.from ?? "/dashboard";
  // New accounts go straight to interview setup; returning users go back where they were headed.
  const dest = mode === "signup" ? "/interview/new" : from;

  if (user) return <Navigate to={dest} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (mode === "signup" && password.length < 8) { setError("Use at least 8 characters for your password."); return; }
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await signup(email, password, name);
      nav(dest, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <Logo />
        <h1 className="mt-8 text-3xl font-extrabold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p className="mt-1 text-muted">
          {mode === "login" ? "Pick up where your last interview left off." : "Your progress and weak topics are saved to this account."}
        </p>
        <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
          {mode === "signup" && (
            <Field label="Name" htmlFor="name">
              <input id="name" className={inputCls} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
            </Field>
          )}
          <Field label="Email" htmlFor="email">
            <input id="email" type="email" required className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </Field>
          <Field label="Password" htmlFor="password" hint={mode === "signup" ? "At least 8 characters." : undefined}>
            <input id="password" type="password" required className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)}
                   autoComplete={mode === "login" ? "current-password" : "new-password"} />
          </Field>
          {error && <ErrorNote message={error} />}
          <Button type="submit" loading={busy} className="w-full py-3">{mode === "login" ? "Sign in" : "Create account"}</Button>
        </form>
        <p className="mt-6 text-center text-muted">
          {mode === "login" ? <>New here? <Link className="font-bold text-accent underline-offset-2 hover:underline" to="/signup">Create an account</Link></>
            : <>Already registered? <Link className="font-bold text-accent underline-offset-2 hover:underline" to="/login">Sign in</Link></>}
        </p>
      </div>
    </div>
  );
}
