import PageHeading from "./components/PageHeading";
import UploadPanel from "./components/UploadPanel";
import VideoDetailsForm from "./components/VideoDetailsForm";
import "./content-generator.css";

function ContentGeneratorPage() {
  return (
    <div className="content-generator">
      <PageHeading />

      <div className="generator-grid">
        <div className="generator-inputs">
          <UploadPanel />
          <VideoDetailsForm />
        </div>
      </div>
    </div>
  );
}

export default ContentGeneratorPage;
