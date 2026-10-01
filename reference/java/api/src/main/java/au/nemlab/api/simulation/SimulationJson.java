package au.nemlab.api.simulation;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.batterylab.SimulationRequest;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Set;

/** Strict decimal-string boundary; core owns physical validation. */
final class SimulationJson {
    private static final JsonMapper JSON = JsonMapper.builder()
            .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();

    static SimulationRequest parse(byte[] body) {
        JsonNode root = JSON.readTree(body);
        object(root, "request", "region", "day", "site", "efficiency", "costs", "windows", "thresholds");
        var site = root.get("site");
        object(site, "site", "capacityMWh", "minimumMWh", "maximumMWh", "initialMWh", "chargeMW", "dischargeMW", "importLimitMW", "exportLimitMW");
        var efficiency = root.get("efficiency");
        object(efficiency, "efficiency", "charge", "discharge", "roundTrip");
        var costs = root.get("costs");
        object(costs, "costs", "importFee", "exportFee", "degradationPerExportedMWh");
        var windows = root.get("windows");
        object(windows, "windows", "chargeStart", "chargeEnd", "dischargeStart", "dischargeEnd");
        var thresholds = root.get("thresholds");
        SimulationRequest.ThresholdInput thresholdInput = null;
        if (thresholds != null && !thresholds.isNull()) {
            object(thresholds, "thresholds", "chargeBelow", "dischargeAbove");
            thresholdInput = new SimulationRequest.ThresholdInput(
                    decimal(thresholds, "thresholds", "chargeBelow"),
                    decimal(thresholds, "thresholds", "dischargeAbove"));
        }
        PriceDay.Region region;
        LocalDate day;
        try { region = PriceDay.Region.valueOf(string(root.get("region"), "region")); }
        catch (IllegalArgumentException invalid) { throw invalid("region", "INVALID_VALUE"); }
        String date = string(root.get("day"), "day");
        try {
            if (!date.matches("[0-9]{4}-[0-9]{2}-[0-9]{2}")) throw new IllegalArgumentException();
            day = LocalDate.parse(date);
        } catch (RuntimeException invalid) { throw invalid("day", "INVALID_VALUE"); }
        return new SimulationRequest(region, day,
                new SimulationRequest.Site(decimal(site, "site", "capacityMWh"), decimal(site, "site", "minimumMWh"),
                        decimal(site, "site", "maximumMWh"), decimal(site, "site", "initialMWh"),
                        decimal(site, "site", "chargeMW"), decimal(site, "site", "dischargeMW"),
                        decimal(site, "site", "importLimitMW"), decimal(site, "site", "exportLimitMW")),
                new SimulationRequest.EfficiencyInput(optional(efficiency, "charge"), optional(efficiency, "discharge"), optional(efficiency, "roundTrip")),
                new SimulationRequest.Costs(decimal(costs, "costs", "importFee"), decimal(costs, "costs", "exportFee"), decimal(costs, "costs", "degradationPerExportedMWh")),
                new SimulationRequest.Windows(minute(windows, "chargeStart"), minute(windows, "chargeEnd"), minute(windows, "dischargeStart"), minute(windows, "dischargeEnd")),
                thresholdInput);
    }

    private static void object(JsonNode value, String path, String... allowed) {
        if (value == null || !value.isObject()) throw invalid(path, "REQUIRED_OBJECT");
        Set<String> fields = Set.of(allowed);
        for (String field : value.propertyNames())
            if (!fields.contains(field)) throw invalid(path, "UNKNOWN_FIELD");
    }

    private static String string(JsonNode value, String field) {
        if (value == null) throw invalid(field, "REQUIRED");
        if (!value.isString()) throw invalid(field, "STRING_REQUIRED");
        return value.asString();
    }

    private static BigDecimal optional(JsonNode object, String field) {
        return object.has(field) ? decimal(object, "efficiency", field) : null;
    }

    private static BigDecimal decimal(JsonNode object, String path, String field) {
        String value = string(object.get(field), path + "." + field);
        if (value.length() > 80 || !value.matches("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?"))
            throw invalid(path + "." + field, "INVALID_DECIMAL");
        try { return new BigDecimal(value); }
        catch (NumberFormatException invalid) { throw invalid(path + "." + field, "INVALID_DECIMAL"); }
    }

    private static Integer minute(JsonNode object, String field) {
        JsonNode value = object.get(field);
        if (value == null || !value.isIntegralNumber() || !value.canConvertToInt())
            throw invalid("windows." + field, "INTEGER_REQUIRED");
        return value.asInt();
    }

    private static SimulationRequest.Invalid invalid(String field, String code) {
        return new SimulationRequest.Invalid(field, code);
    }
}
