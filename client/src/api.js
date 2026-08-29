const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

/** GET /api/weather/live */
export function fetchLiveWeather() {
  return request("/api/weather/live");
}

/** POST /api/predict */
export function predictPrice({ temperature, rainfall, humidity, last_price }) {
  return request("/api/predict", {
    method: "POST",
    body: JSON.stringify({ temperature, rainfall, humidity, last_price }),
  });
}

/** POST /api/advice */
export function getAdvice({ temperature, rainfall, humidity, last_price }) {
  return request("/api/advice", {
    method: "POST",
    body: JSON.stringify({ temperature, rainfall, humidity, last_price }),
  });
}
