import { useMemo } from "react";

import GenerateContentPanel from "./components/GenerateContentPanel";
import GeneratedText from "./components/GeneratedText";
import PageHeading from "./components/PageHeading";
import PromptPanel from "./components/PromptPanel";
import ReferenceImagesPanel from "./components/ReferenceImagesPanel";
import ThumbnailVariations from "./components/ThumbnailVariations";
import VideoDetailsForm from "./components/VideoDetailsForm";
import { useAsyncAction } from "./hooks/useAsyncAction";
import { useCopyToClipboard } from "./hooks/useCopyToClipboard";
import { useLimitedText } from "./hooks/useLimitedText";
import { useReferenceImages } from "./hooks/useReferenceImages";
import { useThumbnailVariations } from "./hooks/useThumbnailVariations";
import {
  DEFAULT_PROMPT,
  DESCRIPTION_MAX_LENGTH,
  PROMPT_MAX_LENGTH,
  TOPIC_MAX_LENGTH,
} from "./lib/formLimits";
import { generateCaptions, generateHashtags } from "./services/mockGenerationService";
import "./content-generator.css";

// This component owns the state (the hooks) and passes it down. The panels
// below only draw what they are given and report what the user did.
function ContentGeneratorPage() {
  const topic = useLimitedText(TOPIC_MAX_LENGTH);
  const description = useLimitedText(DESCRIPTION_MAX_LENGTH);
  const prompt = useLimitedText(PROMPT_MAX_LENGTH, DEFAULT_PROMPT);
  const referenceImages = useReferenceImages();

  const captions = useAsyncAction(generateCaptions);
  const hashtags = useAsyncAction(generateHashtags);
  const thumbnails = useThumbnailVariations();
  const { copiedKey, copy } = useCopyToClipboard();

  // What generation is based on. Memoised so its identity only changes when
  // one of these values does.
  const brief = useMemo(
    () => ({
      topic: topic.value.trim(),
      description: description.value.trim(),
      prompt: prompt.value.trim(),
      referenceCount: referenceImages.images.length,
    }),
    [topic.value, description.value, prompt.value, referenceImages.images.length],
  );
  const canGenerate = !topic.isBlank;

  return (
    <div className="content-generator">
      <PageHeading />

      <div className="cg-grid">
        <div className="cg-column">
          <ReferenceImagesPanel
            images={referenceImages.images}
            problems={referenceImages.problems}
            isFull={referenceImages.isFull}
            onAddFiles={referenceImages.addFiles}
            onRemove={referenceImages.removeImage}
          />
          <PromptPanel prompt={prompt} />
          <VideoDetailsForm topic={topic} description={description} />
        </div>

        <div className="cg-column">
          <GenerateContentPanel
            canGenerate={canGenerate}
            captionsLoading={captions.isLoading}
            hashtagsLoading={hashtags.isLoading}
            thumbnailsLoading={thumbnails.isGenerating}
            onCaptions={() => captions.run(brief)}
            onHashtags={() => hashtags.run(brief)}
            onThumbnails={() => thumbnails.generate(brief)}
          />
          <GeneratedText
            captions={captions}
            hashtags={hashtags}
            copiedKey={copiedKey}
            onCopy={copy}
          />
          <ThumbnailVariations thumbnails={thumbnails} />
        </div>
      </div>
    </div>
  );
}

export default ContentGeneratorPage;
