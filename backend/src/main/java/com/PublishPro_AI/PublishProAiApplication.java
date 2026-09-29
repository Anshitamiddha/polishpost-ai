package com.PublishPro_AI;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class PublishProAiApplication {

	public static void main(String[] args) {
		SpringApplication.run(PublishProAiApplication.class, args);
	}

}
