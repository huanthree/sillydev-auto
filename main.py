import os
import signal
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

# --- 配置项 ---
# 目标服务器的URL
SERVER_URL = "https://panel.sillydev.co.uk/server/9425fb98"
# 登录页面的URL
LOGIN_URL = "https://panel.sillydev.co.uk/auth/login"
# 你的 Cookie 名称 (从浏览器开发者工具中获取)
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"
# 单次任务执行的超时时间（秒），防止脚本意外卡死
TASK_TIMEOUT_SECONDS = 300  # 5分钟

# --- 超时处理机制 (适用于非Windows环境) ---
class TaskTimeoutError(Exception):
    """自定义任务超时异常"""
    pass

def timeout_handler(signum, frame):
    """超时信号处理函数"""
    raise TaskTimeoutError(f"任务执行超过了设定的 {TASK_TIMEOUT_SECONDS} 秒阈值")

if os.name != 'nt':
    signal.signal(signal.SIGALRM, timeout_handler)

def login_with_playwright(page):
    """处理登录逻辑，优先使用Cookie，失败则使用邮箱密码。"""
    sillydev_cookie = os.environ.get('SILLYDEV_COOKIE')
    sillydev_email = os.environ.get('SILLYDEV_EMAIL')
    sillydev_password = os.environ.get('SILLYDEV_PASSWORD')

    # 优先使用 Cookie 登录
    if sillydev_cookie:
        print("检测到 SILLYDEV_COOKIE，尝试使用 Cookie 登录...")
        session_cookie = {
            'name': COOKIE_NAME,
            'value': sillydev_cookie,
            'domain': '.panel.sillydev.co.uk',
            'path': '/',
            'expires': int(time.time()) + 3600 * 24 * 365,
            'httpOnly': True,
            'secure': True,
            'sameSite': 'Lax'
        }
        page.context.add_cookies([session_cookie])
        print(f"已设置 Cookie。正在访问目标服务器页面: {SERVER_URL}")
        page.goto(SERVER_URL, wait_until="domcontentloaded")
        
        # 检查是否跳转到了登录页，如果是，则说明Cookie无效
        if "auth/login" in page.url:
            print("Cookie 登录失败或会话已过期，将回退到邮箱密码登录。")
            page.context.clear_cookies()
        else:
            print("✅ Cookie 登录成功！")
            return True

    # 如果 Cookie 登录失败或未提供 Cookie，则使用邮箱密码登录
    if not (sillydev_email and sillydev_password):
        print("❌ 错误: Cookie 无效或未提供，且未提供 SILLYDEV_EMAIL 和 SILLYDEV_PASSWORD。无法登录。", flush=True)
        return False

    print("正在尝试使用邮箱和密码登录...")
    try:
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        
        # 直接定位输入框和按钮，因为该登录页面没有额外的点击步骤
        email_selector = 'input[name="username"]'
        password_selector = 'input[name="password"]'
        login_button_selector = 'button[type="submit"]:has-text("Login")'
        
        print("等待登录表单元素加载...")
        page.wait_for_selector(email_selector, timeout=30000)
        page.wait_for_selector(password_selector, timeout=30000)
        
        print("正在填写邮箱和密码...")
        page.fill(email_selector, sillydev_email)
        page.fill(password_selector, sillydev_password)
        
        print("正在点击登录按钮...")
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.click(login_button_selector)
        
        # 再次检查登录后是否还在登录页
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

def renew_server_task(page):
    """执行一次续期服务器的任务。"""
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行服务器续期任务...")
        
        # 确保当前在正确的服务器页面
        if page.url != SERVER_URL:
            print(f"当前不在目标页面，正在导航至: {SERVER_URL}")
            page.goto(SERVER_URL, wait_until="domcontentloaded")

        # 步骤1: 查找并点击 "Renew" 链接/按钮
        # 使用 get_by_text("Renew") 更具弹性，即使元素标签或class变化也能找到
        renew_selector_text = "Renew"
        print(f"步骤1: 查找并点击 '{renew_selector_text}' 按钮...")
        # 等待按钮可见并且可点击
        page.get_by_text(renew_selector_text, exact=True).wait_for(state='visible', timeout=30000)
        page.get_by_text(renew_selector_text, exact=True).click()
        print(f"...已点击 '{renew_selector_text}'。")

        # 步骤2: 在弹出的对话框中，查找并点击 "Okay" 按钮
        okay_button_text = "Okay"
        print(f"步骤2: 查找并点击 '{okay_button_text}' 按钮...")
        # 通常弹窗出现需要一点时间，等待按钮出现
        page.get_by_role("button", name=okay_button_text).wait_for(state='visible', timeout=30000)
        page.get_by_role("button", name=okay_button_text).click()
        print(f"...已点击 '{okay_button_text}'。")

        print(f"✅ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 续期任务成功完成！")
        return True

    except PlaywrightTimeoutError as e:
        print(f"❌ 任务执行超时: 未在规定时间内找到元素。请检查选择器或页面是否已更改。错误: {e}", flush=True)
        page.screenshot(path="task_element_timeout_error.png")
        return False
    except Exception as e:
        print(f"❌ 任务执行过程中发生未知错误: {e}", flush=True)
        page.screenshot(path="task_general_error.png")
        return False

def main():
    """主函数，执行一次登录和一次续期任务，然后退出。"""
    print("启动服务器自动续期任务（单次运行模式）...", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # 在 Actions 中必须使用 headless 模式
        page = browser.new_page()
        page.set_default_timeout(60000) # 设置默认超时为60秒
        print("浏览器启动成功。", flush=True)

        try:
            # 步骤1: 登录
            if not login_with_playwright(page):
                print("登录失败，程序终止。", flush=True)
                exit(1) # 以失败状态码退出，让 Actions 知道任务失败

            # 步骤2: 执行续期核心任务 (带超时监控)
            if os.name != 'nt':
                signal.alarm(TASK_TIMEOUT_SECONDS) # 启动任务超时倒计时
            
            print("\n----------------------------------------------------")
            success = renew_server_task(page)
            
            if os.name != 'nt':
                signal.alarm(0) # 关闭倒计时

            if success:
                print("本轮续期任务成功完成。", flush=True)
            else:
                print("本轮续期任务失败。", flush=True)
                exit(1)

        except TaskTimeoutError as e:
            print(f"🔥🔥🔥 任务强制超时（{TASK_TIMEOUT_SECONDS}秒）！🔥🔥🔥", flush=True)
            print(f"错误信息: {e}", flush=True)
            page.screenshot(path="task_force_timeout_error.png")
            exit(1)
        except Exception as e:
            print(f"主程序发生严重错误: {e}", flush=True)
            page.screenshot(path="main_critical_error.png")
            exit(1)
        finally:
            print("关闭浏览器，程序结束。", flush=True)
            browser.close()

if __name__ == "__main__":
    main()
    print("脚本执行完毕。")
    exit(0) # 以成功状态码退出
