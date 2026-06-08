// API client for the quarry extraction backend.
// Base URL is configurable via VITE_API_URL (Docker) and falls back to localhost.

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

export function createJob({ latitude, longitude, radius_km, max_usd_cost }) {
  const body = { latitude, longitude, radius_km };
  if (max_usd_cost) body.max_usd_cost = max_usd_cost;
  return request("/jobs", { method: "POST", body: JSON.stringify(body) });
}

export function getJob(jobId) {
  return request(`/jobs/${jobId}`);
}

export function listJobs(limit = 20) {
  return request(`/jobs?limit=${limit}`);
}

export function listSites({ q = "", status = "", page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  return request(`/sites?${params.toString()}`);
}

export function getSite(siteId) {
  return request(`/sites/${siteId}`);
}

export function getHealth() {
  return request("/health");
}
