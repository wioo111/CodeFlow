import { existsSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '../frontend/node_modules/playwright-core/index.mjs'

const repositoryRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const base=process.env.CODEFLOW_BASE_URL||'http://127.0.0.1:5173'
const artifactRoot=path.resolve(process.env.CODEFLOW_E2E_ARTIFACT_DIR||path.join(repositoryRoot,'artifacts','e2e'))
mkdirSync(artifactRoot,{recursive:true})
const chromeCandidates=[process.env.CODEFLOW_CHROME_PATH,path.join(process.env.ProgramFiles||'C:\\Program Files','Google','Chrome','Application','chrome.exe')].filter(Boolean)
const chromePath=chromeCandidates.find(candidate=>existsSync(candidate))
const browser=await chromium.launch({headless:true,...(chromePath?{executablePath:chromePath}:{})})
const context=await browser.newContext({viewport:{width:1600,height:1000}})
const page=await context.newPage()
await page.route('**/api/**',route=>route.continue({headers:{...route.request().headers(),'X-User-ID':'scale_coder_01','X-User-Role':'coder'}}))
const consoleErrors=[];const failedRequests=[]
page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text())})
page.on('requestfailed',request=>failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`))

const projects=await page.request.get(`${base}/api/projects`).then(response=>response.json())
const project=projects.find(item=>item.schema_id==='codeflow_scale_250')
if(!project)throw new Error('请先运行 generate_scale_fixture.py 并导入生成的数据包')
const versions=await page.request.get(`${base}/api/projects/${project.id}/dataset-versions`).then(response=>response.json())
const started=performance.now()
await page.goto(`${base}/research/project/${project.id}?dataset=${versions[0].id}`,{waitUntil:'networkidle'})
await page.getByText('标注任务队列').waitFor()
await page.getByText('250',{exact:true}).first().waitFor()
const loadMs=Math.round(performance.now()-started)
const visibleRows=await page.locator('tbody tr').count()
if(visibleRows!==25)throw new Error(`Expected 25 visible rows, got ${visibleRows}`)
await page.screenshot({path:path.join(artifactRoot,'codeflow-scale-250-queue.png'),fullPage:true})
console.log(JSON.stringify({projectId:project.id,datasetVersionId:versions[0].id,loadMs,visibleRows,consoleErrors,failedRequests},null,2))
await browser.close()
