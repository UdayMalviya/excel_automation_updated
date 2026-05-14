const novncUrl =
  import.meta.env.VITE_NOVNC_URL ||
  "http://localhost:6080/vnc.html?autoconnect=true&resize=remote";

function VNCViewer() {
  return (
    <div className="rounded-3xl border border-slate-200/15 bg-slate-950/80 p-5 shadow-2xl shadow-slate-950/30 backdrop-blur-xl max-sm:rounded-2xl max-sm:p-4">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-2xl font-semibold">Live Browser View</h2>
        <span className="text-slate-200/70">noVNC</span>
      </div>
      <iframe
        title="Live noVNC Browser View"
        src={novncUrl}
        className="min-h-[620px] w-full rounded-[18px] border-0 bg-slate-950 max-[1080px]:min-h-[460px] max-sm:min-h-[360px]"
        allow="clipboard-read; clipboard-write"
      />
    </div>
  );
}

export default VNCViewer;
