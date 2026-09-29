package com.PublishPro_AI.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Non-secret connection details for Supabase services.
 * Secrets and database credentials are read from environment variables.
 */
@ConfigurationProperties(prefix = "supabase")
public record SupabaseProperties(String url, String publishableKey) {
}
