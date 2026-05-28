// injected into colab pages by background.js

function getCells() {
  return Array.from(document.querySelectorAll('.cell'));
}

function getOutputText(cellEl) {
  const out = cellEl.querySelector('.output');
  return out ? out.innerText.trim() : '';
}

function isRunning(cellEl) {
  return cellEl.classList.contains('pending') || cellEl.classList.contains('running');
}

function runCell(index) {
  return new Promise((resolve) => {
    const cells = getCells();
    if(index < 0 || index >= cells.length) {
      resolve({ error: `cell ${index} not found — notebook has ${cells.length} cells` });
      return;
    }
    const cell = cells[index];

    // try colab's custom run button (multiple selector attempts)
    const btn =
      cell.querySelector('colab-run-button') ||
      cell.querySelector('.run-button') ||
      cell.querySelector('paper-icon-button[icon="av:play-arrow"]') ||
      cell.querySelector('button[title="Run cell"]');

    if(!btn) {
      // fallback: focus cell and send Ctrl+Enter
      cell.click();
      document.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Enter', ctrlKey: true, bubbles: true
      }));
    } else {
      btn.click();
    }

    // wait for execution to finish — poll every 300ms, timeout 5min
    let elapsed = 0;
    const POLL = 300;
    const TIMEOUT = 5 * 60 * 1000;
    const MIN_WAIT = 800; // always wait at least this long before checking

    const iv = setInterval(() => {
      elapsed += POLL;
      if(elapsed < MIN_WAIT) return;
      if(!isRunning(cell) || elapsed >= TIMEOUT) {
        clearInterval(iv);
        const output = getOutputText(cell);
        const result = { output };
        if(elapsed >= TIMEOUT) result.warning = 'timed out after 5 min';
        resolve(result);
      }
    }, POLL);
  });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if(msg.cmd === 'run_cell') {
    runCell(msg.index).then(sendResponse);
    return true; // keep channel open for async response
  }
  if(msg.cmd === 'get_output') {
    const cells = getCells();
    const idx = msg.index;
    if(idx < 0 || idx >= cells.length) {
      sendResponse({ error: `cell ${idx} not found` });
    } else {
      sendResponse({ output: getOutputText(cells[idx]) });
    }
  }
});
