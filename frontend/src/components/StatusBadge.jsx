// Small coloured pill showing a job or site status.

export default function StatusBadge({ status }) {
  if (!status) return null;
  return <span className={`badge ${status}`}>{status}</span>;
}
