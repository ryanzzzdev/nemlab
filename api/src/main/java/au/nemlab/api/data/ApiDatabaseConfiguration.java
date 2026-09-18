package au.nemlab.api.data;

import au.nemlab.infrastructure.jobs.RefreshJobConfiguration;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.boot.autoconfigure.condition.ConditionalOnExpression;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;

/** One database configuration shared by independently enabled reads and operator controls. */
@Configuration(proxyBeanMethods = false)
@ConditionalOnExpression("${nemlab.admin.enabled:false} or ${nemlab.data.enabled:false}")
@Import(RefreshJobConfiguration.class)
public class ApiDatabaseConfiguration {
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
            jdbc.queryForObject("SELECT count(*) FROM refresh_job WHERE false", Integer.class);
            jdbc.queryForObject("SELECT count(*) FROM price_current WHERE false", Integer.class);
        } catch (RuntimeException failure) {
            throw new IllegalStateException("API database unavailable or migrations missing (details omitted)");
        }
        return source;
    }

    private static String required(Environment environment, String name) {
        String value = environment.getProperty(name);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " is required when database-backed API features are enabled");
        }
        return value;
    }
}
