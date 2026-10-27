import React from "react";
import ReactDOM from "react-dom/client";
import { useEffect, useState, type FormEvent } from "react";
import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { Landing } from "./pages/Landing";
import { ReviewPage } from "./pages/Review";
import { Dashboard, PublicCase, RunPage } from "./pages/Runs";
import { EvalPage } from "./pages/Eval";
import { Icon } from "./icons";
import { api } from "./api";
import "./style.css";

function AuthGate({ children }: { children: React.ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ authenticated: boolean }>("/api/auth/check")
      .then(() => setAuthenticated(true))
      .catch((cause: Error) => {
        if (cause.message.startsWith("401:")) {
          sessionStorage.removeItem("dak_reviewer_password");
        } else {
          setError(cause.message);
        }
      })
      .finally(() => setChecking(false));
  }, []);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    sessionStorage.setItem("dak_reviewer_password", password);
    try {
      await api("/api/auth/check");
      setAuthenticated(true);
    } catch (cause) {
      sessionStorage.removeItem("dak_reviewer_password");
      setError(cause instanceof Error ? "That password was not accepted." : "Sign-in failed.");
    }
  }

  if (checking) return <div className="login-shell" aria-live="polite">Checking workspace access…</div>;
  if (authenticated) return <>{children}</>;
  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={signIn}>
        <span className="eyebrow">DAK · REVIEW WORKSPACE</span>
        <h1>Welcome back.</h1>
        <p>Enter the private reviewer password to open the synthetic demo inbox.</p>
        <label htmlFor="reviewer-password">Reviewer password</label>
        <input
          id="reviewer-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" type="submit">Open workspace</button>
      </form>
    </main>
  );
}

function Workspace() {
  const { pathname } = useLocation();
  const section =
    pathname === "/"
      ? "Compose"
      : pathname.startsWith("/review")
        ? "Review desk"
        : pathname === "/dashboard"
          ? "Activity"
          : pathname === "/eval"
            ? "Evaluation"
            : "Correspondence";
  return (
    <div className="app-shell">
      <a href="#main" className="skip">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Workspace">
        <NavLink to="/" className="wordmark" aria-label="Dak home">
          <span className="brand-symbol">
            <Icon name="layers" size={25} />
          </span>
          dak<span className="brand-period">.</span>
        </NavLink>
        <div className="workspace-label">
          <span className="workspace-avatar">V</span>
          <span>
            Vantara Insurance<small>Demo workspace</small>
          </span>
          <span className="workspace-chevron" aria-hidden="true">
            ⌄
          </span>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <NavLink to="/" end>
            <Icon name="compose" />
            Compose
            <span className="nav-dot" />
          </NavLink>
          <NavLink to="/review">
            <Icon name="inbox" />
            Review desk
          </NavLink>
          <NavLink to="/dashboard">
            <Icon name="activity" />
            Activity
          </NavLink>
          <NavLink to="/eval">
            <Icon name="chart" />
            Evaluation
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <div className="human-note">
            <span className="human-note-icon">
              <Icon name="shield" />
            </span>
            <strong>A little human goes a long way.</strong>
            <p>
              Dak prepares the response.
              <br />
              You make the final call.
            </p>
            <NavLink to="/review">
              Visit the review desk <Icon name="arrow" size={15} />
            </NavLink>
          </div>
          <div className="workspace-user">
            <span className="user-avatar">VR</span>
            <span>
              Vantara reviewer<small>Local workspace</small>
            </span>
            <span className="user-presence" aria-hidden="true" />
          </div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="site-header">
          <div className="breadcrumb">
            <Icon name="layers" size={16} />
            <span>Workspace</span>
            <span aria-hidden="true">/</span>
            <strong>{section}</strong>
          </div>
          <span className="synthetic-tag">
            <span />
            SYNTHETIC DEMO
          </span>
        </header>
        <main id="main">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/runs/:id" element={<RunPage />} />
            <Route path="/t/:token" element={<PublicCase />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/eval" element={<EvalPage />} />
            <Route
              path="*"
              element={
                <div className="state">
                  <h1>Page not found</h1>
                  <NavLink to="/">Return to the mailroom</NavLink>
                </div>
              }
            />
          </Routes>
        </main>
        <footer>
          <span>
            <span className="footer-dot" />
            DAK · CORRESPONDENCE, CONSIDERED.
          </span>
          <span>Made for better decisions. Every reply stays a draft.</span>
        </footer>
      </div>
    </div>
  );
}

function App() {
  return <AuthGate><Workspace /></AuthGate>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
