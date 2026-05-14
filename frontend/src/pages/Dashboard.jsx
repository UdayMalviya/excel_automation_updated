import { useState } from "react";
import ControlPanel from "../components/ControlPanel";
import VNCViewer from "../components/VNCViewer";
// import LogsPanel from "../components/LogsPanel";
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
    <main className="mx-auto min-h-screen w-[calc(100%_-_32px)] max-w-[1400px] py-6 pb-8 max-sm:w-[calc(100%_-_20px)] max-sm:pt-4">
      <section className="mb-5 grid grid-cols-[1.3fr_0.9fr] items-start gap-5 rounded-3xl border border-slate-200/15 bg-slate-950/80 p-7 shadow-2xl shadow-slate-950/30 backdrop-blur-xl max-[1080px]:grid-cols-1 max-sm:rounded-2xl max-sm:p-4">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald-200">
            Visible Browser Automation
          </p>
          <h1 className="mb-3.5 text-[clamp(2rem,3vw,3.5rem)] font-bold leading-[1.05]">
            Run Playwright and watch it live.
          </h1>
          <p className="text-slate-200/70">
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
                  log_download_url: getDownloadUrl(result.log_download_path),
                }
              : null
          }
          onStart={handleStart}
          onSubmitCaptcha={handleSubmitCaptcha}
        />
      </section>

      {/* <section className="grid grid-cols-[1.35fr_0.85fr] gap-5 max-[1080px]:grid-cols-1 w-full"> */}
      <section className="w-full">
        <VNCViewer />
        {/* <LogsPanel logs={logs} result={result} /> */}
      </section>
    </main>
  );
}

export default Dashboard;
