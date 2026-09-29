package com.PublishPro_AI.security;

import com.PublishPro_AI.auth.token.JwtService;
import com.PublishPro_AI.user.entity.User;
import com.PublishPro_AI.user.repository.UserRepository;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.AuthorityUtils;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private final UserRepository userRepository;

    public JwtAuthenticationFilter(
            JwtService jwtService,
            UserRepository userRepository
    ) {
        this.jwtService = jwtService;
        this.userRepository = userRepository;
    }

    /*
     * This method runs once for every HTTP request.
     *
     * Example:
     *
     * GET /api/users/me
     *
     * Authorization: Bearer eyJhbGci...
     *
     * The filter checks that token before the request
     * reaches our controller.
     */
    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {

        /*
         * Read the Authorization header.
         *
         * Expected format:
         *
         * Authorization: Bearer <JWT>
         */
        String authHeader = request.getHeader("Authorization");

        /*
         * If there is no Authorization header,
         * simply continue the request.
         *
         * Spring Security will eventually reject the request
         * if the endpoint requires authentication.
         */
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            filterChain.doFilter(request, response);
            return;
        }

        /*
         * Remove "Bearer " and keep only the JWT.
         */
        String token = authHeader.substring(7);

        try {

            /*
             * First verify that the JWT is cryptographically valid
             * and has not expired.
             */
            if (jwtService.isTokenValid(token)) {

                /*
                 * Our JWT subject contains the user ID.
                 *
                 * Example:
                 *
                 * subject = "15"
                 *
                 * Therefore we convert it back to Long.
                 */
                Long userId = jwtService.extractUserId(token);

                /*
                 * Now retrieve the actual user from PostgreSQL.
                 *
                 * This is important because the JWT only tells us
                 * who the user claims to be.
                 *
                 * The database tells us whether that user
                 * actually exists and is still enabled.
                 */
                User user = userRepository.findById(userId)
                        .orElse(null);

                if (user != null && Boolean.TRUE.equals(user.getEnabled())) {

                    /*
                     * Spring Security works with UserDetails.
                     *
                     * We create a minimal UserDetails object
                     * from our database user.
                     *
                     * We currently have no roles/authorities,
                     * so we use an empty authority list.
                     */
                    UserDetails userDetails =
                            org.springframework.security.core.userdetails.User
                                    .withUsername(user.getEmail())
                                    .password(user.getPasswordHash())
                                    .authorities(AuthorityUtils.NO_AUTHORITIES)
                                    .disabled(!user.getEnabled())
                                    .build();

                    /*
                     * This object represents an authenticated user
                     * inside Spring Security.
                     *
                     * Principal = userDetails
                     *
                     * Credentials = null because we already
                     * authenticated using the JWT.
                     */
                    UsernamePasswordAuthenticationToken authentication =
                            new UsernamePasswordAuthenticationToken(
                                    userDetails,
                                    null,
                                    userDetails.getAuthorities()
                            );

                    /*
                     * Store authentication in Spring's
                     * SecurityContext.
                     *
                     * From this point onward, controllers and
                     * services can ask Spring:
                     *
                     * "Who is the current authenticated user?"
                     */
                    SecurityContextHolder
                            .getContext()
                            .setAuthentication(authentication);
                }
            }

        } catch (Exception exception) {

            /*
             * Invalid/expired/malformed JWT.
             *
             * We do NOT expose internal JWT errors to the client.
             *
             * We simply leave the request unauthenticated.
             *
             * If the endpoint is protected, Spring Security
             * will reject it.
             */
        }

        /*
         * VERY IMPORTANT:
         *
         * Continue the filter chain.
         *
         * If we don't call this, the request will stop here
         * and never reach the controller.
         */
        filterChain.doFilter(request, response);
    }
}