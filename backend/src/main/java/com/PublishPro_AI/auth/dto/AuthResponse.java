package com.PublishPro_AI.auth.dto;

import com.PublishPro_AI.user.dto.UserResponse;

public class AuthResponse {

    private String accessToken;
    private String tokenType;
    private UserResponse user;

    public AuthResponse() {
    }

    public AuthResponse(String accessToken, String tokenType, UserResponse user) {
        this.accessToken = accessToken;
        this.tokenType = tokenType;
        this.user = user;
    }

    public String getAccessToken() {
        return accessToken;
    }

    public void setAccessToken(String accessToken) {
        this.accessToken = accessToken;
    }

    public String getTokenType() {
        return tokenType;
    }

    public void setTokenType(String tokenType) {
        this.tokenType = tokenType;
    }

    public UserResponse getUser() {
        return user;
    }

    public void setUser(UserResponse user) {
        this.user = user;
    }
}