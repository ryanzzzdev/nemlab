import type { components, operations } from "../generated/schema";

// Consumers retain decimal precision until they explicitly choose chart/display conversion.
export function priceLabel(interval: components["schemas"]["Interval"]): string {
  if (interval.state === "VALUE") {
    const exactPrice: string = interval.price;
    return exactPrice;
  }
  const gap: null = interval.price;
  return gap === null ? "No data" : "";
}

export type CoverageResult =
  operations["getPriceCoverage"]["responses"][200]["content"]["application/json"];
export type OperatorSubmission =
  operations["submitPriceRefresh"]["requestBody"]["content"]["application/json"];

// Numeric prices would lose the API's precision guarantee.
// @ts-expect-error Price strings must not silently become JavaScript numbers.
const invalidPrice: components["schemas"]["Interval"]["price"] = 123.45;
