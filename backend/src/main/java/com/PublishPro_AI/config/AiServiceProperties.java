package com.PublishPro_AI.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Where the Python AI service is and how this backend proves who it is.
 * The shared secret is read from the AI_SERVICE_SHARED_SECRET environment
 * variable and must match the value the AI service was started with.
 */
@ConfigurationProperties(prefix = "ai.service")
public record AiServiceProperties(
        String baseUrl,
        String sharedSecret,
        Duration timeout
) {
}
