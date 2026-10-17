// Presentation & accessibility regression checks for FE-01/FE-02 (Natal's lane).
// Synthetic demo data only; no patient content. Mirrors tests/browser.cjs: it
// needs Playwright + Chromium and the static server running. It is intentionally
// NOT named *.test.js, so `npm test` (node --test tests/*.test.js) does not run
// it and it stays out of the deploy allowlist. Run it manually:
//   npm --prefix frontend run build   # optional, serves source directly otherwise
//   (serve the repo root, e.g. `npm --prefix frontend start`)
//   node frontend/tests/presentation-browser.cjs
// Honors PLAYWRIGHT_MODULE, CHROMIUM_PATH and FRONTEND_URL like the other
// browser tests.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const URL=process.env.FRONTEND_URL || 'http://127.0.0.1:4173/frontend/';
const noOverflow=page=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth);
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(URL);
 // Regression: below 520px the sidebar was display:none, hiding every nav link.
 // The mobile nav bar must stay present and its items reachable.
 assert.notEqual(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).display),'none','sidebar is hidden below 520px');
 for(const sel of ['#nav-intake','#nav-guide']) await page.locator(sel).waitFor({state:'visible'});
 await page.locator('a.nav-item[href="./team/"]').waitFor({state:'visible'});
 // Decorative glyphs are hidden from assistive technology.
 assert.equal(await page.locator('#nav-guide span[aria-hidden="true"]').count(),1,'nav icon glyph is not aria-hidden');
 assert.ok(await noOverflow(page),'horizontal overflow on intake at 390px');
 await page.locator('#demo').click();
 await page.getByText('Make the evidence clear.').waitFor();
 assert.ok(await noOverflow(page),'horizontal overflow on review at 390px');
 // Source/field review must stay reachable and overflow-free on a phone width.
 await page.locator('#fields-view').click();
 await page.getByRole('heading',{name:'Source evidence'}).waitFor();
 assert.ok(await noOverflow(page),'horizontal overflow on field review at 390px');
 // WCAG 1.4.10 reflow: usable at a 320px CSS width with no 2D scrolling.
 await page.setViewportSize({width:320,height:800});
 assert.ok(await noOverflow(page),'horizontal overflow at 320px');
 // Keyboard: focus reaches a nav item and shows a visible outline.
 await page.setViewportSize({width:390,height:844});
 await page.goto(URL);
 await page.locator('#demo').waitFor();
 let focus=null;
 for(let i=0;i<8;i++){
  await page.keyboard.press('Tab');
  focus=await page.evaluate(()=>{const a=document.activeElement,cs=getComputedStyle(a);return{isNav:!!(a.classList&&a.classList.contains('nav-item')),id:a.id,outlineWidth:cs.outlineWidth};});
  if(focus.isNav)break;
 }
 assert.ok(focus&&focus.isNav,'keyboard focus never reached a nav item');
 assert.notEqual(focus.outlineWidth,'0px','focus outline is missing on the focused nav item');
 assert.deepEqual(errors,[]);
 console.log('PASS: mobile nav present <520px, aria-hidden glyphs, no overflow at 390/320px, source review reachable on mobile, keyboard focus visible, no JS errors.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
