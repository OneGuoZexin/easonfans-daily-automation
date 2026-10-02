import unittest
from unittest.mock import Mock
from playwright.async_api import async_playwright
from easonfans_daily import Bot


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_hidden_logout_and_numeric_option(self):
        bot = Bot.__new__(Bot)
        bot.config = {}
        bot.log = Mock()
        bot.base_url = 'https://fixture.test/'
        bot.quiz_bank = [{'question':'他是第几个歌手？', 'answer':'第 2 个'}]
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.route('**/*', lambda route: route.fulfill(
                    content_type='text/html', body='''<meta charset="utf-8">
                    <a style="display:none" href="member.php?action=logout">退出</a>
                    <form id="myform"><div>【题目】他是第几个歌手？</div>
                    <label class="qs_option"><input type="radio" name="answer" value="1">第一个</label>
                    <label class="qs_option"><input type="radio" name="answer" value="2">第二个</label>
                    <label class="qs_option"><input type="radio" name="answer" value="12">第十二个</label>
                    </form>'''))
                self.assertTrue(await bot.ensure_login(page, wait=False))
                question = await bot.extract_quiz_question(page)
                self.assertTrue(await bot.select_quiz_answer(page, question))
                self.assertEqual(await page.locator('input:checked').input_value(), '2')
            finally:
                await browser.close()


if __name__ == '__main__':
    unittest.main()
