package au.nemlab.api.simulation;

import au.nemlab.infrastructure.batterylab.SimulationJobs;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import javax.sql.DataSource;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "nemlab.simulation-api.enabled", havingValue = "true")
public class SimulationConfiguration {
    @Bean
    public SimulationJobs simulationJobs(DataSource source) { return new SimulationJobs(source); }
}
