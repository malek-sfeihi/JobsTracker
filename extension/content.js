// Adds a floating "JobsTracker" button to Gmail that opens the online dashboard.
const DASHBOARD_URL = "https://jobstracker-malek.streamlit.app";

// Gmail never reloads the page, so the button is added once and stays
if (!document.getElementById("jobstracker-button")) {
  const button = document.createElement("a");
  button.id = "jobstracker-button";
  button.href = DASHBOARD_URL;
  button.target = "_blank";  // new tab: Gmail stays open
  button.rel = "noopener";
  button.textContent = "🌿 JobsTracker";
  button.title = "Open your applications dashboard";
  document.body.appendChild(button);
}
