package com.PublishPro_AI.thumbnail.dto;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Set;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.Test;

// The limits are the AI service's, so a request that passes here is accepted there.
class GenerateThumbnailRequestTest {

    private final Validator validator =
            Validation.buildDefaultValidatorFactory().getValidator();

    private Set<ConstraintViolation<GenerateThumbnailRequest>> check(
            String title, String description, String prompt
    ) {
        return validator.validate(new GenerateThumbnailRequest(title, description, prompt));
    }

    @Test
    void aTitleAloneIsEnough() {
        assertTrue(check("AI APP IN 7 DAYS", null, null).isEmpty());
    }

    @Test
    void aFullRequestAtTheLimitsIsAccepted() {
        assertTrue(check("x".repeat(60), "y".repeat(300), "z".repeat(500)).isEmpty());
    }

    @Test
    void theTitleIsRequiredAndLimited() {
        assertEquals(1, check(null, null, null).size());
        assertEquals(1, check("   ", null, null).size()); // blank, though long enough
        assertEquals(1, check("ab", null, null).size());
        assertEquals(1, check("x".repeat(61), null, null).size());
    }

    @Test
    void theDescriptionAndPromptAreLimited() {
        assertEquals(1, check("A title", "y".repeat(301), null).size());
        assertEquals(1, check("A title", null, "z".repeat(501)).size());
    }
}
