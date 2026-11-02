import { SparklesIcon } from "./icons";

function PageHeading() {
  return (
    <header className="cg-heading">
      <div>
        <h1>Create your next post</h1>
        <p>Turn your video idea into publish-ready content.</p>
      </div>

      <span className="cg-chip cg-chip--accent">
        <SparklesIcon size={14} />
        AI Workspace
      </span>
    </header>
  );
}

export default PageHeading;
