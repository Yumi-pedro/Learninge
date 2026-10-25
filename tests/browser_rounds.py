"""Round-trip persistence and context checks with explicit model fixtures."""
import json
import os
from playwright.sync_api import sync_playwright, expect

OLD = 'Yesterday I go to the park with my family.'
NEW = 'Yesterday I went to the park with my family.'

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True)
    page = browser.new_page()
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://localhost:8080')
    page.evaluate("localStorage.setItem('betterEnglish_sessions',JSON.stringify([{topic:'Legacy',text:'A legacy answer.',date:'昨天',words:3}]))")
    page.reload()
    page.locator('.sidebar [data-page="speaking"]').click()

    def response(route):
        request = route.request.post_data_json
        requests.append(request)
        previous = request.get('previous')
        result = {'engine': '本机 Ollama AI', 'summary': '你描述了昨天的家庭活动。',
                  'referenceAnswer': NEW, 'retryTask': '不看参考稿，用过去时再说一次。',
                  'issues': [] if request['text'] == NEW else [{'original':'I go','suggestion':'I went',
                    'type':'语法错误','explanation':'yesterday 对应过去时。','correctedSentence':NEW}],
                  'recommendations':[{'phrase':'spend time with family','meaning':'与家人共度时光',
                     'example':'I spent time with my family at the park yesterday.','usage':'描述家庭活动。'}]}
        if previous:
            result['comparison'] = {'summary':'本轮正确使用了过去时；一次使用不代表永久掌握。',
                'changes':[{'before':'I go','after':'I went','status':'已改善','explanation':'go 已改为表示过去的 went。'}]}
        route.fulfill(status=200,content_type='application/json',body=json.dumps(result))

    page.route('**/api/analyze', response)
    answer = page.locator('#speakingAnswer')
    answer.fill(OLD)
    page.locator('#getFeedback').click()
    expect(page.locator('#analysisEngineTag')).to_have_text('本机 Ollama AI')
    page.locator('#startRetry').click()
    expect(answer).to_have_value('')
    expect(page.locator('#retryContextPanel')).to_be_visible()
    assert requests[0]['previous'] is None
    page.reload()
    page.locator('.sidebar [data-page="speaking"]').click()
    expect(page.locator('#retryContextPanel')).to_contain_text(OLD)
    answer.fill(NEW)
    page.locator('#getFeedback').click()
    expect(page.locator('.round-comparison')).to_contain_text('已改善')
    expect(answer).to_have_value(NEW)
    assert requests[-1]['previous']['text'] == OLD
    assert requests[-1]['previous']['issues'][0]['original'] == 'I go'
    assert requests[-1]['previous']['phrases'] == ['spend time with family']
    page.locator('#saveSpeaking').click()
    page.reload()
    page.locator('.sidebar [data-page="speaking"]').click()
    expect(page.locator('#speakingHistory')).to_contain_text('A legacy answer.')
    expect(page.locator('#speakingHistory .round-comparison')).to_contain_text(OLD)
    expect(page.locator('#speakingHistory .round-comparison')).to_contain_text(NEW)
    page.locator('#newTopic').click()
    expect(page.locator('#retryContextPanel')).not_to_be_visible()
    assert page.evaluate("JSON.parse(localStorage.getItem('betterEnglish_retryContext'))") is None
    answer.fill(NEW)
    page.locator('#getFeedback').click()
    expect(page.locator('#analysisEngineTag')).to_have_text('本机 Ollama AI')
    assert requests[-1]['previous'] is None
    expect(page.locator('#speakingAnalysisBody .round-comparison')).to_have_count(0)
    # A failure writing retry state leaves the answer intact; saved history remains recoverable.
    page.evaluate("() => {window.originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='betterEnglish_retryContext')throw new DOMException('Storage full','QuotaExceededError');return originalSetItem.call(this,k,v)}}")
    page.locator('#startRetry').click()
    expect(page.locator('#toast')).to_contain_text('无法建立对照')
    expect(answer).to_have_value(NEW)
    page.evaluate('() => {Storage.prototype.setItem=window.originalSetItem}')
    page.locator('#startRetry').click()
    page.unroute('**/api/analyze')
    page.route('**/api/analyze', lambda route: route.fulfill(status=200,content_type='application/json',body=json.dumps(
        {'summary':'旧服务结果','referenceAnswer':NEW,'issues':[],'recommendations':[],'retryTask':'再说一次。'})))
    answer.fill(NEW)
    page.locator('#getFeedback').click()
    expect(page.locator('#analysisStatusText')).to_contain_text('server.py 已更新')
    expect(answer).to_have_value(NEW)
    assert not errors, errors
    browser.close()
    print('PASS: previous context sent separately; two-round evidence shown; legacy history retained; refresh restores context/comparison; topic clears context; storage failure preserves answer; old backend gives upgrade guidance. Model responses are fixtures.')
