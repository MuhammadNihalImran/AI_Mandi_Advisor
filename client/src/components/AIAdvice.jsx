import { useState } from "react";
import { getAdvice } from "../api";

export default function AIAdvice({ inputs }) {
  const [advice, setAdvice] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [show, setShow] = useState(false);

  async function handleAsk() {
    setLoading(true);
    setError("");
    setShow(true);
    setAdvice("");
    setHistory([]);

    try {
      const data = await getAdvice(inputs);
      setAdvice(data.advice);
      setHistory(data.retrieved_history || []);
    } catch (err) {
      setShow(false);
      setError(
        `AI advisory abhi load nahi ho saki. Dobara try karein. (${err.message})`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button className="ask" onClick={handleAsk} disabled={loading}>
        {loading ? "Soch raha hoon..." : "Farmer advice lein (AI)"}
      </button>
      {error && <div className="error-text">{error}</div>}

      {show && (
        <div className="advice-box">
          <div className="who">AI advisory</div>
          {loading ? (
            <p className="loading">
              Similar din retrieve kar raha hoon aur AI advisory taiyar kar
              raha hoon...
            </p>
          ) : (
            <p>{advice}</p>
          )}

          {history.length > 0 && !loading && (
            <div className="rag-context">
              <div className="rag-label">Retrieved similar days (RAG)</div>
              <div className="rag-list">
                {history.map((day, i) => (
                  <span key={i}>
                    {day.date} &middot; {day.temperature}&deg;C, {day.rainfall}
                    mm rain, {day.humidity}% hum &rarr; Rs {day.price}/kg
                    {i < history.length - 1 && <br />}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
