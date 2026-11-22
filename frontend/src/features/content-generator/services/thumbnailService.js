import { apiRequest } from "../../../lib/apiClient";
import { buildThumbnailRequest, thumbnailEndpoint } from "../lib/thumbnailRequest";

// Asks the backend for ONE real thumbnail. The backend checks the workspace,
// then the Python AI service makes the picture with Magic Hour and stores it.
//
// Resolves to { status, image: { assetId, objectKey, ... }, providerGenerationId,
// creditsCharged }. `objectKey` says where the picture is stored. It is not a
// link, so nothing here can be shown as an image yet.
export function generateThumbnail(workspaceId, brief) {
  if (!workspaceId) {
    return Promise.reject(new Error("Choose a workspace before generating a thumbnail."));
  }

  return apiRequest(thumbnailEndpoint(workspaceId), {
    method: "POST",
    body: buildThumbnailRequest(brief),
    auth: true,
  });
}
