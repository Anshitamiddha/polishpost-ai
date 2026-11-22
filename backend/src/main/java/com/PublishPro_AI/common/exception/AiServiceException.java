package com.PublishPro_AI.common.exception;

import org.springframework.http.HttpStatus;

/**
 * The AI service could not make the picture. The message is safe to show the
 * user, and the status is the one the client should get.
 */
public class AiServiceException extends RuntimeException {

    private final HttpStatus status;

    public AiServiceException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus getStatus() {
        return status;
    }
}
