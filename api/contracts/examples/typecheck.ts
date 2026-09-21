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

export type SimulationSubmission =
  operations["submitSimulation"]["requestBody"]["content"]["application/json"];
export type SimulationResult =
  operations["getSimulationResult"]["responses"][200]["content"]["application/json"];

// @ts-expect-error Scenario decimal inputs must also remain exact strings.
const invalidCapacity: SimulationSubmission["site"]["capacityMWh"] = 1;
export function simulationMargin(result: SimulationResult): number {
  const exactCapacity: string = result.inputs.site.capacityMWh;
  const status: "OPTIMAL" = result.solver.status;
  return status === "OPTIMAL" && exactCapacity ? result.hindsight.accounting.margin : 0;
}
