import StatusBadge from "./StatusBadge.jsx";

// Resolve a source_id to its URL for evidence links.
function sourceUrl(sources, sourceId) {
  const src = (sources || []).find((s) => s.source_id === sourceId);
  return src?.url;
}

// Render the evidence quotes that ground a field value.
function Evidence({ evidence, sources }) {
  if (!evidence || evidence.length === 0) return null;
  return (
    <>
      {evidence.map((ev, i) => {
        const url = sourceUrl(sources, ev.source_id);
        return (
          <div className="evidence" key={i}>
            <span className="quote">“{ev.quote}”</span>
            <br />
            {url ? (
              <a href={url} target="_blank" rel="noreferrer">
                {ev.source_id}
              </a>
            ) : (
              ev.source_id
            )}{" "}
            (chars {ev.char_start}–{ev.char_end})
          </div>
        );
      })}
    </>
  );
}

// Render a single grounded field (scalar): value + confidence + evidence, or abstention.
function GroundedField({ label, field, sources }) {
  if (!field) return null;
  const abstained = field.value == null;
  return (
    <div className="field-row">
      <div className="field-label">{label}</div>
      <div className="field-value">
        {abstained ? (
          <span className="abstain">abstained — {field.abstain_reason || "no evidence"}</span>
        ) : (
          <>
            {String(field.value)}
            <span className="confidence">conf {field.confidence?.toFixed(2)}</span>
            <Evidence evidence={field.evidence} sources={sources} />
          </>
        )}
      </div>
    </div>
  );
}

// Render an array field (materials, certifications) as a list of grounded values.
function ArrayField({ label, items, sources }) {
  if (!items || items.length === 0) {
    return (
      <div className="field-row">
        <div className="field-label">{label}</div>
        <div className="field-value">
          <span className="abstain">none</span>
        </div>
      </div>
    );
  }
  return (
    <div className="field-row">
      <div className="field-label">{label}</div>
      <div className="field-value">
        {items.map((item, i) => (
          <div key={i} style={{ marginBottom: 8 }}>
            {item.value}
            <span className="confidence">conf {item.confidence?.toFixed(2)}</span>
            <Evidence evidence={item.evidence} sources={sources} />
          </div>
        ))}
      </div>
    </div>
  );
}

// Full record view for a single quarry: extraction, provenance, metrics.
export default function SiteDetail({ site, onBack }) {
  if (!site) return null;
  const ex = site.extraction || {};
  const sources = site.provenance?.sources || [];
  const metrics = site.metrics || {};

  return (
    <div className="panel">
      <div className="row-between" style={{ marginBottom: 16 }}>
        <button className="link-btn" onClick={onBack}>
          ← Back to list
        </button>
        <span style={{ fontSize: 12, color: "var(--muted)" }}>{site.site_id}</span>
      </div>

      <h2>Extraction</h2>
      <GroundedField label="Official name" field={ex.official_name} sources={sources} />
      <GroundedField label="Site type" field={ex.site_type} sources={sources} />
      <GroundedField label="Operational status" field={ex.operational_status} sources={sources} />
      <GroundedField label="Description" field={ex.description} sources={sources} />
      <ArrayField label="Materials produced" items={ex.materials_produced} sources={sources} />
      <ArrayField label="Certifications" items={ex.certifications} sources={sources} />

      <h2 style={{ marginTop: 24 }}>Provenance — {sources.length} source(s)</h2>
      {sources.map((s) => (
        <div className="field-row" key={s.source_id}>
          <div className="field-label">
            {s.source_id} <StatusBadge status={s.trust_tier} />
          </div>
          <div className="field-value" style={{ fontSize: 13 }}>
            <a href={s.url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
              {s.url}
            </a>
          </div>
        </div>
      ))}

      {site.provenance?.reconciliations?.length > 0 && (
        <>
          <h2 style={{ marginTop: 24 }}>Reconciliations</h2>
          {site.provenance.reconciliations.map((r, i) => (
            <div className="field-row" key={i}>
              <div className="field-label">{r.field}</div>
              <div className="field-value" style={{ fontSize: 13 }}>
                Winner: {r.winner_source_id} — {r.reason}
              </div>
            </div>
          ))}
        </>
      )}

      <div className="metrics-line">
        {metrics.llm_tokens_in + metrics.llm_tokens_out} tokens · $
        {metrics.usd_cost?.toFixed(4)} · {metrics.latency_ms} ms ·{" "}
        {metrics.model_calls?.length || 0} model call(s)
      </div>
    </div>
  );
}
