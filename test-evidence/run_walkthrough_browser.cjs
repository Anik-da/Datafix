const puppeteer = require('C:/Users/anikd/node_modules/puppeteer-core');
(async()=>{
 const browser=await puppeteer.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--no-sandbox'],defaultViewport:{width:1400,height:1000}});
 const page=await browser.newPage();const errors=[];page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/#/walkthrough',{waitUntil:'networkidle2',timeout:30000});
 console.log('initial title',await page.title(),'cta',await page.$$eval('[data-testid="live-sample-analysis-cta"]', els=>els.length));
 await page.screenshot({path:'test-evidence/walkthrough-before-live.png',fullPage:false});
 await page.$eval('[data-testid="live-sample-analysis-cta"]', e=>e.click());
 await page.waitForFunction(()=>location.hash.includes('/runs/')&&location.hash.includes('/overview'),{timeout:60000});
 await new Promise(r=>setTimeout(r,1500));
 console.log('final url',page.url());console.log('body excerpt',(await page.$eval('body', e=>e.innerText)).slice(0,5000));console.log('console errors',JSON.stringify(errors));
 await page.screenshot({path:'test-evidence/walkthrough-live-run.png',fullPage:true});
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
