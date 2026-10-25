"""Real local-model smoke checks. Synthetic text only; no files or learner data are read."""
import json
import urllib.error
import urllib.request

client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
base = 'http://localhost:8080'

def call(path, body=None):
    request = urllib.request.Request(base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        with client.open(request, timeout=200) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            message = json.load(exc).get('error', str(exc))
        except ValueError:
            message = str(exc)
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError('本地网站服务未启动，尚未执行真实模型测试。') from exc


def main():
    try:
        health = call('/api/health')
        if not health.get('installed'):
            raise RuntimeError('目标模型尚未安装；测试不会自动下载模型。')
        cases = [
            ('过去时', 'Describe what you did yesterday.', 'Yesterday I go to the park with my family.'),
            ('正确表达', 'Describe a hobby.', 'I enjoy cooking for my family because it helps me relax.'),
            ('不同语境', 'Talk about a skill you want to learn.', 'I want to learn photography so I can take better pictures on holiday.'),
        ]
        results = []
        for label, topic, text in cases:
            result = call('/api/analyze', {'text': text, 'topic': topic})
            for issue in result['issues']:
                if issue['original'] not in text:
                    raise RuntimeError('模型引用了不存在的片段。')
            if label == '过去时' and not any('went' in x['suggestion'].lower() for x in result['issues']):
                raise RuntimeError('过去时测试未给出预期的 went 修改，需要检查模型反馈质量。')
            if label == '正确表达' and any(x['type'] in ['语法错误', '搭配问题'] for x in result['issues']):
                raise RuntimeError('模型可能把正确表达判成错误，需要人工复核。')
            results.append(result)
            print(label + '：已返回结构化反馈。')
            print(json.dumps(result, ensure_ascii=False, indent=2))
        earlier = results[0]
        previous = {'text': cases[0][2],
                    'issues': [{k: x[k] for k in ['type', 'original', 'suggestion']} for x in earlier['issues']],
                    'phrases': [x['phrase'] for x in earlier['recommendations']]}
        result = call('/api/analyze', {'text': 'Yesterday I went to the park with my family.',
                                      'topic': cases[0][1], 'previous': previous})
        if not result.get('comparison'):
            raise RuntimeError('没有返回两轮对照，需检查服务版本。')
        print('两轮对照：' + json.dumps(result['comparison'], ensure_ascii=False, indent=2))
        print('本地模型结构与有限语义检查完成。例句自然度、保留原意及对照解释仍需人工阅读上述实际反馈。')
    except (RuntimeError, TimeoutError, ValueError, KeyError, TypeError) as exc:
        print('未通过：' + str(exc))
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
