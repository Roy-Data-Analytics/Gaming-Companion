export function chooseTab(tabs, preferredUrl) {
  const valid = tabs.filter(tab => {
    try { return ["chatgpt.com", "chat.openai.com"].includes(new URL(tab.url).hostname); }
    catch { return false; }
  });
  const exact = valid.filter(tab => tab.url === preferredUrl);
  if (exact.length === 1) return exact[0];
  if (exact.length > 1) return null;
  // With multiple different conversations never guess where screenshots belong.
  return valid.length === 1 ? valid[0] : null;
}
