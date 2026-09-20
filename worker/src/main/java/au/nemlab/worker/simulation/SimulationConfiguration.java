package au.nemlab.worker.simulation;

import au.nemlab.infrastructure.batterylab.SimulationJobs;
import au.nemlab.worker.WorkerDatabaseConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.core.env.Environment;
import javax.sql.DataSource;
import java.time.Duration;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "nemlab.simulation.enabled", havingValue = "true")
@Import(WorkerDatabaseConfiguration.class)
public class SimulationConfiguration {
    @Bean
    public SimulationJobs simulationJobs(DataSource source) { return new SimulationJobs(source); }

    @Bean
    public SimulationProcess simulationProcess() { return new SimulationProcess(); }

    @Bean
    public SimulationWorker simulationWorker(SimulationJobs jobs, SimulationProcess process, Environment environment) {
        long milliseconds = environment.getProperty("nemlab.simulation.poll-ms", Long.class, 5000L);
        if (milliseconds < 1000 || milliseconds > 60_000)
            throw new IllegalArgumentException("Simulation poll interval must be between 1000 and 60000 ms");
        return new SimulationWorker(jobs, process, Duration.ofMillis(milliseconds));
    }
}
