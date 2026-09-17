package au.nemlab.batterylab;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import java.util.*;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;
import static au.nemlab.batterylab.BatteryEngineTest.*;

class HindsightTest {
    static OrderedHindsight.Outcome solve(Battery b, ScheduleWindows w, TradingCosts c, PriceDay p) {
        return new OrderedHindsight().solve(b,w,c,p,OrderedHindsight.Limits.standard());
    }
    static void proven(OrderedHindsight.Outcome outcome,double expected) {
        assertEquals(OrderedHindsight.Status.OPTIMAL,outcome.status(),outcome.toString());
        assertEquals(expected,outcome.accounting().margin(),1e-6);
        assertTrue(outcome.upperBound() >= expected-1e-7);
        assertTrue(outcome.absoluteGap()>=0 && outcome.absoluteGap()<=.01);
    }
    @ParameterizedTest @CsvSource({"-30,200,230","100,10,0","0,0,0","-30,-10,20"})
    void manualPriceOptima(double buy,double sell,double expected) {
        var r=solve(ideal(),WINDOWS,FREE,prices(buy,sell)); proven(r,expected);
        assertTrue(r.accounting().margin()+1e-6>=run(ideal(),buy,sell).accounting().margin());
    }
    @Test void feesLossesAndConnectionLimit() {
        proven(solve(battery(1,0,12,12,new Efficiency(1,.9)),WINDOWS,new TradingCosts(2,2,10),prices(-30,200)),197.2);
        proven(solve(new Battery(1,0,1,0,12,12,12,6,new Efficiency(1,1)),WINDOWS,FREE,prices(0,100)),50);
    }
    @Test void initialInventoryAndZeroPowerCannotCreateProfit() {
        proven(solve(battery(1,1,12,12,new Efficiency(1,1)),WINDOWS,FREE,prices(0,100)),0);
        proven(solve(battery(1,0,0,12,new Efficiency(1,1)),WINDOWS,FREE,prices(-30,200)),0);
        proven(solve(battery(1,0,12,0,new Efficiency(1,1)),WINDOWS,FREE,prices(-30,200)),0);
    }
    @Test void negativePricesCannotRewardSimultaneousEnergyDissipation() {
        var r=solve(battery(1,0,12,12,Efficiency.roundTrip(.81)),WINDOWS,FREE,prices(-100,-100));
        proven(r,19); // Only legitimate inter-interval cycling; no same-interval import/export.
        for(var interval:r.dispatch().intervals()) assertTrue(interval.importedMWh()==0 || interval.exportedMWh()==0);
        assertEquals(0,r.dispatch().intervals().getLast().endingEnergyMWh(),1e-7);
    }
    @Test void tinyExactEnumerationAcrossEveryFeasibleBinaryDispatch() {
        var random=new Random(10210);
        var windows=new ScheduleWindows(0,2,2,4);
        for(int trial=0;trial<40;trial++) {
            var original=prices(0,0);var entries=new ArrayList<>(original.intervals());
            int[] price=new int[4];
            for(int i=0;i<4;i++) {
                price[i]=random.nextInt(81)-40;
                var old=entries.get(i);
                entries.set(i,PriceDay.Interval.fromEnd(old.region(),old.end(),BigDecimal.valueOf(price[i])));
            }
            var day=new PriceDay(original.region(),original.date(),entries);
            double best=0;
            for(int mask=0;mask<16;mask++) {
                int c0=mask&1,c1=(mask>>1)&1,d0=(mask>>2)&1,d1=(mask>>3)&1;
                if(c0+c1>1 || c0+c1!=d0+d1)continue;
                best=Math.max(best,-price[0]*c0-price[1]*c1+price[2]*d0+price[3]*d1);
            }
            // Unit capacities and energy balance form an integral flow polytope: this enumeration is an exact oracle.
            var result=solve(ideal(),windows,FREE,day);proven(result,best);
            var baseline=new BatterySimulation().run(ideal(),windows,FREE,day);
            assertTrue(result.accounting().margin()+1e-6>=baseline.accounting().margin());
        }
    }
    @Test void omittedProofIsNeverReportedAsOptimal() {
        for(var limit:List.of(new OrderedHindsight.Limits(0,100),new OrderedHindsight.Limits(100,0))) {
            var r=new OrderedHindsight().solve(ideal(),WINDOWS,FREE,prices(-30,200),limit);
            assertEquals(OrderedHindsight.Status.NO_SOLUTION,r.status());
            assertNull(r.dispatch()); assertNull(r.upperBound()); assertNull(r.absoluteGap());
        }
    }
    @Test void feasibleTimeoutMissingProofOrLargeGapCannotBecomeOptimal() {
        assertTrue(OrderedHindsight.canClaimOptimal(true,.001,false));
        assertFalse(OrderedHindsight.canClaimOptimal(false,.001,false));
        assertFalse(OrderedHindsight.canClaimOptimal(true,.001,true));
        assertFalse(OrderedHindsight.canClaimOptimal(true,null,false));
        assertFalse(OrderedHindsight.canClaimOptimal(true,.02,false));
        assertFalse(OrderedHindsight.canClaimOptimal(true,Double.NaN,false));
        assertFalse(OrderedHindsight.canClaimOptimal(true,-.001,false));
    }
    @Test void fractionalReferenceCasesWithEfficiencyAndFees() {
        var random=new Random(105);
        for(int i=0;i<20;i++) {
            double eta=.5+random.nextDouble()*.5;
            double purchase=random.nextDouble()*100-50, sale=random.nextDouble()*200-50;
            var b=battery(2,.25,12,12,new Efficiency(eta,eta));
            var result=solve(b,WINDOWS,new TradingCosts(2,3,4),prices(purchase,sale));
            // Import is limited to 1 MWh; a cycle exports eta squared, or the optimum idles.
            double optimum=Math.max(0,(sale-7)*eta*eta-purchase-2);
            proven(result,optimum);
        }
    }
    @Test void largeNumericalAllowancePreservesFeasiblePointWithoutClaimingOptimality() {
        var result=solve(battery(1_000_000,0,12_000_000,12_000_000,new Efficiency(1,1)),WINDOWS,FREE,prices(-30,200));
        assertEquals(OrderedHindsight.Status.FEASIBLE_NOT_PROVEN,result.status(),result.toString());
        assertNotNull(result.dispatch());
        assertEquals(230_000_000,result.accounting().margin(),1e-5);
        assertTrue(result.absoluteGap()>.01);
    }
    @Test void numericalFailureHasNoPublishableDispatch() {
        var r=solve(battery(1,0,12,12,new Efficiency(1,Double.MIN_VALUE)),WINDOWS,FREE,prices(0,100));
        assertEquals(OrderedHindsight.Status.FAILED_VALIDATION,r.status());
        assertNull(r.dispatch());
    }
    @Test void dualExpressionIsAnUpperBoundEvenWithNonoptimalMultipliers() {
        double[] buy=new double[288],sell=new double[288]; buy[0]=-30;sell[1]=200;
        // mu=0, lambda=0 gives the loose but valid upper bound 230.
        assertTrue(OrderedHindsight.dualUpperBound(WINDOWS,buy,sell,1,1,1,0,0)>=230);
        // Very poor multipliers still bound the optimum.
        assertTrue(OrderedHindsight.dualUpperBound(WINDOWS,buy,sell,1,1,1,50,30)>=230);
    }
}
