import { useState } from "react";
import WeatherInputs from "./components/WeatherInputs";
import PricePrediction from "./components/PricePrediction";
import AIAdvice from "./components/AIAdvice";

const DEFAULT_INPUTS = {
  temperature: 33,
  rainfall: 0.5,
  humidity: 65,
  last_price: 246,
};

export default function App() {
  const [inputs, setInputs] = useState(DEFAULT_INPUTS);

  return (
    <div className="board">
      <p className="eyebrow">Faisalabad mandi &middot; hybrid advisory</p>
      <h1>Tomato rate board</h1>
      <p className="subtitle">
        Chhota regression model (Rs/kg) + AI advisory layer — weather aur
        recent price se agla estimate aur farmer ke liye seedha jawab.
      </p>

      <WeatherInputs
        inputs={inputs}
        setInputs={setInputs}
      />

      <PricePrediction inputs={inputs} />

      <AIAdvice inputs={inputs} />

      <p className="foot">
        ML: 5-feature Ridge model (temp, rainfall, humidity, lag-price,
        rolling avg) &middot; test R&sup2; 0.54 (Leave-One-Out CV) &middot;
        11 samples se train — chhoti dataset hai, interval ke tor pe lein,
        exact guarantee nahi.
        <br />
        Tool use: "Live weather fetch" button Open-Meteo forecast API se
        Faisalabad ka abhi ka mausam khud fetch karta hai.
        <br />
        RAG: advice maangne pe, system 13 real historical mandi weeks mein
        se 3 sabse "similar weather" wale din retrieve karta hai
        (nearest-neighbour), aur unhe AI ko context ke tor pe deta hai —
        grounding ke liye, hallucination kam karne.
        <br />
        AI advisory layer: ML ke number + retrieved history ko context ke
        sath farmer-friendly recommendation mein convert karta hai — khud
        price generate nahi karta.
      </p>
    </div>
  );
}
