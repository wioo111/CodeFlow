import { existsSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import { chromium } from '../frontend/node_modules/playwright-core/index.mjs'

const base=process.env.CODEFLOW_BASE_URL||'http://127.0.0.1:5173'
const artifactRoot=path.resolve(process.env.CODEFLOW_E2E_ARTIFACT_DIR||'artifacts/e2e-live')
mkdirSync(artifactRoot,{recursive:true})
const chromeCandidates=[process.env.CODEFLOW_CHROME_PATH,path.join(process.env.ProgramFiles||'C:\\Program Files','Google','Chrome','Application','chrome.exe')].filter(Boolean)
const chromePath=chromeCandidates.find(candidate=>existsSync(candidate))
const browser=await chromium.launch({headless:true,...(chromePath?{executablePath:chromePath}:{})})
const page=await browser.newPage({viewport:{width:1600,height:1000}})
const consoleErrors=[];const failedRequests=[]
page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text())})
page.on('requestfailed',request=>failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`))

const projects=await page.request.get(`${base}/api/projects`).then(response=>response.json())
const project=projects.find(item=>item.schema_id==='football_cp_v0.1')
if(!project)throw new Error('Current football project not found')
const versions=await page.request.get(`${base}/api/projects/${project.id}/dataset-versions`).then(response=>response.json())
const dataset=versions.find(item=>item.dataset_version==='Football-Douyin-Communicative-Moment-Benchmark-clean-v0.1')
if(!dataset)throw new Error('Current 250-sample dataset not found')

await page.goto(`${base}/research/project/${project.id}?dataset=${dataset.id}`,{waitUntil:'networkidle'})
await page.getByText('标注任务队列').waitFor()
await page.getByText('250',{exact:true}).first().waitFor()
const visibleRows=await page.locator('tbody tr').count()
await page.screenshot({path:path.join(artifactRoot,'football-250-ai-queue.png'),fullPage:true})

const queuePages=await Promise.all([1,2,3].map(pageNumber=>page.request.get(`${base}/api/projects/${project.id}/samples?dataset_version_id=${dataset.id}&page=${pageNumber}&page_size=100`).then(response=>response.json())))
const target=queuePages.flatMap(result=>result.items).find(item=>item.sample_id==='LLD-v0.1-001363')
if(!target)throw new Error('Calibration sample not found in queue')
await page.goto(`${base}/research/assignment/${target.assignment_id}`,{waitUntil:'networkidle'})
await page.getByText('AI 原始结果（只读）').waitFor()
await page.getByText('不可覆盖 · Run 4').waitFor()
await page.locator('video').waitFor()
await page.waitForFunction(()=>{const video=document.querySelector('video');return video&&video.readyState>=1})
await page.locator('video').evaluate(async video=>{video.muted=true;await video.play();await new Promise(resolve=>setTimeout(resolve,700));video.pause()})
const playedTime=await page.locator('video').evaluate(video=>video.currentTime)
if(playedTime<=0)throw new Error('Video did not advance')
const frameCount=await page.locator('.frame-card').count()
if(frameCount<1)throw new Error('No frames rendered')
await page.locator('.frame-card img').first().waitFor()
await page.screenshot({path:path.join(artifactRoot,'football-ai-calibration-workbench.png'),fullPage:true})

const actionableFailedRequests=failedRequests.filter(item=>!(item.includes('/media/video?')&&item.includes('ERR_ABORTED')))
console.log(JSON.stringify({projectId:project.id,datasetVersionId:dataset.id,assignmentId:target.assignment_id,visibleRows,frameCount,modelRunId:4,playedTime,consoleErrors,actionableFailedRequests,expectedVideoRangeAborts:failedRequests.length-actionableFailedRequests.length},null,2))
await browser.close()
