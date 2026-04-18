function ControlPanel({
  url,
  setUrl,
  username,
  setUsername,
  password,
  setPassword,
  captchaText,
  setCaptchaText,
  sessionId,
  status,
  result,
  onStart,
  onSubmitCaptcha,
}) {
  return (
    <div className="panel control-panel">
      <div className="panel-header">
        <h2>Dashboard</h2>
        <span className={`status-pill status-${status}`}>{status}</span>
      </div>

      <label className="field">
        <span>Target URL</span>
        <input
          type="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://example.com"
        />
      </label>

      <label className="field">
        <span>Username</span>
        <input
          type="text"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Enter username"
          autoComplete="username"
        />
      </label>

      <label className="field">
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Enter password"
          autoComplete="current-password"
        />
      </label>

      <label className="field">
        <span>CAPTCHA</span>
        <input
          type="text"
          value={captchaText}
          onChange={(event) => setCaptchaText(event.target.value)}
          placeholder="Enter CAPTCHA text"
          disabled={!sessionId}
        />
      </label>

      <button className="primary-button" onClick={onStart} disabled={status === "running" || Boolean(sessionId)}>
        {status === "running" ? "Opening Browser..." : "Run Automation"}
      </button>

      <button
        className="primary-button secondary-button"
        onClick={onSubmitCaptcha}
        disabled={status === "running" || !sessionId || !captchaText.trim()}
      >
        Submit CAPTCHA
      </button>

      <div className="result-card">
        <h3>Latest Result</h3>
        <p>{result?.message || "No automation run yet."}</p>
        {result?.title ? <p className="muted">Page title: {result.title}</p> : null}
        {sessionId ? <p className="muted">Session: {sessionId}</p> : null}
      </div>
    </div>
  );
}

export default ControlPanel;
