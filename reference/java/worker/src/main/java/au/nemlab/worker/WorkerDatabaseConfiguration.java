package au.nemlab.worker;

import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.boot.autoconfigure.condition.ConditionalOnExpression;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;
import javax.sql.DataSource;

/** One shared database connection configuration for independently enabled workers. */
@Configuration(proxyBeanMethods = false)
@ConditionalOnExpression("${nemlab.worker.enabled:false} or ${nemlab.simulation.enabled:false}")
public class WorkerDatabaseConfiguration {
    @Bean
    public DataSource dataSource(Environment environment) {
        PGSimpleDataSource source = new PGSimpleDataSource();
        source.setURL(required(environment, "NEMLAB_DB_URL"));
        source.setUser(required(environment, "NEMLAB_DB_USER"));
        source.setPassword(required(environment, "NEMLAB_DB_PASSWORD"));
        source.setConnectTimeout(5);
        source.setSocketTimeout(10);
        try {
            var jdbc = new JdbcTemplate(source);
            if (environment.getProperty("nemlab.worker.enabled", Boolean.class, false))
                jdbc.queryForObject("SELECT count(*) FROM refresh_job WHERE false", Integer.class);
            if (environment.getProperty("nemlab.simulation.enabled", Boolean.class, false))
                jdbc.queryForObject("SELECT count(*) FROM simulation_job WHERE false", Integer.class);
        } catch (RuntimeException failure) {
            throw new IllegalStateException("Worker database unavailable or migrations missing (details omitted)");
        }
        return source;
    }

    private static String required(Environment environment, String name) {
        String value = environment.getProperty(name);
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " is required when a worker is enabled");
        return value;
    }
}
