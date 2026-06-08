import { useState } from "react";

// Form to submit a new extraction job (coordinate + radius + optional budget).
export default function JobForm({ onSubmit, disabled }) {
  const [lat, setLat] = useState("45.764");
  const [lon, setLon] = useState("4.835");
  const [radius, setRadius] = useState("30");
  const [budget, setBudget] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit({
      latitude: parseFloat(lat),
      longitude: parseFloat(lon),
      radius_km: parseFloat(radius),
      max_usd_cost: budget ? parseFloat(budget) : undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="lat">Latitude</label>
      <input id="lat" value={lat} onChange={(e) => setLat(e.target.value)} required />

      <label htmlFor="lon">Longitude</label>
      <input id="lon" value={lon} onChange={(e) => setLon(e.target.value)} required />

      <label htmlFor="radius">Radius (km)</label>
      <input id="radius" value={radius} onChange={(e) => setRadius(e.target.value)} required />

      <label htmlFor="budget">Max cost USD (optional)</label>
      <input
        id="budget"
        value={budget}
        onChange={(e) => setBudget(e.target.value)}
        placeholder="e.g. 2.00"
      />

      <button type="submit" disabled={disabled}>
        {disabled ? "Running..." : "Start extraction"}
      </button>
    </form>
  );
}
