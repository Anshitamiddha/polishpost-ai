// What the Create Post page sends to the backend for one thumbnail.
// Kept apart from the network code so it can be tested without a browser.

// Where the request goes. The workspace is part of the path, and the backend
// checks that the logged-in user belongs to it.
export function thumbnailEndpoint(workspaceId) {
  return `/api/workspaces/${workspaceId}/thumbnails`;
}

// `brief` is built in ContentGeneratorPage. The title becomes the text written
// on the thumbnail, the description says what the video is about, and the
// global creative prompt goes along exactly as the user wrote it. The backend
// leaves out a blank prompt.
export function buildThumbnailRequest(brief) {
  return {
    title: brief.topic,
    description: brief.description,
    prompt: brief.prompt,
  };
}
