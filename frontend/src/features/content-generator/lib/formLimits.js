// Text limits for the create-post form. They match the AI service's limits, so
// text that fits here is accepted there: the title is `video_topic` (at most 60,
// because it is written on the thumbnail), the description is `description` (at
// most 300) and the prompt is `global_prompt` (at most 500).
export const TOPIC_MAX_LENGTH = 60;
export const DESCRIPTION_MAX_LENGTH = 300;
export const PROMPT_MAX_LENGTH = 500;

// Starting point for the global prompt. The user can edit or clear it.
export const DEFAULT_PROMPT =
  "Create a bold, cinematic YouTube thumbnail. Keep the creator as the main focus, " +
  "use dramatic lighting, strong contrast, and leave space for a short headline.";
