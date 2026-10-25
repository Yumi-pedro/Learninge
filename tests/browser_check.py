"""Run against python3 server.py. Model responses are fixtures, not actual AI validation."""
import json
import os
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)))
    page.goto('http://localhost:8080')
    page.evaluate("localStorage.setItem('betterEnglish_words', JSON.stringify([{word:'existing',meaning:'旧词',example:'An existing example.',status:'学习中',level:1}]));localStorage.setItem('betterEnglish_sessions',JSON.stringify([{topic:'Old topic',text:'Old answer.',date:'昨天',words:2}]))")
    page.reload()
    for name in ['vocabulary', 'review', 'speaking', 'progress', 'home']:
        page.locator(f'.sidebar [data-page="{name}"]').click()
        expect(page.locator(f'#page-{name}')).to_be_visible()
    page.locator('.sidebar [data-page="speaking"]').click()
    answer = page.locator('#speakingAnswer')
    answer.fill('I enjoy walking in the park.')
    page.locator('#getFeedback').click()
    expect(page.locator('#analysisStatusText')).to_contain_text('无法连接本机 Ollama')
    expect(page.locator('#analysisEngineTag')).to_have_text('AI 分析未完成')
    expect(answer).to_have_value('I enjoy walking in the park.')

    def respond(route):
        text = route.request.post_data_json['text']
        walking = 'walking' in text
        result = {'engine': '本机 Ollama AI', 'model': 'test-fixture', 'summary': '描述散步很清楚。' if walking else '描述学习技能很清楚。',
                  'issues': [], 'referenceAnswer': text,
                  'recommendations': [{'phrase': 'go for a walk' if walking else 'pick up a skill', 'meaning': '去散步' if walking else '学会一项技能',
                                       'example': 'I go for a walk after dinner.' if walking else 'I want to pick up a new skill.', 'usage': '描述日常生活。'}],
                  'retryTask': '用推荐表达再说一次。'}
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result))
    page.route('**/api/analyze', respond)
    page.locator('#retryAnalysis').click()
    expect(page.locator('#speakReference')).to_be_visible()
    expect(answer).to_have_value('I enjoy walking in the park.')
    page.locator('[data-add-rec="0"]').click()
    expect(page.locator('[data-add-rec="0"]')).to_be_disabled()
    assert page.evaluate("JSON.parse(localStorage.getItem('betterEnglish_words')).length") == 2
    page.evaluate('addRecommendationToVocabulary(0)')
    assert page.evaluate("JSON.parse(localStorage.getItem('betterEnglish_words')).length") == 2
    page.locator('#startRetry').click()
    expect(answer).to_have_value('')
    expect(page.locator('#speakingHistory')).to_contain_text('I enjoy walking in the park.')
    expect(page.locator('#speakingHistory details')).to_contain_text('描述散步很清楚。')
    answer.fill('I want to learn painting.')
    expect(page.locator('#speakingAnalysisPanel')).not_to_be_visible()
    page.locator('#getFeedback').click()
    expect(page.locator('#speakingAnalysisBody')).to_contain_text('pick up a skill')
    expect(page.locator('#speakingAnalysisBody')).not_to_contain_text('go for a walk')
    # Force storage failure: no false success and no in-memory insertion.
    page.evaluate("() => {window.originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new DOMException('Storage full','QuotaExceededError')}}")
    page.locator('[data-add-rec="0"]').click()
    expect(page.locator('#toast')).to_contain_text('保存失败')
    assert page.evaluate('words.length') == 2
    page.evaluate('() => {Storage.prototype.setItem=window.originalSetItem}')
    # Editing cancels an in-flight response and immediately hides old feedback.
    page.unroute('**/api/analyze')
    page.route('**/api/analyze', lambda route: route.fulfill(status=502,content_type='application/json',body='{"error":"模型返回格式错误，请重新分析。"}'))
    answer.fill('Another answer.')
    page.locator('#getFeedback').click()
    expect(page.locator('#analysisStatusText')).to_contain_text('模型返回格式错误')
    page.reload()
    page.locator('.sidebar [data-page="vocabulary"]').click()
    expect(page.locator('#vocabRows')).to_contain_text('existing')
    expect(page.locator('#vocabRows')).to_contain_text('go for a walk')
    page.locator('.sidebar [data-page="review"]').click()
    expect(page.locator('#reviewWord')).to_have_text('go for a walk')
    page.locator('#revealAnswer').click()
    expect(page.locator('#reviewAnswer')).to_contain_text('去散步')
    page.locator('[data-grade="known"]').click()
    assert page.evaluate("JSON.parse(localStorage.getItem('betterEnglish_words'))[0].level") == 1
    # Repeated final recognition results do not duplicate; interim tail is retained.
    text = page.evaluate('''() => {
      speechCyclePrefix='';speechFinalText='';speechInterimText='';speechPrefixAtStart='';
      const result=(t,f)=>{const r=[{transcript:t}];r.isFinal=f;return r};
      const e={results:[result('I enjoy walking.',true),result('It helps me relax.',false)],resultIndex:0};
      handleSpeechResult(e);handleSpeechResult(e);finalizeSpeechSession();return $('speakingAnswer').value;
    }''')
    assert text == 'I enjoy walking. It helps me relax.', text
    page.locator('.sidebar [data-page="speaking"]').click()
    held = []
    page.unroute('**/api/analyze')
    page.route('**/api/analyze', lambda route: held.append(route))
    answer.fill('The previous answer.')
    page.locator('#getFeedback').click()
    page.wait_for_timeout(100)
    assert held
    answer.fill('This is my corrected answer.')
    held[0].fulfill(status=200,content_type='application/json',body=json.dumps({'engine':'本机 Ollama AI','summary':'过期反馈','referenceAnswer':'Old.','issues':[],'recommendations':[],'retryTask':'Old'}))
    page.wait_for_timeout(100)
    expect(page.locator('#speakingAnalysisPanel')).not_to_be_visible()
    expect(answer).to_have_value('This is my corrected answer.')
    page.evaluate('clearTimeout(analysisDebounce)')
    # Simulated local voice checks cancellation and stop behavior, not audible output.
    page.evaluate("""() => {window.ttsCalls=[];window.SpeechSynthesisUtterance=class{constructor(text){this.text=text}};Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{getVoices:()=>[{lang:'en-US',localService:true}],cancel:()=>ttsCalls.push('cancel'),speak:u=>ttsCalls.push(u.text)}})}""")
    page.evaluate("() => {speakText('First.');speakText('Second.');$('stopSpeech').click()}")
    assert page.evaluate('ttsCalls') == ['cancel','First.','cancel','Second.','cancel']
    assert not errors, errors
    browser.close()
    print('PASS: five pages; unavailable/model-format errors; original retained; fixture feedback; save/deduplicate/storage failure; history; refresh; review; speech result deduplication and tail.')
    print('NOTE: model fixtures do not validate actual language quality; microphone and audio require Mac testing.')
