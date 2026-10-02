import argparse
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from quiz_tools import parse_bank, choose_option, signed_today


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def load_json(path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



def normalize(text):
    text = re.sub(r"[\s\xa0]+", "", text or "")
    text = text.lower()
    punctuation = (
        "\u300a\u300b\u300c\u300d\u201c\u201d\"'\uff0c,\u3002.:"
        "\uff1a\uff1f?\uff01!\uff08\uff09()\[\]\u3010\u3011\-_/`~"
    )
    return re.sub(f"[{punctuation}]", "", text)


def score_match(page_question, bank_question):
    a = normalize(page_question)
    b = normalize(bank_question)
    if not a or not b:
        return 0
    if a == b:
        return 10000 + len(a)
    if a in b or b in a:
        return min(len(a), len(b)) + 1000
    shared = set(a) & set(b)
    return int(100 * len(shared) / max(len(set(a)), 1))

def extract_uid(url):
    match = re.search(r"[?&]uid=(\d+)", url)
    return match.group(1) if match else ""


class Bot:
    def __init__(self, config):
        self.config = config
        self.base_url = config["base_url"].rstrip("/") + "/"
        self.sign_url = self.base_url + "plugin.php?id=dsu_paulsign:sign"
        self.wheel_url = self.base_url + "plugin.php?id=gplayconstellation:front"
        self.quiz_url = self.base_url + "plugin.php?id=ahome_dayquestion:index"
        self.source_wall_url = config["wall_url"]
        self.self_uid = extract_uid(self.source_wall_url)
        self.log_dir = ROOT / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"run-{datetime.now():%Y%m%d-%H%M%S}.log"
        self.quiz_bank = load_json(ROOT / config["quiz_bank"], [])
        source = ROOT / '题库.txt'
        if source.exists():
            self.quiz_bank, issues = parse_bank(source.read_text(encoding='utf-8-sig'))
            if not self.quiz_bank:
                raise ValueError('题库.txt 没有可读取的题目，请检查格式。')
            write_json(ROOT / config['quiz_bank'], self.quiz_bank)
            write_json(ROOT / '题库导入报告.json', {'count': len(self.quiz_bank), 'issues': issues})
        if not self.quiz_bank:
            raise ValueError('题库缺失，请将题库.txt 放到程序目录。')
        self.state_path = ROOT / config["state_file"]
        self.state = load_json(self.state_path, {"visited_uids": []})

    def log(self, message):
        line = f"[{datetime.now():%H:%M:%S}] {message}"
        print(line)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def screenshot(self, page, name):
        path = self.log_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{name}.png"
        await page.screenshot(path=str(path), full_page=True)
        self.log(f"Screenshot saved: {path}")

    async def sign_in(self, page):
        self.log("Step 1: sign in")
        await page.goto(self.sign_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        body = await page.locator("body").inner_text()
        if signed_today(body):
            self.log("Already signed in today")
            return

        if await page.locator("#qiandao").count() == 0:
            await self.screenshot(page, "sign-form-missing")
            raise RuntimeError('未找到签到表单，也未确认已签到，请查看截图。')

        mood_ids = ["kx", "ng", "ym", "wl", "nu", "ch", "fd", "yl", "shuai"]
        mood_index = min(int(self.config.get("emoji_index", 0)), len(mood_ids) - 1)
        mood_id = mood_ids[mood_index]
        try:
            await page.locator(f"#{mood_id}").click(timeout=5000)
        except PlaywrightTimeoutError:
            await page.locator(f"#{mood_id}_s").check(force=True)

        mode = page.locator("#qiandao input[name='qdmode'][value='3']")
        if await mode.count():
            await mode.check(force=True)

        try:
            await page.evaluate("showWindow('qwindow', 'qiandao', 'post', '0')")
            await page.wait_for_timeout(2500)
        except Exception:
            await self.screenshot(page, "sign-submit-failed")
            raise

        await page.goto(self.sign_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1200)
        after = await page.locator("body").inner_text()
        if not signed_today(after):
            await self.screenshot(page, "sign-still-not-signed")
            raise RuntimeError('签到提交后未确认成功，请查看截图。')
        else:
            self.log("Sign in completed")

    async def lucky_wheel(self, page):
        self.log("Step 2: lucky wheel")
        await page.goto(self.wheel_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        body = await page.locator("body").inner_text()
        if "今日剩余免费次数：0" in body:
            self.log("Lucky wheel already used today")
            return
        try:
            await page.locator("#pointlevel").click(timeout=5000)
            await page.wait_for_timeout(8000)
            self.log("Clicked wheel control: #pointlevel")
            return
        except PlaywrightTimeoutError:
            pass
        await self.screenshot(page, "wheel-control-missing")

    async def answer_quiz(self, page):
        self.log("Step 3: quiz")
        for idx in range(3):
            await page.goto(self.quiz_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            if await page.locator("#myform").count() == 0:
                self.log("No quiz form; quiz is probably complete today")
                return
            question = await self.extract_quiz_question(page)
            if not question:
                self.log("No question found")
                await self.screenshot(page, f"quiz-no-question-{idx + 1}")
                return
            self.log(f"Question {idx + 1}: {question}")
            if not await self.select_quiz_answer(page, question):
                await self.screenshot(page, f"quiz-answer-not-found-{idx + 1}")
                self.log('题目或选项无法唯一匹配，未提交答案；结束本次答题，继续后续留言任务。')
                return
            await page.locator("#myform button[type='submit']").click(timeout=5000)
            await page.wait_for_timeout(4500)

    async def extract_quiz_question(self, page):
        text = await page.locator("#myform").evaluate("el => el.innerText")
        text = text.replace("\xa0", " ")
        match = re.search(r"\u3010\u9898\u76ee\u3011\s*(.+?)(?:\n|$)", text)
        if match:
            line = match.group(1).strip()
        else:
            line = next((x.strip() for x in text.splitlines() if "\uff1f" in x or "?" in x), "")
        # Some browsers expose option text on the same line. Trim at the first option-like double space.
        return re.split(r"\s{2,}", line)[0].strip()

    def find_answer_candidates(self, question):
        if not self.quiz_bank:
            return []
        scored = []
        for item in self.quiz_bank:
            score = score_match(question, item.get("question", ""))
            if score >= 60:
                scored.append((score, item.get("answer", ""), item.get("question", "")))
        return sorted(scored, reverse=True)

    async def select_quiz_answer(self, page, question):
        options = page.locator("#myform .qs_option")
        option_items = []
        for i in range(await options.count()):
            option = options.nth(i)
            text = await option.evaluate("el => el.innerText")
            option_items.append((option, text, normalize(text)))
        texts = [text for _, text, _ in option_items]
        self.log(f'Quiz options: {texts}')
        selected = choose_option(question, texts, self.quiz_bank)
        if selected is None:
            self.log('No unique, confident answer; skipping submission')
            return False
        option, text, _ = option_items[selected]
        radio = option.locator('input[type="radio"]')
        if await radio.count():
            await radio.check()
        else:
            await option.click(timeout=5000)
        self.log(f'Selected quiz option: {text.strip()}')
        return True

    async def leave_wall_messages(self, page):
        if int(self.config.get('message_count', 0)) <= 0:
            self.log('Wall messages disabled (message_count=0)')
            return
        self.log("Step 4: wall messages")
        source_uids = await self.collect_uids_from_source_wall_pages(
            page, int(self.config["message_count"])
        )
        targets = source_uids[: int(self.config["message_count"])]
        self.log(
            f"Found {len(source_uids)} uids from your wall pages only, selected {len(targets)} targets"
        )
        history = set(map(str, self.state.get("visited_uids", [])))
        if self.self_uid:
            history.add(self.self_uid)
        for index, uid in enumerate(targets):
            ok = await self.leave_one_message(page, uid)
            if ok:
                history.add(uid)
                self.state["visited_uids"] = sorted(
                    history, key=lambda x: int(x) if x.isdigit() else x
                )
                write_json(self.state_path, self.state)
            if index < len(targets) - 1:
                await page.wait_for_timeout(int(self.config["message_delay_seconds"]) * 1000)

    async def collect_uids_from_source_wall_pages(self, page, needed):
        all_uids = []
        # Only page through the configured source wall. Never expand from target users' walls.
        for page_no in range(1, 31):
            await page.goto(self.wall_page_url(page_no), wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)
            for uid in await self.collect_uids_from_current_page(page):
                if uid not in all_uids:
                    all_uids.append(uid)
            if len(all_uids) >= needed:
                break
        return all_uids

    def wall_page_url(self, page_no):
        parsed = urlparse(self.source_wall_url)
        query = parse_qs(parsed.query)
        query["page"] = [str(page_no)]
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    async def collect_uids_from_current_page(self, page):
        hrefs = []
        for _ in range(3):
            try:
                await page.wait_for_timeout(800)
                hrefs = await page.locator("a[href*='uid=']").evaluate_all(
                    "(links) => links.map(a => a.href)"
                )
                break
            except Exception:
                await page.wait_for_timeout(1200)
        uids = []
        for href in hrefs:
            uid = extract_uid(href)
            if uid and uid != self.self_uid and uid not in uids:
                uids.append(uid)
        return uids

    async def leave_one_message(self, page, uid):
        self.log(f"Leaving wall emoji for uid={uid}")
        await page.goto(
            f"{self.base_url}home.php?mod=space&uid={uid}&do=wall",
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(1200)
        if await page.locator("#comment_message").count() == 0:
            await self.screenshot(page, f"wall-no-textarea-{uid}")
            return False
        await page.locator("#comment_message").fill("")
        await self.choose_wall_emoji(page)
        if not (await page.locator("#comment_message").input_value()).strip():
            await page.locator("#comment_message").fill("[em:1:]")
        try:
            await page.locator("#commentsubmit_btn").click(timeout=5000)
            await page.wait_for_timeout(2500)
            result = ""
            result_box = page.locator(f"#return_qcwall_{uid}")
            if await result_box.count():
                result = (await result_box.inner_text(timeout=1000)).strip()
            self.log(f"Wall result for uid={uid}: {result or 'submitted'}")
            if "操作成功" in result:
                return True
            if "操作太快" in result:
                return False
            return bool(result)
        except PlaywrightTimeoutError:
            await self.screenshot(page, f"wall-submit-failed-{uid}")
            return False

    async def choose_wall_emoji(self, page):
        emoji_index = int(self.config.get("emoji_index", 0))
        try:
            await page.locator("#comment_face").click(timeout=3000)
            await page.wait_for_timeout(500)
        except PlaywrightTimeoutError:
            return False
        faces = page.locator("img[onclick*='insertFace'][src*='static/image/smiley/comcom']")
        count = await faces.count()
        if count:
            await faces.nth(min(emoji_index, count - 1)).click(timeout=3000)
            return True
        return False

    async def is_logged_in(self, page):
        return await page.locator('a[href*="action=logout"]').count() > 0

    async def ensure_login(self, page, wait=True):
        await page.goto(self.base_url, wait_until='domcontentloaded')
        try:
            await page.locator('a[href*="action=logout"]').first.wait_for(state='attached', timeout=8000)
            return True
        except PlaywrightTimeoutError:
            pass
        if not wait:
            return False
        self.log('请在浏览器中登录，程序将自动继续。')
        await self.screenshot(page, 'login-required')
        try:
            await page.locator('a[href*="action=logout"]').first.wait_for(
                state='attached', timeout=int(self.config.get('login_wait_minutes', 10)) * 60000)
            return True
        except PlaywrightTimeoutError:
            raise RuntimeError('等待登录超时，请运行 首次登录.bat。')

    async def run(self, check_login=False, inspect=False):
        profile = ROOT / self.config["profile_dir"]
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=True if check_login or inspect else bool(self.config.get("headless", False)),
                slow_mo=int(self.config.get("slow_mo_ms", 0)),
            )
            browser.set_default_timeout(int(self.config.get("navigation_timeout_ms", 45000)))
            page = browser.pages[0] if browser.pages else await browser.new_page()
            try:
                logged_in = await self.ensure_login(page, wait=not (check_login or inspect))
                if not logged_in:
                    await self.screenshot(page, 'login-check-failed')
                    raise RuntimeError('登录已失效，请运行 首次登录.bat。')
                if check_login:
                    self.log('登录状态有效；未执行签到、答题或留言。')
                    return
                if inspect:
                    for label, url in [('sign', self.sign_url), ('quiz', self.quiz_url)]:
                        await page.goto(url, wait_until='domcontentloaded')
                        await page.wait_for_timeout(2000)
                        await self.screenshot(page, 'inspect-' + label)
                        if label == 'sign':
                            self.log('Sign page text: ' + (await page.locator('body').inner_text())[:3500])
                        elif await page.locator('#myform').count():
                            question = await self.extract_quiz_question(page)
                            options = await page.locator('#myform .qs_option').all_inner_texts()
                            self.log(f'Preview question: {question}; options: {options}; match: {choose_option(question, options, self.quiz_bank)}')
                    return
                await self.sign_in(page)
                await self.lucky_wheel(page)
                await self.answer_quiz(page)
                await self.leave_wall_messages(page)
                self.log("Done")
            finally:
                await browser.close()

    async def login(self):
        profile = ROOT / self.config["profile_dir"]
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=False,
                slow_mo=int(self.config.get("slow_mo_ms", 0)),
            )
            page = browser.pages[0] if browser.pages else await browser.new_page()
            try:
                await self.ensure_login(page)
                self.log('登录成功，登录状态已保存。')
            finally:
                await browser.close()


def ensure_config():
    if not CONFIG_PATH.exists():
        example = ROOT / "config.example.json"
        CONFIG_PATH.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")


async def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--login", action="store_true")
    modes.add_argument("--run", action="store_true")
    modes.add_argument('--check-login', action='store_true')
    modes.add_argument('--inspect', action='store_true', help='Read-only website diagnosis')
    modes.add_argument('--import-bank', action='store_true', help='Import 题库.txt without opening a browser')
    args = parser.parse_args()
    ensure_config()
    bot = Bot(load_json(CONFIG_PATH, {}))
    if args.login:
        await bot.login()
    elif args.run:
        await bot.run()
    elif args.check_login:
        await bot.run(check_login=True)
    elif args.inspect:
        await bot.run(inspect=True)
    elif args.import_bank:
        print(f'Imported {len(bot.quiz_bank)} questions. See 题库导入报告.json')
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
