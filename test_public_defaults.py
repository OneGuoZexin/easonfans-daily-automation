import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from easonfans_daily import Bot


class PublicDefaultsTests(unittest.IsolatedAsyncioTestCase):
    async def test_messages_disabled_without_visiting_profiles(self):
        bot = Bot.__new__(Bot)
        bot.config = {'message_count': 0}
        bot.log = Mock()
        bot.collect_uids_from_source_wall_pages = AsyncMock()
        bot.leave_one_message = AsyncMock()
        await bot.leave_wall_messages(Mock())
        bot.collect_uids_from_source_wall_pages.assert_not_awaited()
        bot.leave_one_message.assert_not_awaited()

    def test_example_contains_no_real_uid_and_disables_messages(self):
        config = json.loads(Path('config.example.json').read_text(encoding='utf-8'))
        self.assertIn('YOUR_UID', config['wall_url'])
        self.assertEqual(config['message_count'], 0)
