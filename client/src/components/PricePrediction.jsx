import { useState, useEffect } from "react";
import { predictPrice } from "../api";

export default function PricePrediction({ inputs, onPrediction }) {
  const [predicted, setPredicted] = useState(null);
  const [delta, setDelta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    predictPrice(inputs)
      .then((data) => {
        if (cancelled) return;
        setPredicted(data.predicted_price);
        setDelta(data.delta_pct);
        onPrediction?.(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    inputs.temperature,
    inputs.rainfall,
    inputs.humidity,
    inputs.last_price,
  ]);

  let deltaClass = "delta flat";
  let deltaText = "lagbhag same";
  if (delta !== null) {
    if (delta > 3) {
      deltaClass = "delta up";
      deltaText = `+${Math.round(delta)}% pichle se`;
    } else if (delta < -3) {
      deltaClass = "delta down";
      deltaText = `${Math.round(delta)}% pichle se`;
    }
  }

  const priceText =
    loading ? null : predicted !== null ? `Rs ${predicted.toLocaleString()}` : null;

  return (
    <>
      <div className="ticker">
        {loading ? (
          <div className="ticker-loading">Rate calculate ho raha hai...</div>
        ) : priceText ? (
          <div className="ticker-track">
            {[0, 1].map((i) => (
              <span className="ticker-item" key={i}>
                <span className="price">{priceText}</span>
                <span className="unit">/kg</span>
              </span>
            ))}
          </div>
        ) : (
          <div className="ticker-waiting">Rate board taiyar hai</div>
        )}
      </div>

      {priceText && (
        <div className="ticker-meta">
          <span className="ml-note">
            Ridge regression, trained: 11 real mandi weeks (Faisalabad)
          </span>
          <span className={deltaClass}>{deltaText}</span>
        </div>
      )}

      {error && <div className="error-text">{error}</div>}
    </>
  );
}
