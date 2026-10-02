"""Offline regression tests: no website access or real messages."""
import unittest
from unittest.mock import AsyncMock, Mock, patch

from easonfans_daily import Bot


class QuizFlowTests(unittest.IsolatedAsyncioTestCase):
    def make_bot(self):
        bot = Bot.__new__(Bot)
        bot.config = {'profile_dir': 'unused-test-profile'}
        bot.quiz_url = 'https://fixture.invalid/quiz'
        bot.log = Mock()
        bot.screenshot = AsyncMock()
        bot.ensure_login = AsyncMock(return_value=True)
        bot.sign_in = AsyncMock()
        bot.lucky_wheel = AsyncMock()
        bot.leave_wall_messages = AsyncMock()
        bot.extract_quiz_question = AsyncMock(return_value='题库里没有的问题？')
        bot.select_quiz_answer = AsyncMock(return_value=False)
        return bot

    async def run_offline(self, bot):
        page = Mock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        form = Mock()
        form.count = AsyncMock(return_value=1)
        form.click = AsyncMock()
        page.locator.return_value = form
        browser = Mock()
        browser.pages = [page]
        browser.close = AsyncMock()
        runtime = Mock()
        runtime.chromium.launch_persistent_context = AsyncMock(return_value=browser)
        manager = AsyncMock()
        manager.__aenter__.return_value = runtime
        with patch('easonfans_daily.async_playwright', return_value=manager):
            await bot.run()
        return page, form, browser

    async def test_unknown_answer_continues_to_wall_without_submitting(self):
        bot = self.make_bot()
        try:
            page, form, browser = await self.run_offline(bot)
        except RuntimeError as exc:
            self.fail(f'未知答案不应中断整个流程: {exc}')
        bot.leave_wall_messages.assert_awaited_once_with(page)
        bot.select_quiz_answer.assert_awaited_once()
        page.goto.assert_awaited_once()  # Stop quiz, do not retry the same question.
        form.click.assert_not_awaited()
        bot.screenshot.assert_awaited_once_with(page, 'quiz-answer-not-found-1')
        browser.close.assert_awaited_once()
        bot.log.assert_any_call('Done')

    async def test_unexpected_quiz_error_is_not_silently_ignored(self):
        bot = self.make_bot()
        bot.select_quiz_answer.side_effect = RuntimeError('unexpected browser failure')
        with self.assertRaisesRegex(RuntimeError, 'unexpected browser failure'):
            await self.run_offline(bot)
        bot.leave_wall_messages.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
