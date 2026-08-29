import { useState } from "react";
import { fetchLiveWeather } from "../api";

export default function WeatherInputs({ inputs, setInputs, onWeatherFetched }) {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  function handleChange(field, raw) {
    const value = parseFloat(raw);
    setInputs((prev) => ({ ...prev, [field]: value }));
  }

  async function handleLiveWeather() {
    setLoading(true);
    setStatus("Fetching...");
    try {
      const data = await fetchLiveWeather();
      const updated = {
        temperature: Math.round(data.temperature),
        rainfall: parseFloat(data.rainfall),
        humidity: Math.round(data.humidity),
      };
      setInputs((prev) => ({ ...prev, ...updated }));
      onWeatherFetched?.(updated);
      setStatus(
        `Live weather load ho gaya (${new Date().toLocaleTimeString()})`
      );
    } catch (err) {
      setStatus(`Live weather fetch nahi ho saka - ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <p className="section-label">Aaj ka mausam aur mandi</p>
      <div className="inputs-grid">
        <div className="field">
          <label>
            Temperature{" "}
            <span className="val">{inputs.temperature}&deg;C</span>
          </label>
          <input
            type="range"
            min="5"
            max="45"
            step="1"
            value={inputs.temperature}
            onChange={(e) => handleChange("temperature", e.target.value)}
          />
        </div>

        <div className="field">
          <label>
            Rainfall{" "}
            <span className="val">
              {inputs.rainfall.toFixed(1)} mm
            </span>
          </label>
          <input
            type="range"
            min="0"
            max="30"
            step="0.5"
            value={inputs.rainfall}
            onChange={(e) => handleChange("rainfall", e.target.value)}
          />
        </div>

        <div className="field">
          <label>
            Humidity <span className="val">{inputs.humidity}%</span>
          </label>
          <input
            type="range"
            min="15"
            max="95"
            step="1"
            value={inputs.humidity}
            onChange={(e) => handleChange("humidity", e.target.value)}
          />
        </div>

        <div className="field">
          <label>Pichla mandi rate (Rs/kg)</label>
          <input
            type="number"
            value={inputs.last_price}
            step="1"
            onChange={(e) => handleChange("last_price", e.target.value)}
          />
        </div>
      </div>

      <button
        className="ask ask-outline"
        onClick={handleLiveWeather}
        disabled={loading}
      >
        {loading ? "Fetching..." : "Live Faisalabad weather fetch karein"}
      </button>
      {status && <div className="status-text">{status}</div>}
    </>
  );
}
