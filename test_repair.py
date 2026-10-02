import unittest
import quiz_tools as q


class QuizTests(unittest.TestCase):
    def test_number_formats(self):
        self.assertEqual(q.normalize('第 2 个'), q.normalize('第二个'))
        self.assertEqual(q.normalize('第十四届'), q.normalize('第14届'))
        self.assertEqual(q.normalize('一百零二场'), q.normalize('102场'))
        self.assertNotEqual(q.normalize('十年'), q.normalize('十面埋伏'))

    def test_import_multiline_and_correction(self):
        rows, issues = q.parse_bank('一、测试\n1.生日是？—1974-07-27\n2.洗澡顺序？\n3.—洗头→洗脸\n4.首作？—选了游离分子是错的/正确答案是我的理想！')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]['answer'], '洗头→洗脸')
        self.assertEqual(rows[2]['answer'], '我的理想')

    def test_parenthetical_question_continues(self):
        rows, issues = q.parse_bank('33.冲凉次序係？（洗澡的顺序是？）\n34.—洗头→洗脸')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['answer'], '洗头→洗脸')
        self.assertEqual(issues, [])

    def test_word_soft_linebreak_answer(self):
        rows, issues = q.parse_bank('29.你最想和哪位网球运动员搭档打双打？\v答：张德培')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['answer'], '张德培')
        rows, issues = q.parse_bank('1.最喜欢什么运动?/最喜欢的运动是什么？\v答：网球')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['answer'], '网球')

    def test_sign_status_ignores_other_people(self):
        self.assertFalse(q.signed_today('排行榜：张三 今天已签到\n【今天未签到】\n2031人 今日已签到'))
        self.assertTrue(q.signed_today('排行榜：张三 今天已签到\n【今天已签到】'))

    def test_conflicts_and_unparseable_are_reported(self):
        rows, issues = q.parse_bank('1.纹身？—七\n2.纹身？—小姐选美\n3.散乱备注')
        self.assertTrue(any(x['kind'] == 'conflict' for x in issues))
        self.assertTrue(any(x['kind'] == 'unparsed' for x in issues))
        self.assertIsNone(q.choose_option('纹身？', ['七', '小姐选美'], rows))

    def test_options(self):
        bank = [{'question': '他是第几个歌手？', 'answer': '第 2个'}]
        self.assertEqual(q.choose_option('他是第几个歌手？', ['第四个','第三个','第二个','第一个'], bank), 2)
        self.assertIsNone(q.choose_option('他是第几个歌手？', ['', '第十二个'], bank))
        self.assertIsNone(q.choose_option('哪个不是歌手？', ['第二个'], bank))

    def test_no_fallback_to_wrong_question(self):
        bank = [{'question': '生日？', 'answer': '7月27日'}, {'question': '生日是哪一天？', 'answer': '8月1日'}]
        self.assertIsNone(q.choose_option('生日？', ['8月1日'], bank))

    def test_negative_and_numeric_distinctions(self):
        bank = [{'question': '他没有在哪家公司？', 'answer': '华纳'}]
        self.assertIsNone(q.choose_option('他在哪家公司？', ['华纳'], bank))
        self.assertIsNone(q.choose_option('哪一年？', ['12006年'], [{'question':'哪一年？', 'answer':'2006'}]))


if __name__ == '__main__':
    unittest.main()
