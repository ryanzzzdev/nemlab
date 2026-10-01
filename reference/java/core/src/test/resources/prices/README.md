# Price fixtures

These CSV files project `interval_end` and exact price decimals from the checked-in
`docs/project/evidence/oe-validation/{recent,historical}-price-normalised.json` samples.
Region: NSW1; source: Open Electricity; interval-end labels; five-minute resolution;
fixed UTC+10 market days. The evidence directory records retrieval and validation.
No live request or credential is needed to run tests. Update only deliberately with
source provenance; tests must not track changing OE responses.
