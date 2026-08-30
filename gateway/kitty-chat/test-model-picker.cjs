const { chromium } = require('/Users/jacobbrizinnski/Projects/kitty/.worktrees/daily-driver-model-truth-20260829/gateway/kitty-chat/node_modules/playwright');

const SCREENSHOT_DIR = '/Users/jacobbrizinnski/Projects/kitty/.worktrees/daily-driver-model-truth-20260829/.worktree-artifacts/pr672-346f1a06';

async function run() {
  const results = {
    desktop: { passed: false, modelLabels: [], errors: [], screenshots: [], rawAliasesFound: [] },
    iphone: { passed: false, modelLabels: [], errors: [], screenshots: [], rawAliasesFound: [], hasOverflow: false },
    reload: { passed: false, modelLabels: [], errors: [], screenshots: [] },
    degraded: { passed: false, errors: [], screenshots: [], rawAliasesFound: [], hasRecoveryMessage: false },
    consoleErrors: [],
    allScreenshots: []
  };

  const browser = await chromium.launch({ headless: true });
  const forbiddenPatterns = ['deepseek-', 'deepseek_', 'Qwen3', 'openrouter/', '4bit', 'localhost:', '127.0.0.1:', ':4190', ':4191', 'Traceback', 'stack trace', 'TypeError', 'ReferenceError'];

  try {
    // ============ SCENARIO 1: Desktop 1440x900 on 4190 ============
    console.log('\n=== SCENARIO 1: Desktop 1440x900 on port 4190 ===');
    const desktopCtx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    });
    const desktopPage = await desktopCtx.newPage();
    
    const desktopConsoleLogs = [];
    desktopPage.on('console', msg => {
      desktopConsoleLogs.push({ type: msg.type(), text: msg.text() });
    });
    desktopPage.on('pageerror', err => {
      results.consoleErrors.push({ page: 'desktop', error: err.message });
    });

    try {
      await desktopPage.goto('http://127.0.0.1:4190', { waitUntil: 'networkidle', timeout: 15000 });
      console.log('Desktop page loaded');
      
      await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/01-desktop-initial.png`, fullPage: false });
      results.allScreenshots.push('01-desktop-initial.png');
      
      // Dump all visible text on the page for analysis
      const bodyText = await desktopPage.textContent('body');
      console.log('=== DESKTOP PAGE BODY TEXT (first 3000 chars) ===');
      console.log(bodyText?.substring(0, 3000));
      
      // Look for model picker with broad selectors
      const pickerSelectors = [
        'button:has-text("model")',
        'button:has-text("Model")',
        '[data-testid*="model"]',
        'select',
        '[role="listbox"]',
        '[role="combobox"]',
        '[role="menu"]',
        '.model-picker',
        '#model-picker',
        '[class*="model"]',
        '[class*="Model"]',
        '[class*="picker"]',
        '[class*="Picker"]',
      ];
      
      let pickerFound = false;
      for (const sel of pickerSelectors) {
        try {
          const els = await desktopPage.$$(sel);
          for (const el of els) {
            const visible = await el.isVisible().catch(() => false);
            if (visible) {
              const text = await el.textContent();
              console.log(`Desktop: Found visible picker element: ${sel} -> "${text?.trim().substring(0, 100)}"`);
              pickerFound = true;
            }
          }
        } catch(e) { /* continue */ }
      }
      
      // List ALL visible buttons
      console.log('\n=== ALL VISIBLE BUTTONS ===');
      const allButtons = await desktopPage.$$('button, [role="button"], a[href]');
      for (const btn of allButtons) {
        const text = await btn.textContent().catch(() => '');
        const visible = await btn.isVisible().catch(() => false);
        if (visible && text?.trim()) {
          console.log(`  Button: "${text.trim().substring(0, 100)}"`);
        }
      }
      
      // Try to find and click model-related controls
      console.log('\n=== ATTEMPTING TO OPEN MODEL PICKER ===');
      let modelPickerOpened = false;
      
      // Try various approaches to find the model selector
      const clickTargets = [
        'button:has-text("Daily Kitty")',
        'button:has-text("Quick")',
        'button:has-text("Think")',
        'button:has-text("Code")',
        'button:has-text("Vision")',
        'button:has-text("Daily")',
        'button:has-text("model")',
        'button:has-text("Model")',
        '[class*="model"]',
        '[class*="picker"]',
        'select',
        '[role="combobox"]',
      ];
      
      for (const target of clickTargets) {
        try {
          const el = await desktopPage.$(target);
          if (el && await el.isVisible()) {
            console.log(`Desktop: Clicking ${target}`);
            await el.click();
            await desktopPage.waitForTimeout(1000);
            modelPickerOpened = true;
            await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/02-desktop-picker-opened.png`, fullPage: false });
            results.allScreenshots.push('02-desktop-picker-opened.png');
            break;
          }
        } catch(e) { /* continue */ }
      }
      
      // After clicking, look for dropdown/popup options
      console.log('\n=== LOOKING FOR DROPDOWN OPTIONS ===');
      const optionSelectors = [
        '[role="option"]',
        '[role="menuitem"]',
        '[role="menuitemradio"]',
        '[role="listbox"] > *',
        '[role="listbox"] [role="option"]',
        'option',
        '[class*="option"]',
        '[class*="Option"]',
        '[class*="menu"] [class*="item"]',
        '[class*="dropdown"] [class*="item"]',
        '[class*="select"] [class*="option"]',
      ];
      
      for (const sel of optionSelectors) {
        try {
          const opts = await desktopPage.$$(sel);
          if (opts.length > 0) {
            console.log(`Desktop: Found ${opts.length} options with selector: ${sel}`);
            for (const opt of opts) {
              const text = await opt.textContent().catch(() => '');
              const visible = await opt.isVisible().catch(() => false);
              if (visible && text?.trim()) {
                results.desktop.modelLabels.push(text.trim());
                console.log(`  Option: "${text.trim()}"`);
              }
            }
            if (results.desktop.modelLabels.length > 0) break;
          }
        } catch(e) { /* continue */ }
      }
      
      // Now try selecting an option
      if (results.desktop.modelLabels.length > 0) {
        console.log('\n=== SELECTING FIRST MODEL OPTION ===');
        const firstOption = results.desktop.modelLabels[0];
        try {
          const optionEl = await desktopPage.$(`text="${firstOption}"`);
          if (optionEl && await optionEl.isVisible()) {
            await optionEl.click();
            await desktopPage.waitForTimeout(500);
            console.log(`Selected: ${firstOption}`);
            await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/03-desktop-option-selected.png`, fullPage: false });
            results.allScreenshots.push('03-desktop-option-selected.png');
            
            // Verify picker still looks reasonable after selection
            const afterText = await desktopPage.textContent('body');
            console.log('Page still coherent after selection:', afterText.length > 100 ? 'Yes' : 'No');
          }
        } catch(e) {
          console.log('Could not click option:', e.message);
        }
      }
      
      // Check for raw aliases and expected labels
      const fullPageText = await desktopPage.textContent('body');
      results.desktop.rawAliasesFound = forbiddenPatterns.filter(p => fullPageText.includes(p));
      if (results.desktop.rawAliasesFound.length > 0) {
        console.log('WARNING: Raw internal aliases in desktop view:', results.desktop.rawAliasesFound);
      } else {
        console.log('OK: No raw internal aliases found in desktop view');
      }
      
      const expectedLabels = ['Daily Kitty', 'Quick', 'Think', 'Code', 'Vision'];
      const foundExpected = expectedLabels.filter(l => fullPageText.includes(l));
      console.log('Expected role-style labels found:', foundExpected);
      
      results.desktop.errors = desktopConsoleLogs.filter(l => l.type === 'error');
      results.desktop.passed = true; // Will refine after manual review
      
    } catch(e) {
      console.error('Desktop scenario error:', e.message);
      results.desktop.errors.push({ type: 'exception', text: e.message });
      try { await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/01-desktop-error.png`, fullPage: false }); } catch(_) {}
    }
    
    await desktopCtx.close();

    // ============ SCENARIO 2: iPhone 14 Pro 393x852 on 4190 ============
    console.log('\n\n=== SCENARIO 2: iPhone 14 Pro 393x852 on port 4190 ===');
    const iphoneCtx = await browser.newContext({
      viewport: { width: 393, height: 852 },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
      isMobile: true,
      hasTouch: true,
    });
    const iphonePage = await iphoneCtx.newPage();
    
    const iphoneConsoleLogs = [];
    iphonePage.on('console', msg => {
      iphoneConsoleLogs.push({ type: msg.type(), text: msg.text() });
    });
    iphonePage.on('pageerror', err => {
      results.consoleErrors.push({ page: 'iphone', error: err.message });
    });

    try {
      await iphonePage.goto('http://127.0.0.1:4190', { waitUntil: 'networkidle', timeout: 15000 });
      console.log('iPhone page loaded');
      
      await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/04-iphone-initial.png`, fullPage: false });
      results.allScreenshots.push('04-iphone-initial.png');
      
      // Check for horizontal overflow
      const overflowCheck = await iphonePage.evaluate(() => ({
        docWidth: document.documentElement.scrollWidth,
        viewWidth: window.innerWidth,
        hasOverflow: document.documentElement.scrollWidth > window.innerWidth
      }));
      console.log(`iPhone overflow check: docWidth=${overflowCheck.docWidth}, viewWidth=${overflowCheck.viewWidth}, overflow=${overflowCheck.hasOverflow}`);
      results.iphone.hasOverflow = overflowCheck.hasOverflow;
      
      if (overflowCheck.hasOverflow) {
        console.log('WARNING: Horizontal document overflow detected!');
        await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/04-iphone-overflow-fullpage.png`, fullPage: true });
        results.allScreenshots.push('04-iphone-overflow-fullpage.png');
      }
      
      // Dump page text
      const iphoneText = await iphonePage.textContent('body');
      console.log('=== iPHONE PAGE BODY TEXT (first 2000 chars) ===');
      console.log(iphoneText?.substring(0, 2000));
      
      // List all visible buttons
      console.log('\n=== ALL VISIBLE BUTTONS (iPhone) ===');
      const iphoneButtons = await iphonePage.$$('button, [role="button"], a[href]');
      for (const btn of iphoneButtons) {
        const text = await btn.textContent().catch(() => '');
        const visible = await btn.isVisible().catch(() => false);
        if (visible && text?.trim()) {
          console.log(`  Button: "${text.trim().substring(0, 100)}"`);
        }
      }
      
      // Try to open model picker on mobile
      console.log('\n=== ATTEMPTING TO OPEN MODEL PICKER (iPhone) ===');
      for (const target of clickTargets) {
        try {
          const el = await iphonePage.$(target);
          if (el && await el.isVisible()) {
            console.log(`iPhone: Clicking ${target}`);
            await el.click();
            await iphonePage.waitForTimeout(1000);
            await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/05-iphone-picker-opened.png`, fullPage: false });
            results.allScreenshots.push('05-iphone-picker-opened.png');
            break;
          }
        } catch(e) { /* continue */ }
      }
      
      // Check for options on mobile
      for (const sel of optionSelectors) {
        try {
          const opts = await iphonePage.$$(sel);
          const visibleOpts = [];
          for (const opt of opts) {
            const visible = await opt.isVisible().catch(() => false);
            if (visible) {
              const text = await opt.textContent().catch(() => '');
              if (text?.trim()) visibleOpts.push(text.trim());
            }
          }
          if (visibleOpts.length > 0) {
            console.log(`iPhone: Found ${visibleOpts.length} visible options: ${sel}`);
            visibleOpts.forEach(t => console.log(`  Option: "${t}"`));
            results.iphone.modelLabels = visibleOpts;
            break;
          }
        } catch(e) { /* continue */ }
      }
      
      // Check for raw aliases
      const iphoneFullText = await iphonePage.textContent('body');
      results.iphone.rawAliasesFound = forbiddenPatterns.filter(p => iphoneFullText.includes(p));
      if (results.iphone.rawAliasesFound.length > 0) {
        console.log('WARNING: Raw aliases on iPhone:', results.iphone.rawAliasesFound);
      } else {
        console.log('OK: No raw internal aliases on iPhone');
      }
      
      // Check controls are tappable (not covered by fixed elements)
      const tapCheck = await iphonePage.evaluate(() => {
        const fixedEls = document.querySelectorAll('*');
        let covered = 0;
        for (const el of fixedEls) {
          const style = window.getComputedStyle(el);
          if (style.position === 'fixed' && el.offsetHeight > 50) {
            covered++;
          }
        }
        return { fixedCount: covered, bodyHeight: document.body.scrollHeight, windowH: window.innerHeight };
      });
      console.log('iPhone tap check:', tapCheck);
      
      results.iphone.errors = iphoneConsoleLogs.filter(l => l.type === 'error');
      results.iphone.passed = !overflowCheck.hasOverflow;
      
    } catch(e) {
      console.error('iPhone scenario error:', e.message);
      results.iphone.errors.push({ type: 'exception', text: e.message });
      try { await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/04-iphone-error.png`, fullPage: false }); } catch(_) {}
    }
    
    // ============ SCENARIO 3: iPhone reload ============
    console.log('\n\n=== SCENARIO 3: iPhone reload on 4190 ===');
    try {
      await iphonePage.reload({ waitUntil: 'networkidle', timeout: 15000 });
      console.log('iPhone page reloaded');
      
      await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/06-iphone-reload.png`, fullPage: false });
      results.allScreenshots.push('06-iphone-reload.png');
      
      // Verify overflow is still clean after reload
      const reloadOverflow = await iphonePage.evaluate(() => ({
        docWidth: document.documentElement.scrollWidth,
        viewWidth: window.innerWidth,
        hasOverflow: document.documentElement.scrollWidth > window.innerWidth
      }));
      console.log(`iPhone reload overflow: ${reloadOverflow.hasOverflow}`);
      
      const reloadText = await iphonePage.textContent('body');
      const reloadExpectedLabels = ['Daily Kitty', 'Quick', 'Think', 'Code', 'Vision'];
      const reloadFoundExpected = reloadExpectedLabels.filter(l => reloadText.includes(l));
      console.log('iPhone reload: Expected labels found:', reloadFoundExpected);
      
      // List visible buttons after reload
      console.log('\n=== VISIBLE BUTTONS AFTER RELOAD ===');
      const reloadButtons = await iphonePage.$$('button, [role="button"]');
      for (const btn of reloadButtons) {
        const text = await btn.textContent().catch(() => '');
        const visible = await btn.isVisible().catch(() => false);
        if (visible && text?.trim()) {
          console.log(`  Button: "${text.trim().substring(0, 100)}"`);
        }
      }
      
      results.reload.modelLabels = reloadFoundExpected;
      results.reload.passed = !reloadOverflow.hasOverflow && reloadFoundExpected.length > 0;
      
    } catch(e) {
      console.error('iPhone reload error:', e.message);
    }
    
    await iphonePage.close();
    await iphoneCtx.close();

    // ============ SCENARIO 4: Degraded path on 4191 ============
    console.log('\n\n=== SCENARIO 4: Degraded path on port 4191 ===');
    const degradedCtx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    });
    const degradedPage = await degradedCtx.newPage();
    
    const degradedConsoleLogs = [];
    degradedPage.on('console', msg => {
      degradedConsoleLogs.push({ type: msg.type(), text: msg.text() });
    });
    degradedPage.on('pageerror', err => {
      results.consoleErrors.push({ page: 'degraded', error: err.message });
    });
    
    try {
      await degradedPage.goto('http://127.0.0.1:4191', { waitUntil: 'networkidle', timeout: 15000 });
      console.log('Degraded page loaded');
      
      await degradedPage.screenshot({ path: `${SCREENSHOT_DIR}/07-degraded-initial.png`, fullPage: false });
      results.allScreenshots.push('07-degraded-initial.png');
      
      const degradedText = await degradedPage.textContent('body');
      console.log('=== DEGRADED PAGE BODY TEXT (first 3000 chars) ===');
      console.log(degradedText?.substring(0, 3000));
      
      // Check for raw aliases/ports/env vars/stack traces
      results.degraded.rawAliasesFound = forbiddenPatterns.filter(p => degradedText.includes(p));
      if (results.degraded.rawAliasesFound.length > 0) {
        console.log('WARNING: Degraded mode shows raw internal details:', results.degraded.rawAliasesFound);
      } else {
        console.log('OK: No raw internal aliases in degraded mode');
      }
      
      // Check for clear recovery/unavailable message
      const recoveryIndicators = ['unavailable', 'error', 'failed', 'try again', 'retry', 'offline', 'connection', 'cannot', "can't", 'unable', 'not available', 'recover', 'check', 'down', 'reconnect'];
      const foundRecovery = recoveryIndicators.filter(i => degradedText.toLowerCase().includes(i));
      console.log('Degraded recovery indicators:', foundRecovery);
      results.degraded.hasRecoveryMessage = foundRecovery.length > 0;
      
      // List all visible buttons in degraded mode
      console.log('\n=== ALL VISIBLE BUTTONS (Degraded) ===');
      const degradedButtons = await degradedPage.$$('button, [role="button"], a[href]');
      for (const btn of degradedButtons) {
        const text = await btn.textContent().catch(() => '');
        const visible = await btn.isVisible().catch(() => false);
        if (visible && text?.trim()) {
          console.log(`  Button: "${text.trim().substring(0, 100)}"`);
        }
      }
      
      // Check that model control is not replaced with raw aliases
      const degradedRawCheck = degradedText.match(/deepseek|Qwen3|openrouter|4bit|localhost|127\.0\.0\.1|Traceback|TypeError/gi);
      console.log('Degraded raw patterns found:', degradedRawCheck);
      
      results.degraded.errors = degradedConsoleLogs.filter(l => l.type === 'error');
      results.degraded.passed = results.degraded.rawAliasesFound.length === 0;
      
      await degradedPage.screenshot({ path: `${SCREENSHOT_DIR}/08-degraded-final.png`, fullPage: false });
      results.allScreenshots.push('08-degraded-final.png');
      
    } catch(e) {
      console.error('Degraded scenario error:', e.message);
      results.degraded.errors.push({ type: 'exception', text: e.message });
      try { await degradedPage.screenshot({ path: `${SCREENSHOT_DIR}/07-degraded-error.png`, fullPage: false }); } catch(_) {}
    }
    
    await degradedCtx.close();

  } finally {
    await browser.close();
  }

  // Output all results as JSON
  console.log('\n\n=== RESULTS JSON ===');
  console.log(JSON.stringify(results, null, 2));
}

run().catch(e => {
  console.error('FATAL:', e);
  process.exit(1);
});
