// Text limits for the create-post form. The topic limit matches the AI
// service's `video_topic` limit, so a topic that fits here is accepted there.
export const TOPIC_MAX_LENGTH = 500;
export const DESCRIPTION_MAX_LENGTH = 1000;
export const PROMPT_MAX_LENGTH = 500;

// Starting point for the global prompt. The user can edit or clear it.
export const DEFAULT_PROMPT =
  "Create a bold, cinematic YouTube thumbnail. Keep the creator as the main focus, " +
  "use dramatic lighting, strong contrast, and leave space for a short headline.";
