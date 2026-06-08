import { useEffect, useState, useCallback } from "react";
import * as api from "../api/client.js";
import JobForm from "../components/JobForm.jsx";
import JobsList from "../components/JobsList.jsx";
import SiteList from "../components/SiteList.jsx";
import SiteDetail from "../components/SiteDetail.jsx";

const POLL_INTERVAL_MS = 2000;

export default function HomePage() {
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);
  const [sites, setSites] = useState([]);
  const [selectedSite, setSelectedSite] = useState(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState(null);

  // True while any job in the list is still running — drives polling.
  const anyRunning = jobs.some((j) => j.status === "running" || j.status === "pending");

  const loadJobs = useCallback(async () => {
    try {
      const data = await api.listJobs(20);
      setJobs(data);
      return data;
    } catch (e) {
      setError(e.message);
      return [];
    }
  }, []);

  const loadSites = useCallback(async () => {
    try {
      const data = await api.listSites({ q: query, status: statusFilter, pageSize: 50 });
      setSites(data.items);
    } catch (e) {
      setError(e.message);
    }
  }, [query, statusFilter]);

  // Initial load of jobs + sites.
  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    loadSites();
  }, [loadSites]);

  // Poll the jobs list while any job is running; refresh sites when one finishes.
  useEffect(() => {
    if (!anyRunning) return;
    const timer = setInterval(async () => {
      const updated = await loadJobs();
      const stillRunning = updated.some(
        (j) => j.status === "running" || j.status === "pending"
      );
      if (!stillRunning) loadSites();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [anyRunning, loadJobs, loadSites]);

  async function handleSubmit(payload) {
    setError(null);
    setSelectedSite(null);
    try {
      const created = await api.createJob(payload);
      setActiveJobId(created.id);
      await loadJobs();
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleSelect(siteId) {
    setError(null);
    try {
      const site = await api.getSite(siteId);
      setSelectedSite(site);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="grid">
      <div>
        <div className="panel">
          <h2>New extraction</h2>
          <JobForm onSubmit={handleSubmit} disabled={anyRunning} />
        </div>

        <div className="panel" style={{ marginTop: 16 }}>
          <div className="row-between" style={{ marginBottom: 12 }}>
            <h2 style={{ margin: 0 }}>Jobs — {jobs.length}</h2>
            <button className="link-btn" onClick={loadJobs}>
              ↻ Refresh
            </button>
          </div>
          <JobsList jobs={jobs} activeJobId={activeJobId} />
        </div>
      </div>

      <div>
        {error && <div className="error-box">{error}</div>}

        {selectedSite ? (
          <SiteDetail site={selectedSite} onBack={() => setSelectedSite(null)} />
        ) : (
          <div className="panel">
            <div className="row-between" style={{ marginBottom: 16 }}>
              <h2 style={{ margin: 0 }}>Results — {sites.length}</h2>
              <button className="link-btn" onClick={loadSites}>
                ↻ Refresh
              </button>
            </div>

            <div className="toolbar">
              <input
                placeholder="Search by name…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>

            <SiteList sites={sites} onSelect={handleSelect} />
          </div>
        )}
      </div>
    </div>
  );
}
