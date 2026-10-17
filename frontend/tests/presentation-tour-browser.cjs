const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4176/');await page.click('#start-presentation');
const speakers=['Neetal','Aaron','Aaron','Aaron','Vibhu','Vibhu','Harjeev','Harjeev'];
for(let i=0;i<speakers.length;i++){
 assert.ok((await page.locator('.presentation-speaker').textContent()).startsWith(speakers[i]));
 await page.waitForFunction(()=>document.querySelector('.presentation-highlight'));
 assert.equal(await page.locator('.presentation-highlight').count(),1);
 assert.ok(await page.locator('.presentation-script').isVisible());
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
 if(i===3){assert.match(await page.locator('main').textContent(),/not verified current prices/);assert.match(await page.locator('main').textContent(),/No automatic clinical admission/);assert.match(await page.locator('main').textContent(),/not predictions or observed outcomes/);}
 if(i===2)assert.ok(await page.locator('.review-grid').isVisible());
 if(i===5)assert.ok(await page.locator('.onboarding-panel').isVisible());
 if(i===7)assert.match(await page.locator('main').textContent(),/Before real use/);
 await page.click('#presentation-next');
}
assert.equal(await page.locator('#presentation-notes').count(),0);assert.equal(await page.evaluate(()=>document.activeElement.id),'start-presentation');assert.match(await page.locator('main h1').textContent(),/Referral inbox/);
// Exit restores selected local PDF rather than replacing it with the synthetic review.
await page.click('#nav-intake');await page.setInputFiles('#file-input','frontend/fixtures/synthetic-training/Careward-Synthetic-Referral-Packet.pdf');await page.locator('#pdf-preview canvas').waitFor();await page.click('#start-presentation');await page.keyboard.press('ArrowRight');assert.match(await page.locator('.presentation-speaker').textContent(),/Aaron/);await page.keyboard.press('ArrowLeft');assert.match(await page.locator('.presentation-speaker').textContent(),/Neetal/);await page.keyboard.press('Escape');await page.locator('#pdf-preview canvas').waitFor();assert.match(await page.locator('main').textContent(),/Careward-Synthetic-Referral-Packet.pdf/);
await page.setViewportSize({width:390,height:844});await page.click('#start-presentation');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.locator('#presentation-next').scrollIntoViewIfNeeded();assert.ok(await page.locator('#presentation-next').isVisible());await page.keyboard.press('Escape');assert.deepEqual(errors,[]);await browser.close();console.log('PASS eight speaker sections, spotlight targets, keyboard navigation, mobile notes, exit restoration and PDF preservation.');})().catch(e=>{console.error(e);process.exit(1)});
