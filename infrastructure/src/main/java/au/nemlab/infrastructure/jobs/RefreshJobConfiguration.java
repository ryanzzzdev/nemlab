package au.nemlab.infrastructure.jobs;

import au.nemlab.infrastructure.prices.PriceStore;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;

import javax.sql.DataSource;

/** Import explicitly in an application that supplies its database connection. */
@Configuration(proxyBeanMethods = false)
@EnableTransactionManagement
public class RefreshJobConfiguration {

    @Bean
    public PlatformTransactionManager transactionManager(DataSource dataSource) {
        return new DataSourceTransactionManager(dataSource);
    }

    @Bean
    public PriceStore priceStore(DataSource dataSource) {
        return new PriceStore(dataSource);
    }

    @Bean
    public RefreshJobService refreshJobService(DataSource dataSource, PriceStore priceStore) {
        return new RefreshJobService(dataSource, priceStore);
    }
}
