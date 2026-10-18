import "./placeholder-page.css";

// Stand-in for pages that haven't been built yet.
function PlaceholderPage({ title }) {
  return (
    <div className="placeholder-page">
      <h1>{title}</h1>
      <p>This page is coming soon.</p>
    </div>
  );
}

export default PlaceholderPage;
