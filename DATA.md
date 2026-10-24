# Data Provenance

## Real data

- 13 weekly Faisalabad tomato rows, 2025-12-11 to 2026-08-20, from
  `faisalabad_tomato_prices_weekly.csv`.
- SOURCE: not recorded in this repository (provided to the project as
  faisalabad_tomato_prices_weekly.csv)
- COLLECTED: not recorded (latest observation is 2026-08-20)
- WHOLESALE OR RETAIL: not recorded

## Cleaning

- Raw file had 2-3 rows per date.
- Rows with negative prices or max < min were dropped.
- Median of valid rows per date was used.
- Three rows have an average of exactly 100.00 and may be placeholder values.

## Weather

- Weather for the 13 real dates: Open-Meteo ERA5 daily means.

## Synthetic 2024 data

- 365 daily rows from `mandi_price_weather_dataset.csv`.
- No generator script is in this repo and its weather values are unrealistic.
- Prices were divided by 40 (maund to kg).
- Do not draw conclusions from it.

## Model

- Ridge, 11 rows (13 minus 2 lag warm-up rows), Leave-One-Out CV R² 0.535.
- This is not a forward-in-time test.
- "feature_importance" in the metrics JSON is raw coefficients, not importance.
