// What the Create Post page sends to the backend for one thumbnail.
// Kept apart from the network code so it can be tested without a browser.

// Where the request goes. The workspace is part of the path, and the backend
// checks that the logged-in user belongs to it.
export function thumbnailEndpoint(workspaceId) {
  return `/api/workspaces/${workspaceId}/thumbnails`;
}

// `brief` is built in ContentGeneratorPage. The field names are the same in
// React, Spring Boot and the AI service: the video topic (also the text written
// on the thumbnail), the description, and the global creative prompt exactly as
// the user wrote it. The workspace is in the URL, not here. The backend leaves
// out a blank description or prompt.
export function buildThumbnailRequest(brief) {
  return {
    video_topic: brief.topic,
    description: brief.description,
    global_prompt: brief.prompt,
  };
}
