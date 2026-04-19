import { useState } from "react";
import ControlPanel from "../components/ControlPanel";
import VNCViewer from "../components/VNCViewer";
import LogsPanel from "../components/LogsPanel";
import { getDownloadUrl, startTask, submitCaptcha } from "../services/api";

const initialLogs = [
  {
    timestamp: new Date().toISOString(),
    stage: "ui",
    message: "Platform ready",
  },
];

function Dashboard() {
  const [url, setUrl] = useState("https://mpapexbankutility.bank.in/");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [excelFile, setExcelFile] = useState(null);
  const [captchaText, setCaptchaText] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [logs, setLogs] = useState(initialLogs);

  const handleStart = async () => {
    if (!url.trim() || !username.trim() || !password.trim()) {
      const message = "URL, username, and password are required before starting automation.";
      setStatus("error");
      setResult({
        status: "error",
        message,
      });
      setLogs((current) => [
        {
          timestamp: new Date().toISOString(),
          stage: "validation",
          message,
        },
        ...current,
      ]);
      return;
    }

    setStatus("running");
    setLogs((current) => [
      {
        timestamp: new Date().toISOString(),
        stage: "ui",
        message: excelFile
          ? `Opening automation session for ${url} using ${excelFile.name}`
          : `Opening automation session for ${url}`,
      },
      ...current,
    ]);

    try {
      const response = await startTask({
        url,
        username,
        password,
        excel_file: excelFile,
      });
      setResult(response);
      setStatus(response.status);
      setSessionId(response.session_id || "");
      setLogs([
        ...response.logs.slice().reverse(),
        {
          timestamp: new Date().toISOString(),
          stage: "ui",
          message: "Browser is waiting for CAPTCHA input",
        },
      ]);
    } catch (error) {
      const message =
        error?.response?.data?.message ||
        error?.message ||
        "Unknown error";

      setStatus("error");
      setSessionId("");
      setResult({
        status: "error",
        message,
      });
      setLogs((current) => [
        {
          timestamp: new Date().toISOString(),
          stage: "error",
          message,
        },
        ...current,
      ]);
    }
  };

  const handleSubmitCaptcha = async () => {
    if (!sessionId) {
      return;
    }

    setStatus("running");
    setLogs((current) => [
      {
        timestamp: new Date().toISOString(),
        stage: "ui",
        message: "Submitting CAPTCHA for the active session",
      },
      ...current,
    ]);

    try {
      const response = await submitCaptcha({
        session_id: sessionId,
        captcha_text: captchaText,
      });
      setResult(response);
      setStatus(response.status);
      setSessionId("");
      setCaptchaText("");
      setLogs([
        ...response.logs.slice().reverse(),
        {
          timestamp: new Date().toISOString(),
          stage: "ui",
          message: "CAPTCHA submitted and automation continued",
        },
      ]);
    } catch (error) {
      const message =
        error?.response?.data?.message ||
        error?.message ||
        "Unknown error";

      setStatus("error");
      setResult({
        status: "error",
        message,
      });
      setLogs((current) => [
        {
          timestamp: new Date().toISOString(),
          stage: "error",
          message,
        },
        ...current,
      ]);
    }
  };

  return (
    <main className="dashboard-shell">
      <section className="hero-card">
        <div>
          <p className="eyebrow">Visible Browser Automation</p>
          <h1>Run Playwright and watch it live.</h1>
          <p className="hero-copy">
            This dashboard triggers FastAPI automation jobs, streams the
            browser through noVNC, and surfaces structured execution output in
            one place.
          </p>
        </div>
        <ControlPanel
          url={url}
          setUrl={setUrl}
          username={username}
          setUsername={setUsername}
          password={password}
          setPassword={setPassword}
          excelFile={excelFile}
          setExcelFile={setExcelFile}
          captchaText={captchaText}
          setCaptchaText={setCaptchaText}
          sessionId={sessionId}
          status={status}
          result={
            result
              ? {
                  ...result,
                  download_url: getDownloadUrl(result.download_path),
                }
              : null
          }
          onStart={handleStart}
          onSubmitCaptcha={handleSubmitCaptcha}
        />
      </section>

      <section className="content-grid">
        <VNCViewer />
        <LogsPanel logs={logs} result={result} />
      </section>
    </main>
  );
}

export default Dashboard;
