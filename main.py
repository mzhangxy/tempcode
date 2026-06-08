import os
import sys
import time
import random
import requests
from xvfbwrapper import Xvfb
from playwright.sync_api import sync_playwright

def send_tg_message(token, chat_id, message):
    if not token or not chat_id:
        print("未配置 TG_TOKEN 或 TG_CHAT_ID，跳过通知。")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "None"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("✅ Telegram 通知发送成功！")
    except Exception as e:
        print(f"❌ Telegram 通知请求异常: {e}")

def renew_host2play(url, proxy_url=None):
    print("启动 Xvfb 虚拟桌面...")
    vdisplay = Xvfb(width=1280, height=720, colordepth=24)
    vdisplay.start()

    success = False
    msg = ""

    # 使用 Playwright
    with sync_playwright() as p:
        try:
            ext_path = os.path.abspath(os.path.join(os.getcwd(), "extensions/nopecha"))
            user_data_dir = "/tmp/playwright_user_data"
            
            print(f"🧩 挂载插件路径: {ext_path}")

            # 构造代理配置
            proxy_config = None
            if proxy_url:
                if "://" not in proxy_url:
                    proxy_url = f"http://{proxy_url}"
                proxy_config = {"server": proxy_url}

            # 1. 以持久化上下文启动 Chromium
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                viewport={'width': 1280, 'height': 720},
                args=[
                    f"--disable-extensions-except={ext_path}",
                    f"--load-extension={ext_path}",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                    f"--proxy-server={proxy_url}",
                    "--ignore-certificate-errors", 
                    "--disable-web-security"
                ]
            )

            # =========================================================
            # 2. 强行唤醒并注入 NopeCHA API Key (Plan B 核心)
            # =========================================================
            time.sleep(3)
            page = context.pages[0]
            
            nopecha_key = os.getenv("NOPECHA_KEY")
            if not nopecha_key:
                print("❌ 警告: 未检测到 NOPECHA_KEY 环境变量，插件可能无法激活！")
            else:
                print(f"🔑 正在注入 NopeCHA API Key 并唤醒插件...")
                # 访问 NopeCHA 的快捷配置链接，插件会自动拦截并保存 Key
                page.goto(f"https://nopecha.com/setup#key={nopecha_key}", wait_until="load")
                time.sleep(5) # 给插件后台几秒钟时间完成验证和初始化
                print("✅ API Key 注入请求已发送。")

            # 3. 访问目标网址
            print(f"🌐 访问续期目标网址: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(5, 8))

            # 清理遮挡元素
            print("🧹 清理遮挡元素...")
            page.evaluate("""
                const cssSelectors = ['ins.adsbygoogle', 'iframe[src*="ads"]', '.modal-backdrop'];
                cssSelectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                });
            """)
            time.sleep(2)

            # 点击 Consent (如果存在)
            consent_btn = page.locator('button:has-text("Consent")')
            if consent_btn.count() > 0:
                consent_btn.first.click()
                time.sleep(2)

            # 4. 触发续期弹窗
            print("🖱️ 打开续期弹窗...")
            renew_btn = page.locator('button:has-text("Renew server")')
            if renew_btn.count() > 0:
                renew_btn.first.click(force=True)
            time.sleep(3)

            # 等待过期时间文本出现
            for _ in range(8):
                if page.locator('text="Expires in:"').count() > 0 or page.locator('text="Deletes on:"').count() > 0:
                    break
                time.sleep(1)

            # 再次点击弹窗内的 Renew
            if renew_btn.count() > 1:
                renew_btn.nth(1).click(force=True)
            elif renew_btn.count() > 0:
                renew_btn.first.click(force=True)
            
            time.sleep(random.uniform(5, 8))

            # =========================================================
            # 5. 核心：旁观者模式等待 NopeCHA 破解 (Playwright版)
            # =========================================================
            solved_captcha = False
            # 定位 reCAPTCHA iframe
            recaptcha_frame = page.frame_locator('iframe[src*="recaptcha/api2/anchor"]')

            if recaptcha_frame.locator('#recaptcha-anchor').count() > 0:
                print("👁️ 侦测到 reCAPTCHA，开始监控 NopeCHA 工作状态...")
                
                max_wait_time = 120 
                check_interval = 2
                
                for i in range(int(max_wait_time / check_interval)):
                    # 防御：10秒没动静，主动点一下唤醒插件
                    if i == 5:
                        try:
                            checkbox = recaptcha_frame.locator('#recaptcha-anchor')
                            if checkbox.get_attribute('aria-checked') != 'true':
                                print("👉 10秒未自动执行，尝试手动点击 checkbox 唤醒 NopeCHA...")
                                checkbox.click(force=True)
                        except Exception as e:
                            print(f"⚠️ 手动唤醒点击失败: {e}")

                    # 检查隐藏表单 g-recaptcha-response
                    token_ele = page.locator('textarea[name="g-recaptcha-response"]')
                    if token_ele.count() > 0:
                        token_val = token_ele.first.input_value()
                        if token_val and len(token_val) > 20:
                            print("✅ [监控通过] 发现 NopeCHA 注入了合法的验证码 Token！")
                            solved_captcha = True
                            break

                    # 检查前端绿勾
                    try:
                        checkbox = recaptcha_frame.locator('#recaptcha-anchor')
                        if checkbox.count() > 0 and checkbox.get_attribute('aria-checked') == 'true':
                            print("✅ [监控通过] reCAPTCHA 显示已勾选！")
                            solved_captcha = True
                            break
                    except:
                        pass
                    
                    if i % 5 == 0:
                        print(f"⏳ 等待 NopeCHA 破解中... (已等待 {i * check_interval} 秒)")
                    time.sleep(check_interval)
                    
                if not solved_captcha:
                    msg = "❌ NopeCHA 破解超时 (2分钟内未获取到Token)"
                    print("📸 正在保存超时现场截图...")
                    page.screenshot(path="error_timeout.jpg", full_page=True)
                    return success, msg

            else:
                print("⚠️ 未侦测到 reCAPTCHA iframe，尝试直接进行最终续期。")
                solved_captcha = True 

            # 6. 提交最终续期
            if solved_captcha:
                print("🚀 准备点击最终 Renew 按钮...")
                time.sleep(2)
                final_btn = page.locator('button:has-text("Renew")').last
                if final_btn.count() > 0:
                    final_btn.click(force=True)
                    time.sleep(8)
                    msg = "🎉 续期操作成功！(Powered by Playwright + NopeCHA)"
                    success = True
                else:
                    msg = "❌ 找不到最终 Renew 按钮"
                    page.screenshot(path="error_no_final_btn.jpg", full_page=True)

        except Exception as e:
            msg = f"💥 脚本运行异常: {str(e)[:200]}"
            print(msg)
            try: page.screenshot(path="error_exception.jpg", full_page=True)
            except: pass
        finally:
            if context:
                context.close()
            vdisplay.stop()
            return success, msg

if __name__ == "__main__":
    renew_url = os.getenv("RENEW_URL")
    tg_token = os.getenv("TG_TOKEN")
    tg_chat_id = os.getenv("TG_CHAT_ID")
    proxy_url = os.getenv("PROXY", "127.0.0.1:10808")

    if not renew_url:
        print("❌ 缺少 RENEW_URL 环境变量")
        sys.exit(1)

    is_success, result_message = renew_host2play(renew_url, proxy_url)
    send_tg_message(tg_token, tg_chat_id, result_message)
    if not is_success: sys.exit(1)
