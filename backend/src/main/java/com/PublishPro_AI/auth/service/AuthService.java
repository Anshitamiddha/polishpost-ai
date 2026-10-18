package com.PublishPro_AI.auth.service;

import com.PublishPro_AI.auth.dto.AuthResponse;
import com.PublishPro_AI.auth.dto.LoginRequest;
import com.PublishPro_AI.auth.dto.RegisterRequest;
import com.PublishPro_AI.auth.token.JwtService;
import com.PublishPro_AI.common.exception.ConflictException;
import com.PublishPro_AI.common.exception.UnauthorizedException;
import com.PublishPro_AI.user.dto.UserResponse;
import com.PublishPro_AI.user.entity.User;
import com.PublishPro_AI.user.repository.UserRepository;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Locale;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    public AuthService(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            JwtService jwtService
    ) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
    }

    public UserResponse register(RegisterRequest request) {

        String email = request.getEmail()
                .trim()
                .toLowerCase(Locale.ROOT);

        if (userRepository.existsByEmail(email)) {
            throw new ConflictException("Email is already registered");
        }

        User user = new User();

        user.setName(request.getName().trim());
        user.setEmail(email);
        user.setPasswordHash(
                passwordEncoder.encode(request.getPassword())
        );
        user.setEnabled(true);

        User savedUser = userRepository.save(user);

        return new UserResponse(
                savedUser.getId(),
                savedUser.getName(),
                savedUser.getEmail()
        );
    }

    public AuthResponse login(LoginRequest request) {

        String email = request.getEmail()
                .trim()
                .toLowerCase(Locale.ROOT);

        User user = userRepository.findByEmail(email)
                .orElseThrow(() ->
                        new UnauthorizedException(
                                "Invalid email or password"
                        )
                );

        if (!Boolean.TRUE.equals(user.getEnabled())) {
            throw new UnauthorizedException(
                    "Invalid email or password"
            );
        }

        boolean passwordMatches = passwordEncoder.matches(
                request.getPassword(),
                user.getPasswordHash()
        );

        if (!passwordMatches) {
            throw new UnauthorizedException(
                    "Invalid email or password"
            );
        }

        String accessToken =
                jwtService.generateAccessToken(user.getId());

        UserResponse userResponse = new UserResponse(
                user.getId(),
                user.getName(),
                user.getEmail()
        );

        return new AuthResponse(
                accessToken,
                "Bearer",
                userResponse
        );
    }
}