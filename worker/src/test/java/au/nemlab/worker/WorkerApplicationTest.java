package au.nemlab.worker;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE, properties = "spring.main.keep-alive=false")
class WorkerApplicationTest {
    @Autowired
    ApplicationContext context;

    @Test
    void workerStartsWithoutDatabaseCredentialsOrWebRuntime() {
        assertEquals("nemlab-worker", context.getEnvironment().getProperty("spring.application.name"));
        assertEquals("none", context.getEnvironment().getProperty("spring.main.web-application-type"));
        assertThrows(ClassNotFoundException.class,
                () -> Class.forName("org.springframework.web.servlet.DispatcherServlet"));
        assertThrows(ClassNotFoundException.class, () -> Class.forName("au.nemlab.api.ApiApplication"));
    }
}
