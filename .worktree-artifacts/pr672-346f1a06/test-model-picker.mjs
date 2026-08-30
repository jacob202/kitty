import { chromium } from 'playwright';

const SCREENSHOT_DIR = '/Users/jacobbrizinnski/Projects/kitty/.worktrees/daily-driver-model-truth-20260829/.worktree-artifacts/pr672-346f1a06';

async function run() {
  const results = {
    desktop: { passed: false, modelLabels: [], errors: [], screenshots: [] },
    iphone: { passed: false, modelLabels: [], errors: [], screenshots: [] },
    reload: { passed: false, modelLabels: [], errors: [], screenshots: [] },
    degraded: { passed: false, errors: [], screenshots: [], rawAliasesFound: [] },
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
    
    // Collect console messages
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
      
      // Screenshot initial load
      await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/01-desktop-initial.png`, fullPage: false });
      results.allScreenshots.push('01-desktop-initial.png');
      
      // Look for model picker - try various selectors
      let pickerFound = false;
      const pickerSelectors = [
        'button:has-text("model")',
        '[data-testid*="model"]',
        'select',
        '[role="listbox"]',
        '[role="combobox"]',
        'button:has-text("Model")',
        '.model-picker',
        '#model-picker',
        '[class*="model"]',
        '[class*="Model"]',
        'button:has-text("Daily")',
        'button:has-text("Quick")',
        'button:has-text("Think")',
        'button:has-text("Code")',
        'button:has-text("Vision")',
      ];
      
      for (const sel of pickerSelectors) {
        try {
          const el = await desktopPage.$(sel);
          if (el) {
            const visible = await el.isVisible();
            if (visible) {
              console.log(`Desktop: Found picker element with selector: ${sel}`);
              pickerFound = true;
              
              // Try clicking to open the picker
              await el.click();
              await desktopPage.waitForTimeout(500);
              
              // Screenshot after click
              await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/02-desktop-picker-opened.png`, fullPage: false });
              results.allScreenshots.push('02-desktop-picker-opened.png');
              break;
            }
          }
        } catch(e) { /* continue */ }
      }
      
      if (!pickerFound) {
        console.log('Desktop: No obvious picker found. Dumping page content...');
        const pageText = await desktopPage.textContent('body');
        console.log('Body text (first 2000 chars):', pageText?.substring(0, 2000));
        
        // Try to find any clickable elements
        const allButtons = await desktopPage.$$('button, [role="button"], a, select');
        console.log(`Found ${allButtons.length} clickable elements`);
        for (const btn of allButtons.slice(0, 20)) {
          const text = await btn.textContent();
          const tag = await btn.evaluate(el => el.tagName + ' ' + el.className);
          if (text?.trim()) {
            console.log(`  Button: "${text.trim().substring(0, 80)}" (${tag})`);
          }
        }
      }
      
      // Now scan for model options if picker is open or available
      const modelOptions = await desktopPage.$$('[role="option"], [role="menuitem"], [role="menuitemradio"], [data-testid*="model-option"], option, [class*="option"], [class*="Option"]');
      if (modelOptions.length > 0) {
        console.log(`Desktop: Found ${modelOptions.length} model options`);
        for (const opt of modelOptions) {
          const text = await opt.textContent();
          if (text?.trim()) {
            results.desktop.modelLabels.push(text.trim());
            console.log(`  Option: "${text.trim()}"`);
          }
        }
      } else {
        // Try to find model-related text in any dropdown/menu/list
        const allElements = await desktopPage.$$('*');
        const rawAliases = ['deepseek', 'Qwen', 'openrouter', 'openai/', 'anthropic/', 'claude/', 'gpt-', 'llama', 'mistral', 'phi-', 'qwen', 'glm', '4bit'];
        const bodyText = await desktopPage.textContent('body');
        console.log('Checking body text for model-related content...');
        
        // Get all visible text that might be model labels
        const textElements = await desktopPage.$$eval('div, span, p, li, a, button, option, label', els => 
          els.map(e => e.textContent?.trim()).filter(t => t && t.length > 0 && t.length < 100)
        );
        
        // Filter for likely model-related text
        const likelyModels = textElements.filter(t => {
          const lower = t.toLowerCase();
          return lower.includes('daily') || lower.includes('quick') || lower.includes('think') || 
                 lower.includes('code') || lower.includes('vision') || lower.includes('model') ||
                 lower.includes('kitty') || lower.includes('chat');
        });
        console.log('Likely model-related text elements:', likelyModels.slice(0, 20));
      }
      
      // Check for any visible model text in the page
      const pageContent = await desktopPage.textContent('body');
      
      // Check for raw internal aliases that should NOT appear
      const forbiddenPatterns = ['deepseek-', 'Qwen3', 'openrouter/', '4bit', 'localhost:', '127.0.0.1:', ':4190', ':4191', 'stack trace', 'Traceback', 'Traceback'];
      results.desktop.rawAliasesFound = forbiddenPatterns.filter(p => pageContent.includes(p));
      if (results.desktop.rawAliasesFound.length > 0) {
        console.log('WARNING: Found raw internal aliases in desktop view:', results.desktop.rawAliasesFound);
      }
      
      // Check expected role-style labels
      const expectedLabels = ['Daily', 'Quick', 'Think', 'Code', 'Vision'];
      const foundExpected = expectedLabels.filter(l => pageContent.includes(l));
      console.log('Expected role-style labels found in page:', foundExpected);
      
      results.desktop.errors = desktopConsoleLogs.filter(l => l.type === 'error');
      results.desktop.passed = pickerFound || foundExpected.length > 0;
      
    } catch(e) {
      console.error('Desktop scenario error:', e.message);
      results.desktop.errors.push({ type: 'exception', text: e.message });
      await desktopPage.screenshot({ path: `${SCREENSHOT_DIR}/01-desktop-error.png`, fullPage: false }).catch(() => {});
    }
    
    await desktopCtx.close();

    // ============ SCENARIO 2: iPhone 14 Pro 393x852 on 4190 ============
    console.log('\n=== SCENARIO 2: iPhone 14 Pro 393x852 on port 4190 ===');
    const iphoneCtx = await browser.newContext({
      viewport: { width: 393, height: 852 },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
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
      
      await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/03-iphone-initial.png`, fullPage: false });
      results.allScreenshots.push('03-iphone-initial.png');
      
      // Check for horizontal overflow
      const docWidth = await iphonePage.evaluate(() => document.documentElement.scrollWidth);
      const viewWidth = await iphonePage.evaluate(() => window.innerWidth);
      const hasOverflow = docWidth > viewWidth;
      console.log(`iPhone: docWidth=${docWidth}, viewWidth=${viewWidth}, overflow=${hasOverflow}`);
      results.iphone.hasOverflow = hasOverflow;
      
      if (hasOverflow) {
        console.log('WARNING: Horizontal document overflow detected on iPhone!');
        await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/03-iphone-overflow.png`, fullPage: true });
      }
      
      // Look for model picker on mobile
      let mobilePickerFound = false;
      for (const sel of pickerSelectors) {
        try {
          const el = await iphonePage.$(sel);
          if (el) {
            const visible = await el.isVisible();
            if (visible) {
              console.log(`iPhone: Found picker element with selector: ${sel}`);
              mobilePickerFound = true;
              await el.click();
              await iphonePage.waitForTimeout(500);
              await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/04-iphone-picker-opened.png`, fullPage: false });
              results.allScreenshots.push('04-iphone-picker-opened.png');
              break;
            }
          }
        } catch(e) { /* continue */ }
      }
      
      // Check for expected labels and raw aliases on mobile
      const mobilePageText = await iphonePage.textContent('body');
      const mobileExpectedLabels = ['Daily', 'Quick', 'Think', 'Code', 'Vision'];
      const mobileFoundExpected = mobileExpectedLabels.filter(l => mobilePageText.includes(l));
      console.log('iPhone: Expected role-style labels found:', mobileFoundExpected);
      
      const mobileRawAliases = forbiddenPatterns.filter(p => mobilePageText.includes(p));
      results.iphone.rawAliasesFound = mobileRawAliases;
      if (mobileRawAliases.length > 0) {
        console.log('WARNING: Found raw internal aliases on iPhone:', mobileRawAliases);
      }
      
      // Check that controls are tappable (not clipped/obscured)
      const controlChecks = await iphonePage.evaluate(() => {
        const body = document.body;
        const html = document.documentElement;
        const overflowX = html.scrollWidth > window.innerWidth;
        const fixedElements = document.querySelectorAll('[style*="position: fixed"], [style*="position:fixed"]');
        return {
          overflowX,
          fixedCount: fixedElements.length,
          bodyHeight: body.scrollHeight,
          windowHeight: window.innerHeight,
        };
      });
      console.log('iPhone control checks:', controlChecks);
      
      results.iphone.modelLabels = mobileFoundExpected;
      results.iphone.errors = iphoneConsoleLogs.filter(l => l.type === 'error');
      results.iphone.passed = !hasOverflow && (mobilePickerFound || mobileFoundExpected.length > 0);
      
    } catch(e) {
      console.error('iPhone scenario error:', e.message);
      results.iphone.errors.push({ type: 'exception', text: e.message });
      await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/03-iphone-error.png`, fullPage: false }).catch(() => {});
    }
    
    // ============ SCENARIO 3: iPhone reload ============
    console.log('\n=== SCENARIO 3: iPhone reload on 4190 ===');
    try {
      await iphonePage.reload({ waitUntil: 'networkidle', timeout: 15000 });
      console.log('iPhone page reloaded');
      
      await iphonePage.screenshot({ path: `${SCREENSHOT_DIR}/05-iphone-reload.png`, fullPage: false });
      results.allScreenshots.push('05-iphone-reload.png');
      
      const reloadPageText = await iphonePage.textContent('body');
      const reloadExpectedLabels = ['Daily', 'Quick', 'Think', 'Code', 'Vision'];
      const reloadFoundExpected = reloadExpectedLabels.filter(l => reloadPageText.includes(l));
      console.log('iPhone reload: Expected role-style labels found:', reloadFoundExpected);
      
      results.reload.modelLabels = reloadFoundExpected;
      results.reload.passed = reloadFoundExpected.length > 0;
      
    } catch(e) {
      console.error('iPhone reload error:', e.message);
    }
    
    await iphonePage.close();
    await iphoneCtx.close();

    // ============ SCENARIO 4: Degraded path on 4191 ============
    console.log('\n=== SCENARIO 4: Degraded path on port 4191 ===');
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
      
      await degradedPage.screenshot({ path: `${SCREENSHOT_DIR}/06-degraded-initial.png`, fullPage: false });
      results.allScreenshots.push('06-degraded-initial.png');
      
      const degradedText = await degradedPage.textContent('body');
      console.log('Degraded page body (first 2000 chars):', degradedText?.substring(0, 2000));
      
      // Check for raw aliases, ports, env vars, stack traces in degraded mode
      const degradedForbiddenPatterns = ['deepseek-', 'Qwen3', 'openrouter/', '4bit', 'localhost:', '127.0.0.1:', ':4190', ':4191', 'Traceback', 'stack trace', 'TypeError', 'ReferenceError'];
      results.degraded.rawAliasesFound = degradedForbiddenPatterns.filter(p => degradedText.includes(p));
      if (results.degraded.rawAliasesFound.length > 0) {
        console.log('WARNING: Degraded mode shows raw internal details:', results.degraded.rawAliasesFound);
      }
      
      // Check for clear unavailable/recovery state indicators
      const recoveryIndicators = ['unavailable', 'error', 'failed', 'try again', 'retry', 'offline', 'connection', 'cannot', "can't", 'unable', 'not available', 'recover', 'check'];
      const foundRecovery = recoveryIndicators.filter(i => degradedText.toLowerCase().includes(i));
      console.log('Degraded recovery indicators found:', foundRecovery);
      
      results.degraded.hasRecoveryMessage = foundRecovery.length > 0;
      results.degraded.errors = degradedConsoleLogs.filter(l => l.type === 'error');
      results.degraded.passed = results.degraded.rawAliasesFound.length === 0;
      
    } catch(e) {
      console.error('Degraded scenario error:', e.message);
      results.degraded.errors.push({ type: 'exception', text: e.message });
      await degradedPage.screenshot({ path: `${SCREENSHOT_DIR}/06-degraded-error.png`, fullPage: false }).catch(() => {});
    }
    
    await degradedCtx.close();

  } finally {
    await browser.close();
  }

  // Output all results as JSON
  console.log('\n=== RESULTS JSON ===');
  console.log(JSON.stringify(results, null, 2));
}

run().catch(e => {
  console.error('FATAL:', e);
  process.exit(1);
});
