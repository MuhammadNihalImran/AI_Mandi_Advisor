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

  // Delta class
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

  return (
    <>
      <div className="ticket">
        <div>
          <div className="label">Predicted rate (agla)</div>
          <div className="price">
            Rs {loading ? "..." : predicted !== null ? predicted.toLocaleString() : "--"}{" "}
            <small>/kg</small>
          </div>
          <div className="ml-note">
            Ridge regression &middot; trained: 11 real mandi weeks (Faisalabad)
          </div>
        </div>
        <div className={deltaClass}>{predicted !== null ? deltaText : ""}</div>
      </div>
      {error && <div className="error-text">{error}</div>}
    </>
  );
}
