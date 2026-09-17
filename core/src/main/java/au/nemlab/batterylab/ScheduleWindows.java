package au.nemlab.batterylab;

/** Half-open interval indices: 0 is 00:00, 288 is next midnight in fixed UTC+10. */
public record ScheduleWindows(int chargeStart, int chargeEnd, int dischargeStart, int dischargeEnd) {
    public ScheduleWindows {
        if (chargeStart < 0 || chargeStart >= chargeEnd || chargeEnd > dischargeStart
                || dischargeStart >= dischargeEnd || dischargeEnd > 288)
            throw new IllegalArgumentException("require ordered, nonempty, nonoverlapping windows within one day");
    }
    public static ScheduleWindows minutes(int chargeStart, int chargeEnd, int dischargeStart, int dischargeEnd) {
        for (int minute : new int[]{chargeStart, chargeEnd, dischargeStart, dischargeEnd}) {
            if (minute < 0 || minute > 1440 || minute % 5 != 0)
                throw new IllegalArgumentException("window boundaries must be five-minute aligned within the day");
        }
        return new ScheduleWindows(chargeStart / 5, chargeEnd / 5, dischargeStart / 5, dischargeEnd / 5);
    }
    public boolean canCharge(int i) { return i >= chargeStart && i < chargeEnd; }
    public boolean canDischarge(int i) { return i >= dischargeStart && i < dischargeEnd; }
}
