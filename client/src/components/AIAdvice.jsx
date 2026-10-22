import { useState } from "react";
import { getAdvice, submitFeedback } from "../api";

export default function AIAdvice({ inputs }) {
  const [advice, setAdvice] = useState("");
  const [history, setHistory] = useState([]);
  const [predictedPrice, setPredictedPrice] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [show, setShow] = useState(false);

  // Feedback flow: "ask" -> (Sahi -> "done") | (Galat -> "wrong" -> "done")
  const [stage, setStage] = useState("ask");
  const [reportedPrice, setReportedPrice] = useState("");
  const [note, setNote] = useState("");
  const [fbLoading, setFbLoading] = useState(false);
  const [fbError, setFbError] = useState("");
  const [fbResult, setFbResult] = useState(null);

  async function handleAsk() {
    setLoading(true);
    setError("");
    setShow(true);
    setAdvice("");
    setHistory([]);
    setStage("ask");
    setReportedPrice("");
    setNote("");
    setFbError("");
    setFbResult(null);

    try {
      const data = await getAdvice(inputs);
      setAdvice(data.advice);
      setHistory(data.retrieved_history || []);
      setPredictedPrice(data.predicted_price);
    } catch (err) {
      setShow(false);
      setError(
        `AI advisory abhi load nahi ho saki. Dobara try karein. (${err.message})`
      );
    } finally {
      setLoading(false);
    }
  }

  // Build the feedback payload from the current inputs + prediction.
  function baseFeedback() {
    return {
      temperature: inputs.temperature,
      rainfall: inputs.rainfall,
      humidity: inputs.humidity,
      last_price: inputs.last_price,
      predicted_price: predictedPrice,
    };
  }

  async function handleSahi() {
    setFbLoading(true);
    setFbError("");
    try {
      // "Sahi": reported price equals what the model predicted; no note,
      // no regeneration.
      const data = await submitFeedback({
        ...baseFeedback(),
        reported_price: predictedPrice,
        note: null,
        regenerate: false,
      });
      setFbResult(data);
      setStage("done");
    } catch (err) {
      setFbError(`Report nahi bhej sake. Dobara try karein. (${err.message})`);
    } finally {
      setFbLoading(false);
    }
  }

  function handleGalat() {
    setStage("wrong");
    setFbError("");
  }

  async function handleWrongSubmit(e) {
    e.preventDefault();
    const reported = Number(reportedPrice);
    if (!reportedPrice || Number.isNaN(reported) || reported <= 0) {
      setFbError("Barah-e-karam asal rate (PKR/kg) likhein.");
      return;
    }
    setFbLoading(true);
    setFbError("");
    try {
      // "Galat": send the farmer's real rate + optional note and ask the
      // backend to regenerate the advisory text (Ridge price won't change).
      const data = await submitFeedback({
        ...baseFeedback(),
        reported_price: reported,
        note: note.trim() ? note : null,
        regenerate: true,
      });
      setFbResult(data);
      setStage("done");
    } catch (err) {
      setFbError(`Report nahi bhej sake. Dobara try karein. (${err.message})`);
    } finally {
      setFbLoading(false);
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
                  <span className="stamp" key={i}>
                    {day.date}: {day.temperature}&deg;C, {day.rainfall}mm rain,{" "}
                    {day.humidity}% hum &rarr; Rs {day.price}/kg
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ---- Price-correction feedback ---- */}
          {!loading && predictedPrice != null && stage !== "done" && (
            <div className="rag-context">
              <div className="rag-label">Ye price sahi tha?</div>

              {stage === "ask" && (
                <div className="rag-list">
                  <button
                    className="ask"
                    onClick={handleSahi}
                    disabled={fbLoading}
                  >
                    {fbLoading ? "Bhej raha hoon..." : "Sahi"}
                  </button>
                  <button className="ask" onClick={handleGalat} disabled={fbLoading}>
                    Galat
                  </button>
                </div>
              )}

              {stage === "wrong" && (
                <form onSubmit={handleWrongSubmit} className="rag-list">
                  <label>
                    Asal rate kitna tha? (PKR/kg)
                    <input
                      type="number"
                      inputMode="decimal"
                      min="0"
                      step="0.01"
                      value={reportedPrice}
                      onChange={(e) => setReportedPrice(e.target.value)}
                      style={{ marginLeft: 8, width: 120 }}
                    />
                  </label>
                  <textarea
                    placeholder="Optional note (max 300 chars)"
                    maxLength={300}
                    value={note}
                    onChange={(e) => setNote(e.target.value.slice(0, 300))}
                    rows={2}
                    style={{ width: "100%", marginTop: 8 }}
                  />
                  <div className="rag-list">
                    <button className="ask" type="submit" disabled={fbLoading}>
                      {fbLoading ? "Bhej raha hoon..." : "Report bhejein"}
                    </button>
                    <span className="stamp">{note.length}/300</span>
                  </div>
                </form>
              )}

              {fbError && <div className="error-text">{fbError}</div>}
            </div>
          )}

          {stage === "done" && (
            <div className="rag-context">
              <div className="rag-label">Shukriya! Aapki report save ho gayi.</div>
              {fbResult && fbResult.regenerated && fbResult.advice && (
                <p>{fbResult.advice}</p>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}
