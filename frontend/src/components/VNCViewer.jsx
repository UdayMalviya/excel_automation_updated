const novncUrl =
  import.meta.env.VITE_NOVNC_URL ||
  "http://localhost:6080/vnc.html?autoconnect=true&resize=remote";

function VNCViewer() {
  return (
    <div className="panel viewer-panel">
      <div className="panel-header">
        <h2>Live Browser View</h2>
        <span className="muted">noVNC</span>
      </div>
      <iframe
        title="Live noVNC Browser View"
        src={novncUrl}
        className="viewer-frame"
        allow="clipboard-read; clipboard-write"
      />
    </div>
  );
}

export default VNCViewer;

