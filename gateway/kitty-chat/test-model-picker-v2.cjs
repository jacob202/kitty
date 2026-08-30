const { chromium } = require('/Users/jacobbrizinnski/Projects/kitty/.worktrees/daily-driver-model-truth-20260829/gateway/kitty-chat/node_modules/playwright');

const SCREENSHOT_DIR = '/Users/jacobbrizinnski/Projects/kitty/.worktrees/daily-driver-model-truth-20260829/.worktree-artifacts/pr672-346f1a06';

const PICKER_CLICK_TARGETS = [
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

const OPTION_SELECTORS = [
  '[role="option"]',
  '[role="menuitem"]',
  '[role="menuitemradio"]',
  '[role="listbox"] > *',
  '[role="listbox"] [role="option"]',
  'option',
  '[class*="option"]',
  '[class*="Option"]',
];

const FORBIDDEN_PATTERNS = ['deepseek-', 'deepseek_', 'Qwen3', 'openrouter/', '4bit', 'localhost:', '127.0.0.1:', ':4190', ':4191', 'Traceback', 'stack trace', 'TypeError', 'ReferenceError'];

async function run() {
  const results = {
    desktop: { passed: false, modelLabels: [], errors: [], rawAliasesFound: [] },
    iphone: { passed: false, modelLabels: [], errors: [], rawAliasesFound: [], hasOverflow: false },
    reload: { passed: false, modelLabels: [], errors: [] },
    degraded: { passed: false, errors: [], rawAliasesFound: [], hasRecoveryMessage: false },
    consoleErrors: [],
    allScreenshots: []
  };

  const browser = await chromium.launch({ headless: true });

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
      
      // Find and click model picker button
      let pickerOpened = false;
      for (const target of PICKER_CLICK_TARGETS) {
        try {
          const el = await desktopPage.$(target);
          if (el && await el.isVisible()) {
            const text = await el.textContent();
            console.log(`Desktop: Found picker: ${target} -> "${text?.trim().substring(0, 80)}"`);
            await el.click();
            await desktopPage.waitForTimeout(1000);
            pickerOpened = true;
            await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/02-desktop-picker-opened.png`, fullPage: false });
            results.allScreenshots.push('02-desktop-picker-opened.png');
            break;
          }
        } catch(e) { /* continue */ }
      }
      
      // Get model options
      for (const sel of OPTION_SELECTORS) {
        try {
          const opts = await desktopPage.$$(sel);
          for (const opt of opts) {
            const visible = await opt.isVisible().catch(() => false);
            if (visible) {
              const text = await opt.textContent().catch(() => '');
              if (text?.trim() && text.length > 2) {
                results.desktop.modelLabels.push(text.trim());
                console.log(`  Option: "${text.trim().substring(0, 120)}"`);
              }
            }
          }
          if (results.desktop.modelLabels.length > 0) break;
        } catch(e) { /* continue */ }
      }
      
      // Select an option and verify
      if (results.desktop.modelLabels.length > 0) {
        console.log('\n=== SELECTING AN OPTION ===');
        // Click the first option text that contains a role name
        const roleNames = ['Daily Kitty', 'Quick', 'Think', 'Code', 'Vision'];
        for (const role of roleNames) {
          try {
            const optEl = await desktopPage.$(`text="${role}"`);
            if (optEl && await optEl.isVisible()) {
              await optEl.click();
              await desktopPage.waitForTimeout(800);
              console.log(`Selected: ${role}`);
              break;
            }
          } catch(e) { /* continue */ }
        }
        await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/03-desktop-option-selected.png`, fullPage: false });
        results.allScreenshots.push('03-desktop-option-selected.png');
        
        // Verify page is still coherent
        const afterSelectText = await desktopPage.textContent('body');
        console.log('Page coherent after selection:', afterSelectText.length > 50 ? 'Yes' : 'No');
      }
      
      // Check for raw aliases in the visible text
      const pageText = await desktopPage.textContent('body');
      results.desktop.rawAliasesFound = FORBIDDEN_PATTERNS.filter(p => pageText.includes(p));
      console.log('\nDesktop raw aliases found:', results.desktop.rawAliasesFound.length > 0 ? results.desktop.rawAliasesFound : 'None');
      
      results.desktop.errors = desktopConsoleLogs.filter(l => l.type === 'error');
      results.desktop.passed = true;
      
    } catch(e) {
      console.error('Desktop error:', e.message);
      results.desktop.errors.push({ type: 'exception', text: e.message });
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
      
      // Check overflow
      const overflowCheck = await iphonePage.evaluate(() => ({
        docWidth: document.documentElement.scrollWidth,
        viewWidth: window.innerWidth,
        hasOverflow: document.documentElement.scrollWidth > window.innerWidth
      }));
      console.log(`iPhone overflow: docWidth=${overflowCheck.docWidth}, viewWidth=${overflowCheck.viewWidth}, overflow=${overflowCheck.hasOverflow}`);
      results.iphone.hasOverflow = overflowCheck.hasOverflow;
      
      // Find and click model picker on mobile
      let mobilePickerOpened = false;
      for (const target of PICKER_CLICK_TARGETS) {
        try {
          const el = await iphonePage.$(target);
          if (el && await el.isVisible()) {
            const text = await el.textContent();
            console.log(`iPhone: Found picker: ${target} -> "${text?.trim().substring(0, 80)}"`);
            await el.click();
            await iphonePage.waitForTimeout(1000);
            mobilePickerOpened = true;
            await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/05-iphone-picker-opened.png`, fullPage: false });
            results.allScreenshots.push('05-iphone-picker-opened.png');
            break;
          }
        } catch(e) { /* continue */ }
      }
      
      // Get model options on mobile
      for (const sel of OPTION_SELECTORS) {
        try {
          const opts = await iphonePage.$$(sel);
          for (const opt of opts) {
            const visible = await opt.isVisible().catch(() => false);
            if (visible) {
              const text = await opt.textContent().catch(() => '');
              if (text?.trim() && text.length > 2) {
                results.iphone.modelLabels.push(text.trim());
                console.log(`  Option: "${text.trim().substring(0, 120)}"`);
              }
            }
          }
          if (results.iphone.modelLabels.length > 0) break;
        } catch(e) { /* continue */ }
      }
      
      // If picker opened, take screenshot of it
      if (mobilePickerOpened && results.iphone.modelLabels.length > 0) {
        // Select an option
        const roleNames = ['Daily Kitty', 'Quick', 'Think', 'Code', 'Vision'];
        for (const role of roleNames) {
          try {
            const optEl = await iphonePage.$(`text="${role}"`);
            if (optEl && await optEl.isVisible()) {
              await optEl.click();
              await iphonePage.waitForTimeout(800);
              console.log(`iPhone selected: ${role}`);
              break;
            }
          } catch(e) { /* continue */ }
        }
        await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/05b-iphone-option-selected.png`, fullPage: false });
        results.allScreenshots.push('05b-iphone-option-selected.png');
      }
      
      // Check for raw aliases
      const iphoneText = await iphonePage.textContent('body');
      results.iphone.rawAliasesFound = FORBIDDEN_PATTERNS.filter(p => iphoneText.includes(p));
      console.log('iPhone raw aliases:', results.iphone.rawAliasesFound.length > 0 ? results.iphone.rawAliasesFound : 'None');
      
      results.iphone.errors = iphoneConsoleLogs.filter(l => l.type === 'error');
      results.iphone.passed = !overflowCheck.hasOverflow;
      
    } catch(e) {
      console.error('iPhone error:', e.message);
      results.iphone.errors.push({ type: 'exception', text: e.message });
    }

    // ============ SCENARIO 3: iPhone reload ============
    console.log('\n\n=== SCENARIO 3: iPhone reload ===');
    try {
      await iphonePage.reload({ waitUntil: 'networkidle', timeout: 15000 });
      console.log('iPhone reloaded');
      
      await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/06-iphone-reload.png`, fullPage: false });
      results.allScreenshots.push('06-iphone-reload.png');
      
      const reloadOverflow = await iphonePage.evaluate(() => ({
        docWidth: document.documentElement.scrollWidth,
        viewWidth: window.innerWidth,
        hasOverflow: document.documentElement.scrollWidth > window.innerWidth
      }));
      console.log(`Reload overflow: ${reloadOverflow.hasOverflow}`);
      
      const reloadText = await iphonePage.textContent('body');
      const reloadLabels = ['Daily Kitty', 'Quick', 'Think', 'Code', 'Vision'];
      results.reload.modelLabels = reloadLabels.filter(l => reloadText.includes(l));
      console.log('Reload labels found:', results.reload.modelLabels);
      
      // Verify picker is still accessible after reload
      for (const target of PICKER_CLICK_TARGETS) {
        try {
          const el = await iphonePage.$(target);
          if (el && await el.isVisible()) {
            console.log(`Reload: picker still accessible via ${target}`);
            await el.click();
            await iphonePage.waitForTimeout(1000);
            await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/06b-iphone-reload-picker.png`, fullPage: false });
            results.allScreenshots.push('06b-iphone-reload-picker.png');
            
            // Check options are still there
            for (const sel of OPTION_SELECTORS) {
              const opts = await iphonePage.$$(sel);
              let count = 0;
              for (const opt of opts) {
                if (await opt.isVisible().catch(() => false)) count++;
              }
              if (count > 0) {
                console.log(`Reload: ${count} visible options found`);
                break;
              }
            }
            break;
          }
        } catch(e) { /* continue */ }
      }
      
      results.reload.passed = results.reload.modelLabels.length > 0 && !reloadOverflow.hasOverflow;
      
    } catch(e) {
      console.error('Reload error:', e.message);
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
      console.log('\n=== DEGRADED PAGE VISIBLE TEXT (first 2000 chars) ===');
      // Extract just meaningful text (skip RSC payloads)
      const meaningfulText = degradedText.replace(/\(self\.__next_f.*$/s, '').trim();
      console.log(meaningfulText.substring(0, 2000));
      
      // Check raw aliases
      results.degraded.rawAliasesFound = FORBIDDEN_PATTERNS.filter(p => degradedText.includes(p));
      console.log('\nDegraded raw aliases:', results.degraded.rawAliasesFound.length > 0 ? results.degraded.rawAliasesFound : 'None');
      
      // Check recovery indicators
      const recoveryIndicators = ['unavailable', 'error', 'failed', 'try again', 'retry', 'offline', 'connection', 'cannot', "can't", 'unable', 'not available', 'recover', 'check', 'down', 'reconnect'];
      const foundRecovery = recoveryIndicators.filter(i => degradedText.toLowerCase().includes(i));
      console.log('Recovery indicators:', foundRecovery);
      results.degraded.hasRecoveryMessage = foundRecovery.length > 0;
      
      // Check for visible error/recovery elements
      const errorElements = await degradedPage.$$eval('*', els => 
        els.filter(e => {
          const style = window.getComputedStyle(e);
          const text = e.textContent?.toLowerCase() || '';
          return (text.includes('unavailable') || text.includes('offline') || text.includes('error') || text.includes('reconnect')) 
            && e.offsetHeight > 0 && style.display !== 'none';
        }).map(e => ({ tag: e.tagName, text: e.textContent?.substring(0, 200), className: e.className?.substring(0, 100) }))
      );
      console.log('Error/recovery elements:', JSON.stringify(errorElements.slice(0, 5)));
      
      // Check that model control isn't replaced with raw aliases
      const modelControl = await degradedPage.$('[role="option"]');
      console.log('Model options visible in degraded:', modelControl ? 'Yes (unexpected)' : 'No (correct)');
      
      // List all visible text blocks
      const degradedVisibleText = await degradedPage.$$eval('div, span, p, h1, h2, h3, h4, h5, h6, button, label', els =>
        els.filter(e => e.offsetHeight > 0 && e.textContent?.trim() && e.textContent.length < 200)
          .map(e => e.textContent.trim())
          .filter((v, i, a) => a.indexOf(v) === i)
          .slice(0, 30)
      );
      console.log('\nDegraded visible text blocks:', degradedVisibleText);
      
      results.degraded.errors = degradedConsoleLogs.filter(l => l.type === 'error');
      results.degraded.passed = results.degraded.rawAliasesFound.length === 0 && results.degraded.hasRecoveryMessage;
      
    } catch(e) {
      console.error('Degraded error:', e.message);
      results.degraded.errors.push({ type: 'exception', text: e.message });
    }
    
    await degradedCtx.close();

  } finally {
    await browser.close();
  }

  // Output results
  console.log('\n\n=== FINAL RESULTS ===');
  console.log(JSON.stringify(results, null, 2));
}

run().catch(e => {
  console.error('FATAL:', e);
  process.exit(1);
});
