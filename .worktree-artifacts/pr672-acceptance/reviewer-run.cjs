const { chromium } = require('/Users/jacobbrizinnski/Projects/kitty/.worktrees/daily-driver-model-truth-20260829/gateway/kitty-chat/node_modules/playwright');
const fs=require('fs'); const OUT='/Users/jacobbrizinnski/Projects/kitty/.worktrees/daily-driver-model-truth-20260829/.worktree-artifacts/pr672-acceptance/reviewer-evidence'; fs.mkdirSync(OUT,{recursive:true});
async function onboard(p){await p.addInitScript(()=>localStorage.setItem('kitty-onboarded','true'));}
async function navChat(p){const b=p.getByRole('button',{name:/^chat$/i}).first(); await b.click(); await p.waitForTimeout(400);}
async function run(browser,name,viewport){
 const ctx=await browser.newContext({viewport}); const p=await ctx.newPage(); let phase='healthy'; const errs=[]; const completion=[];
 await onboard(p); p.on('pageerror',e=>errs.push({phase,type:'pageerror',text:String(e)})); p.on('console',m=>{if(m.type()==='error') errs.push({phase,type:'console',text:m.text()})}); p.on('request',r=>{if(r.url().includes('/api/chat/completions')) completion.push({phase,url:r.url()})});
 await p.goto('http://127.0.0.1:4198',{waitUntil:'domcontentloaded'}); await p.waitForTimeout(1800); await navChat(p);
 const c=p.locator('textarea').first(); await c.waitFor({state:'visible'}); await p.waitForFunction(()=>{const x=document.querySelector('textarea');return x&&!x.disabled},{timeout:12000});
 const healthyText=await p.locator('body').innerText(); const healthyOverflow=await p.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth); await p.screenshot({path:`${OUT}/${name}-01-healthy.png`,fullPage:true});
 if(!/Daily Kitty|Quick|Think|Code|Vision/.test(healthyText)) throw new Error(`${name}: no curated model labels visible`);
 if(/Qwen3\.5-4B-4bit/.test(healthyText)) throw new Error(`${name}: unavailable local alias leaked`);
 phase='degraded'; await p.route('**/proxy/models/picker',r=>r.fulfill({status:503,contentType:'application/json',body:'{"error":"acceptance injected picker outage"}'})); await p.reload({waitUntil:'domcontentloaded'}); await p.waitForTimeout(1200); await navChat(p);
 await p.waitForFunction(()=>{const x=document.querySelector('textarea');return x&&x.disabled},{timeout:12000});
 const status=p.getByRole('status').filter({hasText:/Model details unavailable|Model details timed out|No live curated models/i}).first(); await status.waitFor({state:'visible',timeout:5000}); const degradedText=(await status.innerText()).replace(/\s+/g,' '); const degradedOverflow=await p.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth); await p.screenshot({path:`${OUT}/${name}-02-degraded.png`,fullPage:true});
 if(/gateway offline/i.test(degradedText)) throw new Error(`${name}: mislabeled picker outage: ${degradedText}`); if(!/Retry to reconnect to Kitty/i.test(degradedText)) throw new Error(`${name}: no recovery copy: ${degradedText}`);
 const send=p.getByRole('button',{name:/send message/i}); if(await send.count() && !(await send.isDisabled())) throw new Error(`${name}: send enabled during picker outage`); if(completion.length) throw new Error(`${name}: completion dispatched during acceptance`);
 phase='recovery'; await p.unroute('**/proxy/models/picker'); await status.getByRole('button',{name:/retry/i}).click(); await p.waitForFunction(()=>{const x=document.querySelector('textarea');return x&&!x.disabled},{timeout:15000}); await p.waitForTimeout(400); const recoveredText=await p.locator('body').innerText(); await p.screenshot({path:`${OUT}/${name}-03-recovered.png`,fullPage:true}); if(!/Daily Kitty|Quick|Think|Code|Vision/.test(recoveredText)) throw new Error(`${name}: curated models did not recover`);
 phase='reload'; await p.reload({waitUntil:'domcontentloaded'}); await p.waitForTimeout(1200); await navChat(p); await p.waitForFunction(()=>{const x=document.querySelector('textarea');return x&&!x.disabled},{timeout:12000}); const reloadOverflow=await p.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth); await p.screenshot({path:`${OUT}/${name}-04-reload.png`,fullPage:true});
 phase='direct';
 await p.route('**/proxy/api/providers',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({active:'openrouter',order:['openrouter'],warnings:[],config_path:'acceptance',providers:[{name:'openrouter',configured:true,disabled:false}]})}));
 await p.route('**/proxy/api/models',r=>r.fulfill({status:503,contentType:'application/json',body:'{"error":"acceptance injected LiteLLM outage"}'}));
 await p.route('**/proxy/runtime/manifest**',r=>r.fulfill({status:503,contentType:'application/json',body:'{"error":"acceptance injected runtime inference outage"}'}));
 await p.reload({waitUntil:'domcontentloaded'}); await p.waitForTimeout(1200); await navChat(p); await p.waitForFunction(()=>{const x=document.querySelector('textarea');return x&&!x.disabled},{timeout:12000});
 const directText=await p.locator('body').innerText(); const directOverflow=await p.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth); await p.screenshot({path:`${OUT}/${name}-05-direct-provider.png`,fullPage:true});
 if(!/Daily Kitty/.test(directText)) throw new Error(`${name}: direct-provider recovery did not expose Daily Kitty`);
 if(/models temporarily unavailable|Model details unavailable|No live curated models/i.test(directText)) throw new Error(`${name}: direct-provider recovery still reported models unavailable`);
 if(completion.length) throw new Error(`${name}: completion dispatched during direct-provider acceptance`);
 await p.unroute('**/proxy/api/providers'); await p.unroute('**/proxy/api/models'); await p.unroute('**/proxy/runtime/manifest**');
 phase='disabled-direct';
 await p.route('**/proxy/api/providers',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({active:'agentrouter',order:[],warnings:['selected provider is disabled by environment'],config_path:'acceptance',providers:[{name:'agentrouter',configured:true,disabled:true}]})}));
 await p.route('**/proxy/api/models',r=>r.fulfill({status:503,contentType:'application/json',body:'{\"error\":\"acceptance injected LiteLLM outage\"}'}));
 await p.route('**/proxy/runtime/manifest**',r=>r.fulfill({status:503,contentType:'application/json',body:'{\"error\":\"acceptance injected runtime inference outage\"}'}));
 await p.reload({waitUntil:'domcontentloaded'}); await p.waitForTimeout(1200); await navChat(p); await p.waitForFunction(()=>{const x=document.querySelector('textarea');return x&&x.disabled},{timeout:12000});
 const disabledDirectText=await p.locator('body').innerText(); const disabledDirectOverflow=await p.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth); await p.screenshot({path:`${OUT}/${name}-06-disabled-direct-provider.png`,fullPage:true});
 if(!/Model details unavailable|models temporarily unavailable|No live curated models/i.test(disabledDirectText)) throw new Error(`${name}: disabled direct provider did not leave models unavailable`);
 if(completion.length) throw new Error(`${name}: completion dispatched during disabled-provider acceptance`);
 await p.unroute('**/proxy/api/providers'); await p.unroute('**/proxy/api/models'); await p.unroute('**/proxy/runtime/manifest**');
 const unexpected=errs.filter(e=>!((e.phase==='degraded'||e.phase==='direct'||e.phase==='disabled-direct') && /503|Failed to load resource/.test(e.text))); const result={sha:'153cafea3758effbd2e7e7c1a3d0777a2bc5a606',name,healthyOverflow,degradedOverflow,reloadOverflow,directOverflow,disabledDirectOverflow,degradedText,completionRequests:completion.length,unexpectedErrors:unexpected,allErrors:errs}; fs.writeFileSync(`${OUT}/${name}.json`,JSON.stringify(result,null,2)); console.log(JSON.stringify({...result,allErrors:undefined})); await ctx.close();
}
(async()=>{const b=await chromium.launch({headless:true}); await run(b,'desktop',{width:1440,height:900}); await run(b,'iphone',{width:393,height:852}); await b.close();})().catch(e=>{console.error(e);process.exit(1)});
