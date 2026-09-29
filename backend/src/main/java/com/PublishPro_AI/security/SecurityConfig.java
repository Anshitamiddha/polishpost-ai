package com.PublishPro_AI.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
public class SecurityConfig {

    /*
     * This is the main Spring Security configuration.
     *
     * SecurityFilterChain tells Spring:
     * "For every incoming HTTP request, what security rules should be applied?"
     */
    @Bean
    public SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            JwtAuthenticationFilter jwtAuthenticationFilter
    ) throws Exception {

        http

                /*
                 * CSRF protection is mainly useful for browser-based
                 * session/cookie authentication.
                 *
                 * Our API will use JWTs in the Authorization header,
                 * so we disable CSRF for this stateless API.
                 */
                .csrf(csrf -> csrf.disable())

                /*
                 * We are NOT storing login sessions on the server.
                 *
                 * Every request will carry its JWT.
                 *
                 * STATELESS means:
                 * Spring Security should not create or maintain
                 * an HTTP session for authentication.
                 */
                .sessionManagement(session ->
                        session.sessionCreationPolicy(
                                SessionCreationPolicy.STATELESS
                        )
                )

                /*
                 * Define which endpoints are public
                 * and which require authentication.
                 */
                .authorizeHttpRequests(auth -> auth

                        /*
                         * Register and Login must be accessible
                         * without an existing JWT.
                         */
                        .requestMatchers("/api/auth/**").permitAll()

                        /*
                         * Everything else requires authentication.
                         *
                         * Example:
                         * GET /api/users/me
                         *
                         * Without JWT → 401
                         * With valid JWT → request continues
                         */
                        .anyRequest().authenticated()
                )

                /*
                 * Our JWT filter must run BEFORE Spring's
                 * normal username/password authentication filter.
                 *
                 * Why?
                 *
                 * We want to inspect the JWT first and create an
                 * authenticated SecurityContext before the controller runs.
                 */
                .addFilterBefore(
                        jwtAuthenticationFilter,
                        UsernamePasswordAuthenticationFilter.class
                );

        return http.build();
    }
}