package com.PublishPro_AI.user.controller;

import com.PublishPro_AI.user.dto.UserResponse;
import com.PublishPro_AI.user.service.UserService;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    /*
     * This endpoint is protected by Spring Security.
     *
     * GET /api/users/me
     *
     * The user does NOT send their user ID.
     *
     * Spring Security already knows who they are because
     * JwtAuthenticationFilter authenticated the JWT.
     */
    @GetMapping("/profile")
    public ResponseEntity<UserResponse> getProfile(
            Authentication authentication
    ) {

        /*
         * Authentication contains the currently authenticated user.
         *
         * In our JwtAuthenticationFilter we used the user's email
         * as the username.
         *
         * So:
         *
         * authentication.getName()
         *
         * gives us the user's email.
         */
        String email = authentication.getName();

        return ResponseEntity.ok(
                userService.getUserByEmail(email)
        );
    }
}