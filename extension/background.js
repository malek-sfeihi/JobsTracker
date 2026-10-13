// Clicking the extension's icon in the Chrome toolbar also opens the dashboard
chrome.action.onClicked.addListener(() => {
  chrome.tabs.create({ url: "https://jobstracker-malek.streamlit.app" });
});
