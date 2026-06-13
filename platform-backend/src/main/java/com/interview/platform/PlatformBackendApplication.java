package com.interview.platform;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.retry.annotation.EnableRetry;

@SpringBootApplication
@EnableRetry
public class PlatformBackendApplication {

	public static void main(String[] args) {
		SpringApplication.run(PlatformBackendApplication.class, args);
	}

}
