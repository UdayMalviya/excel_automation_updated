// function LogsPanel({ logs, result }) {
//   return (
//     <div className="rounded-3xl border border-slate-200/15 bg-slate-950/80 p-5 shadow-2xl shadow-slate-950/30 backdrop-blur-xl max-sm:rounded-2xl max-sm:p-4">
//       <div className="mb-4 flex items-center justify-between gap-4">
//         <h2 className="text-2xl font-semibold">Execution Logs</h2>
//         <span className="text-slate-200/70">API + UI</span>
//       </div>

//       <pre className="mb-3.5 max-h-[220px] overflow-auto rounded-2xl border border-slate-200/10 bg-slate-950/50 p-3.5 text-sm">
//         {JSON.stringify(result || { status: "idle" }, null, 2)}
//       </pre>

//       <div className="grid max-h-[440px] gap-3 overflow-auto">
//         {logs.map((log, index) => (
//           <article
//             className="rounded-2xl border border-slate-200/10 bg-slate-950/50 p-3.5"
//             key={`${log.timestamp}-${index}`}
//           >
//             <div className="mb-2 flex justify-between gap-3 text-sm text-slate-200/60">
//               <span>{log.stage}</span>
//               <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
//             </div>
//             <p>{log.message}</p>
//           </article>
//         ))}
//       </div>
//     </div>
//   );
// }

// export default LogsPanel;
