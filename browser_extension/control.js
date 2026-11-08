async function refresh() {
  try {
    const state = await chrome.runtime.sendMessage({type: "STATUS"});
    document.getElementById("log").textContent = `${state.connected ? "Connected: " + state.title : state.note}\n${state.logs.join("\n")}`;
  } catch (error) { document.getElementById("log").textContent = error.message; }
}
setInterval(refresh, 1000);
refresh();
