const BASE = 'http://localhost:7823';

async function getColabTab() {
  const tabs = await chrome.tabs.query({ url: 'https://colab.research.google.com/*' });
  return tabs[0] || null;
}

async function poll() {
  let cmd;
  try {
    const r = await fetch(`${BASE}/poll`);
    if(!r.ok) return;
    cmd = await r.json();
    if(!cmd) return;
  } catch(e) {
    return;
  }

  const tab = await getColabTab();
  if(!tab) {
    await postResult({ id: cmd.id, error: 'no Colab tab open' });
    return;
  }

  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
  } catch(e) {}

  chrome.tabs.sendMessage(tab.id, cmd, async (result) => {
    if(chrome.runtime.lastError) {
      await postResult({ id: cmd.id, error: chrome.runtime.lastError.message });
      return;
    }
    await postResult({ id: cmd.id, ...result });
  });
}

async function postResult(data) {
  try {
    await fetch(`${BASE}/result`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  } catch(e) {}
}

// alarms fire every minute minimum, so we chain polls via recursive setTimeout
// keeping the service worker alive with a keepAlive alarm
chrome.alarms.create('keepAlive', { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(() => poll());

// fast polling loop — re-registers itself to keep worker alive
async function fastPoll() {
  await poll();
  setTimeout(fastPoll, 700);
}

chrome.runtime.onStartup.addListener(fastPoll);
chrome.runtime.onInstalled.addListener(fastPoll);
fastPoll();
