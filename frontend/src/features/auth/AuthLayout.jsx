import { Link } from "react-router-dom";

import "./login.css";
import loginIllustration from "../../assets/images/loginIllustration.png";

// Shared shell of the login and sign-up pages: brand, avatar, heading and
// the illustration panel. Each page supplies its own form as `children`.
function AuthLayout({ title, subtitle, children }) {
  return (
    <main className="login-page">
      <section className="login-panel">
        <Link to="/" className="login-brand">
          <span className="login-brand-mark">P</span>
          <span>PublishPro<span className="brand-ai">-AI</span></span>
        </Link>

        <div className="login-content">
          <div className="login-avatar" aria-hidden="true">
            <svg viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="23" fill="#FCE7E7" />
              <circle cx="24" cy="18" r="8" fill="#EFAE91" />
              <path
                d="M16 17C16 7 32 7 32 17C29 14 20 14 16 17Z"
                fill="#762D35"
              />
              <path
                d="M10 42C11 31 17 27 24 27C31 27 37 31 38 42"
                fill="#D94B55"
              />
            </svg>
          </div>

          <h1>{title}</h1>
          <p className="login-subtitle">{subtitle}</p>

          {children}
        </div>

        <p className="login-legal">
          © 2026 PublishPro-AI
        </p>
      </section>

      <section className="login-visual" aria-label="AI content creation">
        <div className="visual-glow visual-glow-one" />
        <div className="visual-glow visual-glow-two" />

        <div className="visual-copy">
          <span className="visual-eyebrow">
            <span className="status-dot" />
            YOUR AI CONTENT STUDIO
          </span>

          <h2>
            Create better.
            <br />
            <span>Publish smarter.</span>
          </h2>

          <p>
            Turn your video ideas into content that stands out.
            One workspace, endless possibilities.
          </p>
        </div>

        <div className="illustration-stage">
          <div className="floating-card floating-video">
            <span className="floating-icon video-icon">▶</span>
            <span>
              <strong>Video ready</strong>
              <small>Content creation</small>
            </span>
          </div>

          <div className="floating-card floating-hashtag">
            <span className="floating-icon hashtag-icon">#</span>
            <span>
              <strong>#Trending</strong>
              <small>Smart hashtags</small>
            </span>
          </div>

          <div className="floating-card floating-ai">
            <span className="floating-icon ai-icon">✦</span>
            <span>
              <strong>AI magic</strong>
              <small>Optimized for you</small>
            </span>
          </div>

          <div className="illustration-orbit" />

          <img
            className="login-illustration"
            src={loginIllustration}
            alt="Creator using a phone surrounded by video and AI icons"
          />

          <div className="visual-bottom-pill">
            <span className="bottom-pill-sparkle">✦</span>
            Your creativity, upgraded
          </div>
        </div>
      </section>
    </main>
  );
}

export default AuthLayout;
