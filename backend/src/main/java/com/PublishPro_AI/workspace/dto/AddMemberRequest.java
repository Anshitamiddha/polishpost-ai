package com.PublishPro_AI.workspace.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public class AddMemberRequest {


    @NotBlank(message = "Email is required")
    @Email(message = "Invalid email format")
    private String email;


    public AddMemberRequest() {
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

}


