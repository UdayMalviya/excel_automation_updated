function LogsPanel({ logs, result }) {
  return (
    <div className="panel logs-panel">
      <div className="panel-header">
        <h2>Execution Logs</h2>
        <span className="muted">API + UI</span>
      </div>

      <pre className="response-preview">
        {JSON.stringify(result || { status: "idle" }, null, 2)}
      </pre>

      <div className="log-list">
        {logs.map((log, index) => (
          <article className="log-item" key={`${log.timestamp}-${index}`}>
            <div className="log-meta">
              <span>{log.stage}</span>
              <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
            </div>
            <p>{log.message}</p>
          </article>
        ))}
      </div>
    </div>
  );
}

export default LogsPanel;

