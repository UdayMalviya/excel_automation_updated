function ControlPanel({
  url,
  setUrl,
  username,
  setUsername,
  password,
  setPassword,
  excelFile,
  setExcelFile,
  captchaText,
  setCaptchaText,
  sessionId,
  status,
  result,
  onStart,
  onSubmitCaptcha,
}) {
  const statusClass =
    {
      idle: "bg-slate-400/15 text-slate-200",
      running: "bg-amber-300/20 text-amber-100",
      success: "bg-emerald-300/20 text-emerald-100",
      error: "bg-red-300/20 text-red-100",
    }[status] || "bg-slate-400/15 text-slate-200";

  const inputClass =
    "w-full rounded-[14px] border border-slate-200/20 bg-slate-950/60 px-4 py-3.5 text-slate-100 outline-none transition placeholder:text-slate-300/40 focus:border-emerald-200/60 focus:ring-2 focus:ring-emerald-200/20 disabled:cursor-not-allowed disabled:opacity-60";
  const labelClass = "grid gap-2 mb-4";
  const primaryButtonClass =
    "w-full rounded-2xl border-0 bg-gradient-to-br from-emerald-200 to-emerald-400 px-[18px] py-3.5 font-bold text-emerald-950 transition hover:-translate-y-px hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:translate-y-0";
  const secondaryButtonClass =
    "mt-3 bg-gradient-to-br from-slate-600 to-slate-800 text-slate-100";

  return (
    <div className="rounded-3xl border border-slate-200/15 bg-slate-950/80 p-5 shadow-2xl shadow-slate-950/30 backdrop-blur-xl max-sm:rounded-2xl max-sm:p-4">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <span
          className={`rounded-full px-3 py-1.5 text-xs uppercase tracking-wide ${statusClass}`}
        >
          {status}
        </span>
      </div>

      <label className={labelClass}>
        <span>Target URL</span>
        <input
          className={inputClass}
          type="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://example.com"
        />
      </label>

      <label className={labelClass}>
        <span>Username</span>
        <input
          className={inputClass}
          type="text"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Enter username"
          autoComplete="username"
        />
      </label>

      <label className={labelClass}>
        <span>Password</span>
        <input
          className={inputClass}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Enter password"
          autoComplete="current-password"
        />
      </label>

      <label className={labelClass}>
        <span>Excel File</span>
        <input
          className={inputClass}
          type="file"
          accept=".xlsx,.xls"
          onChange={(event) => setExcelFile(event.target.files?.[0] || null)}
          disabled={status === "running" || Boolean(sessionId)}
        />
        <small className="text-sm text-slate-200/60">
          Upload the transaction sheet here. The backend will read the Excel row instead of manual entry fields.
        </small>
        {excelFile ? (
          <span className="inline-flex w-fit items-center rounded-full border border-emerald-200/25 bg-emerald-300/15 px-2.5 py-1.5 text-sm text-emerald-100">
            {excelFile.name}
          </span>
        ) : null}
      </label>

      <label className={labelClass}>
        <span>CAPTCHA</span>
        <input
          className={inputClass}
          type="text"
          value={captchaText}
          onChange={(event) => setCaptchaText(event.target.value)}
          placeholder="Enter CAPTCHA text"
          disabled={!sessionId}
        />
      </label>

      <button
        className={primaryButtonClass}
        onClick={onStart}
        disabled={status === "running" || Boolean(sessionId)}
      >
        {status === "running" ? "Opening Browser..." : "Run Automation"}
      </button>

      <button
        className={`${primaryButtonClass} ${secondaryButtonClass}`}
        onClick={onSubmitCaptcha}
        disabled={status === "running" || !sessionId || !captchaText.trim()}
      >
        Submit CAPTCHA
      </button>

      <div className="mt-4 rounded-2xl border border-slate-200/10 bg-slate-950/50 p-4">
        <h3 className="mb-2 text-lg font-semibold">Latest Result</h3>
        <p>{result?.message || "No automation run yet."}</p>
        {result?.title ? (
          <p className="text-slate-200/70">Page title: {result.title}</p>
        ) : null}
        {sessionId ? (
          <p className="break-all text-slate-200/70">Session: {sessionId}</p>
        ) : null}
        {result?.source_file_name ? (
          <p className="text-slate-200/70">
            Excel source: {result.source_file_name}
            {result.source_row_number ? `, row ${result.source_row_number}` : ""}
          </p>
        ) : null}
        {result?.result_file_name ? (
          <p className="text-slate-200/70">Processed file: {result.result_file_name}</p>
        ) : null}
        {result?.download_url ? (
          <a
            className={`${primaryButtonClass} mt-3 inline-flex w-auto items-center justify-center no-underline`}
            href={result.download_url}
            download={result.result_file_name || true}
          >
            Download Excel
          </a>
        ) : null}
        {result?.log_download_url ? (
          <a
            className={`${primaryButtonClass} mt-3 inline-flex w-auto items-center justify-center no-underline`}
            href={result.log_download_url}
            download={result.log_file_name || true}
          >
            Download Logs
          </a>
        ) : null}
      </div>
    </div>
  );
}

export default ControlPanel;
