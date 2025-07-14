import os
import signal
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

# --- 配置项 (保持不变) ---
SERVER_URL = "https://panel.sillydev.co.uk/server/9425fb98"
LOGIN_URL = "https://panel.sillydev.co.uk/auth/login"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"
TASK_TIMEOUT_SECONDS = 300

# --- 超时处理机制 (保持不变) ---
class TaskTimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError(f"任务执行超过了设定的 {TASK_TIMEOUT_SECONDS} 秒阈值")

if os.name != 'nt':
    signal.signal(signal.SIGALRM, timeout_handler)

# --- 登录函数 (保持不变) ---
def login_with_playwright(page):
    """处理登录逻辑，优先使用Cookie，失败则使用邮箱密码。"""
    sillydev_cookie = os.environ.get('SILLYDEV_COOKIE')
    sillydev_email = os.environ.get('SILLYDEV_EMAIL')
    sillydev_password = os.environ.get('SILLYDEV_PASSWORD')

    if sillydev_cookie:
        print("检测到 SILLYDEV_COOKIE，尝试使用 Cookie 登录...")
        print(f"已设置 Cookie。正在访问目标服务器页面: {SERVER_URL}")
        try:
            response = page.goto(SERVER_URL, wait_until="domcontentloaded", timeout=60000)
            content = page.content().lower()
            if response.status != 200 or "you have been blocked" in content or "access denied" in content:
                print("❌ 访问被阻止或页面状态异常。反机器人系统仍然生效。")
                page.screenshot(path="blocked_page_error.png")
                return False
        except PlaywrightTimeoutError:
            print(f"❌ 导航至服务器页面时超时。")
            page.screenshot(path="navigation_timeout_error.png")
            return False
        except Exception as e:
            print(f"❌ 导航至服务器页面时发生未知错误: {e}")
            page.screenshot(path="navigation_error.png")
            return False

        if "auth/login" in page.url:
            print("Cookie 登录失败或会话已过期，将回退到邮箱密码登录。")
            page.context.clear_cookies()
        else:
            print("✅ 成功访问服务器页面！")
            return True

    if not (sillydev_email and sillydev_password):
        print("❌ 错误: Cookie 无效或未提供，且未提供 SILLYDEV_EMAIL 和 SILLYDEV_PASSWORD。无法登录。", flush=True)
        return False

    print("正在尝试使用邮箱和密码登录...")
    try:
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        email_selector = 'input[name="username"]'
        password_selector = 'input[name="password"]'
        login_button_selector = 'button[type="submit"]:has-text("Login")'
        page.wait_for_selector(email_selector, timeout=30000)
        page.wait_for_selector(password_selector, timeout=30000)
        page.fill(email_selector, sillydev_email)
        page.fill(password_selector, sillydev_password)
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.click(login_button_selector)

        if "auth/login" in page.url:
            print("❌ 邮箱密码登录失败，请检查凭据是否正确。", flush=True)
            page.screenshot(path="login_fail_error.png")
            return False

        print("✅ 邮箱密码登录成功！")
        return True
    except Exception as e:
        print(f"❌ 邮箱密码登录过程中发生错误: {e}", flush=True)
        page.screenshot(path="login_process_error.png")
        return False

# --- 核心任务函数 (保持之前强制点击的版本) ---
def renew_server_task(page):
    """执行一次续期服务器的任务。"""
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行服务器续期任务...")

        renew_selector_css = 'span.text-blue-500.text-sm.cursor-pointer'
        renew_element = page.locator(renew_selector_css)

        print(f"步骤1: 等待续订元素 '{renew_selector_css}' 附加到DOM...")
        renew_element.wait_for(state='attached', timeout=60000)
        print("...续订元素已在DOM中找到。")

        time.sleep(2)

        print("步骤2: 强制点击元素（忽略可见性检查）...")
        renew_element.click(force=True, timeout=15000)
        print("...已成功强制点击 'Renew' 链接。")

        okay_button_text = "Okay"
        print(f"步骤3: 查找并点击 '{okay_button_text}' 按钮...")
        okay_button = page.get_by_role("button", name=okay_button_text)
        okay_button.wait_for(state='visible', timeout=30000)
        okay_button.click()
        print(f"...已点击 '{okay_button_text}'。")

        print(f"✅ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 续期任务成功完成！")
        page.screenshot(path="task_success.png")
        return True

    except PlaywrightTimeoutError as e:
        print(f"❌ 任务执行超时。错误: {e}", flush=True)
        page.screenshot(path="task_element_timeout_error.png")
        return False
    except Exception as e:
        print(f"❌ 任务执行过程中发生未知错误: {e}", flush=True)
        page.screenshot(path="task_general_error.png")
        return False

# --- 主函数 (最终版，手动注入脚本反检测) ---
def main():
    """主执行函数"""
    print("启动服务器自动续期任务（单次运行模式）...", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )

        sillydev_cookie = os.environ.get('SILLYDEV_COOKIE')
        if sillydev_cookie:
            session_cookie = {
                'name': COOKIE_NAME, 'value': sillydev_cookie, 'domain': '.panel.sillydev.co.uk',
                'path': '/', 'expires': int(time.time()) + 3600 * 24 * 365, 'httpOnly': True,
                'secure': True, 'sameSite': 'Lax'
            }
            context.add_cookies([session_cookie])

        page = context.new_page()
        
        # 【【【 核心修改点: 手动注入脚本来隐藏webdriver标志 】】】
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("浏览器已启动，并应用了手动伪装脚本。")

        try:
            if not login_with_playwright(page):
                print("登录失败或被拦截，程序终止。", flush=True)
                exit(1)

            print("\n----------------------------------------------------")
            if os.name != 'nt':
                signal.alarm(TASK_TIMEOUT_SECONDS)

            success = renew_server_task(page)

            if os.name != 'nt':
                signal.alarm(0)

            if success:
                print("本轮续期任务成功完成。", flush=True)
            else:
                print("本轮续期任务失败。", flush=True)
                exit(1)

        except (TaskTimeoutError, SystemExit) as e:
            if isinstance(e, TaskTimeoutError):
                 print(f"🔥🔥🔥 任务强制超时（{TASK_TIMEOUT_SECONDS}秒）！🔥🔥🔥", flush=True)
                 print(f"错误信息: {e}", flush=True)
                 page.screenshot(path="task_force_timeout_error.png")
        except Exception as e:
            print(f"主程序发生严重错误: {e}", flush=True)
            page.screenshot(path="main_critical_error.png")
        finally:
            print("关闭浏览器，程序结束。", flush=True)
            if browser.is_connected():
                browser.close()

if __name__ == "__main__":
    main()
    print("脚本执行完毕。")
