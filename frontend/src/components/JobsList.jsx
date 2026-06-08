import StatusBadge from "./StatusBadge.jsx";

// Compact list of recent jobs with their live status and progress.
export default function JobsList({ jobs, activeJobId }) {
  if (!jobs || jobs.length === 0) {
    return <div className="empty">No jobs yet.</div>;
  }

  return (
    <div>
      {jobs.map((job) => {
        const running = job.status === "running" || job.status === "pending";
        return (
          <div
            key={job.id}
            className="site-card"
            style={job.id === activeJobId ? { borderColor: "var(--accent)" } : undefined}
          >
            <div className="row-between">
              <span className="name" style={{ fontSize: 13 }}>
                {job.latitude.toFixed(3)}, {job.longitude.toFixed(3)} · {job.radius_km} km
              </span>
              <StatusBadge status={job.status} />
            </div>
            <div className="meta">
              {running ? (
                <>
                  {job.progress}% — {job.status_message || "starting…"}
                </>
              ) : (
                <>
                  {job.sites_found} site(s) · {new Date(job.created_at).toLocaleString()}
                </>
              )}
            </div>
            {running && (
              <div className="progress-track" style={{ marginTop: 6 }}>
                <div className="progress-fill" style={{ width: `${job.progress}%` }} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
