import unittest

from core.matcher import normalize_analysis
from core.workflow import keyword_intent


class WorkflowIntentTests(unittest.TestCase):
    def test_keyword_intent_routes_action(self):
        self.assertEqual(keyword_intent("帮我给张三发送明天下午两点的面试邀约"), "action_tool")

    def test_keyword_intent_routes_resume(self):
        self.assertEqual(keyword_intent("评估一下这份简历和 JD 的匹配度"), "resume")

    def test_keyword_intent_routes_rag(self):
        self.assertEqual(keyword_intent("年假制度是什么？"), "rag")


class MatcherNormalizationTests(unittest.TestCase):
    def test_normalize_analysis_clamps_score_and_lists(self):
        result = normalize_analysis({"score": 120, "pros": "Python 经验", "cons": ["缺少管理经验"]})

        self.assertEqual(result["score"], 100)
        self.assertEqual(result["pros"], ["Python 经验"])
        self.assertEqual(result["cons"], ["缺少管理经验"])


if __name__ == "__main__":
    unittest.main()
