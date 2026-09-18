package au.nemlab.worker;

import au.nemlab.worker.refresh.FetchCommand;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class WorkerApplication {
    public static void main(String[] args) {
        if (args.length > 0 && FetchCommand.MODE.equals(args[0])) {
            System.exit(FetchCommand.run(args));
            return;
        }
        SpringApplication.run(WorkerApplication.class, args);
    }
}
