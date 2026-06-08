import StatusBadge from "./StatusBadge.jsx";

// Helper: pull a grounded field's display value, or an abstention marker.
function fieldValue(field) {
  if (!field || field.value == null) return null;
  return field.value;
}

// List of quarry site cards. Clicking a card opens its full record.
export default function SiteList({ sites, onSelect }) {
  if (!sites || sites.length === 0) {
    return <div className="empty">No sites yet. Run an extraction to populate results.</div>;
  }

  return (
    <div>
      {sites.map((site) => {
        const name = fieldValue(site.extraction?.official_name) || "Unnamed candidate";
        const status = fieldValue(site.extraction?.operational_status);
        const materials = (site.extraction?.materials_produced || [])
          .map((m) => m.value)
          .filter(Boolean)
          .slice(0, 3);
        const sourceCount = site.provenance?.sources?.length || 0;

        return (
          <div key={site.site_id} className="site-card" onClick={() => onSelect(site.site_id)}>
            <div className="row-between">
              <span className="name">{name}</span>
              {status && <StatusBadge status={status} />}
            </div>
            <div className="meta">
              {materials.length > 0 && <>Materials: {materials.join(", ")} · </>}
              {sourceCount} source{sourceCount !== 1 ? "s" : ""} · {site.site_id}
            </div>
          </div>
        );
      })}
    </div>
  );
}
