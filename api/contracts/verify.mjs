import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import SwaggerParser from "@apidevtools/swagger-parser";
import Ajv from "ajv";
import addFormats from "ajv-formats";

const api = await SwaggerParser.validate("openapi.json");
const ajv = new Ajv({ allErrors: true, strict: true });
addFormats(ajv);
// OpenAPI int64 is descriptive: JavaScript cannot represent every 64-bit integer exactly.
ajv.addFormat("int64", { type: "number", validate: Number.isInteger });
const routes = Object.entries(api.paths).flatMap(([path, methods]) =>
  Object.entries(methods).map(([method, operation]) => ({
    method,
    operation,
    pattern: new RegExp(`^${path.replace(/\{[^}]+\}/g, "[^/]+")}$`),
  })),
);
const seen = new Set();
const statuses = new Set();
const validators = new Map();
function validate(schema, value, label) {
  if (!validators.has(schema)) {
    validators.set(schema, ajv.compile(schema));
  }
  const check = validators.get(schema);
  assert(check(value), `${label}: ${ajv.errorsText(check.errors)}`);
}

for (const route of routes) {
  const { operation } = route;
  const admin = route.pattern.source.includes("admin");
  assert.deepEqual(operation.security, admin ? [{ operatorBearer: [] }] : []);
  for (const response of Object.values(operation.responses)) {
    const schema = response.content?.["application/json"]?.schema;
    if (schema) {
      validators.set(schema, ajv.compile(schema));
    }
  }
}

const directory = new URL("../build/contract-responses/", import.meta.url);
const files = await readdir(directory);
assert(files.length > 0, "Run :api:test to capture actual HTTP responses first");
for (const file of files) {
  const capture = JSON.parse(await readFile(new URL(file, directory), "utf8"));
  const route = routes.find((candidate) =>
    candidate.method === capture.method && candidate.pattern.test(capture.path),
  );
  assert(route, `Undocumented operation: ${capture.method} ${capture.path}`);
  const label = `${route.operation.operationId} ${capture.status}`;
  const response = route.operation.responses[capture.status];
  assert(response, `Undocumented response: ${label}`);
  for (const [name, header] of Object.entries(response.headers ?? {})) {
    const values = capture.headers[name.toLowerCase()];
    assert(values?.length, `${label}: missing ${name}`);
    validate(header.schema, values.join(", "), `${label} ${name}`);
  }
  const schema = response.content?.["application/json"]?.schema;
  if (schema) {
    assert(capture.headers["content-type"]?.[0].startsWith("application/json"));
    const body = JSON.parse(capture.body);
    validate(schema, body, label);
    if (body.code) {
      statuses.add(body.code);
    }
  } else {
    assert.equal(capture.body, "", `${label}: expected an empty body`);
  }
  if (capture.status < 300) {
    seen.add(route.operation.operationId);
  }
}
for (const { operation } of routes) {
  assert(seen.has(operation.operationId), `No successful HTTP evidence: ${operation.operationId}`);
}
for (const code of ["INVALID_REQUEST", "UNAUTHORISED", "PRICE_DAY_NOT_IMPORTED",
  "JOB_NOT_FOUND", "IDEMPOTENCY_CONFLICT", "QUEUE_FULL", "STORAGE_UNAVAILABLE",
  "SIMULATION_NOT_FOUND", "RESULT_NOT_READY",
  "SIMULATION_FAILED", "REQUEST_TOO_LARGE", "UNSUPPORTED_CONTENT_TYPE",
  "PRICE_REFRESH_PENDING", "PRICE_REFRESH_FAILED", "VISITOR_REFRESH_LIMIT",
  "PUBLICATION_NOT_FOUND", "CATALOGUE_NOT_PUBLISHED", "EVENT_NOT_FOUND"]) {
  assert(statuses.has(code), `Missing HTTP error evidence: ${code}`);
}

// Mutation checks make sure the contract rejects common frontend integration mistakes.
const interval = ajv.compile(api.components.schemas.Interval);
const value = { start: "2023-10-01T00:00:00Z", end: "2023-10-01T00:05:00Z",
  state: "VALUE", price: "123.4567890123456789" };
assert(interval(value));
assert(!interval({ ...value, price: 123.45 }));
assert(!interval({ ...value, state: "MISSING" }));
assert(!interval({ ...value, claimToken: "internal" }));
assert(interval({ ...value, state: "SOURCE_NULL", price: null }));
assert(!interval({ ...value, start: "not-an-instant" }));
console.log(`Validated OpenAPI, ${files.length} HTTP responses, all ${routes.length} operations and error codes.`);

const scenario = JSON.parse(await readFile("examples/simulation-request.json", "utf8"));
const requestCheck = ajv.compile(api.components.schemas.SimulationRequest);
assert(requestCheck(scenario));
assert(!requestCheck({ ...scenario, site: { ...scenario.site, capacityMWh: 1 } }));
assert(!requestCheck({ ...scenario, efficiency: { charge: "1", discharge: "1", roundTrip: "1" } }));
assert(!requestCheck({ ...scenario, actor: "spoof" }));
assert(!requestCheck({ ...scenario, windows: { ...scenario.windows, chargeEnd: 6 } }));
