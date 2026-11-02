// Rules for the reference images a user can attach. They live outside React so
// they are easy to test and can be reused by the real upload code later.

export const MAX_REFERENCE_IMAGES = 5;
export const MAX_IMAGE_MB = 5;
export const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

const MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024;

// Splits the chosen files into the ones we can keep and a plain-language
// message for each problem, so the user always learns why a file was skipped.
export function sortIncomingFiles(files, slotsLeft) {
  const accepted = [];
  const problems = [];
  let skippedForSpace = 0;

  for (const file of files) {
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      problems.push(`${file.name} is not a PNG, JPG or WEBP image.`);
    } else if (file.size > MAX_IMAGE_BYTES) {
      problems.push(`${file.name} is larger than ${MAX_IMAGE_MB} MB.`);
    } else if (accepted.length >= slotsLeft) {
      // One summary line is clearer than one message per extra file.
      skippedForSpace += 1;
    } else {
      accepted.push(file);
    }
  }

  if (skippedForSpace > 0) {
    const subject = skippedForSpace === 1 ? "1 image was" : `${skippedForSpace} images were`;
    problems.push(`You can add up to ${MAX_REFERENCE_IMAGES} images, so ${subject} not added.`);
  }

  return { accepted, problems };
}
