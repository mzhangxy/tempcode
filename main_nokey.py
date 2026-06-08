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

    with sync_playwright() as p:
        try:
            ext_path = os.path.abspath(os.path.join(os.getcwd(), "extensions/nopecha"))
            user_data_dir = "/tmp/playwright_user_data"
            
            print(f"🧩 挂载插件路径: {ext_path}")

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
                    "--disable-web-security",
                    # 💥【保留核心杀招】彻底关闭跨域进程隔离
                    "--disable-features=IsolateOrigins,site-per-process"
                ]
            )

            # =========================================================
            # 2. 等待进程苏醒 (已彻底移除 API Key 注入逻辑)
            # =========================================================
            print("⏳ 等待 NopeCHA 后台进程 (Service Worker) 完全激活...")
            worker_ready = False
            for _ in range(15):
                if context.service_workers or context.background_pages:
                    worker_ready = True
                    break
                time.sleep(1)
                
            if worker_ready:
                print("✅ 插件后台进程已确认激活！")
            else:
                print("⚠️ 警告: 插件后台进程响应迟缓。")

            page = context.pages[0]
            
            # 【注意】：这里原本访问 nopecha.com/setup 注入 Key 的代码已被全部删除。
            # 我们现在完全依赖启动参数中注入的 proxy_url (家宽代理) 来获取免费额度。

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

            for _ in range(8):
                if page.locator('text="Expires in:"').count() > 0 or page.locator('text="Deletes on:"').count() > 0:
                    break
                time.sleep(1)

            if renew_btn.count() > 1:
                renew_btn.nth(1).click(force=True)
            elif renew_btn.count() > 0:
                renew_btn.first.click(force=True)
            
            time.sleep(random.uniform(5, 8))

            # =========================================================
            # 5. 核心：旁观者模式等待 NopeCHA 破解
            # =========================================================
            solved_captcha = False
            recaptcha_frame = page.frame_locator('iframe[src*="recaptcha/api2/anchor"]')

            if recaptcha_frame.locator('#recaptcha-anchor').count() > 0:
                print("👁️ 侦测到 reCAPTCHA，开始监控 NopeCHA 工作状态...")
                
                max_wait_time = 120 
                check_interval = 2
                
                for i in range(int(max_wait_time / check_interval)):
                    if i == 5:
                        try:
                            checkbox = recaptcha_frame.locator('#recaptcha-anchor')
                            if checkbox.get_attribute('aria-checked') != 'true':
                                print("👉 10秒未自动执行，尝试手动点击 checkbox 唤醒 NopeCHA...")
                                checkbox.click(force=True)
                        except Exception as e:
                            print(f"⚠️ 手动唤醒点击失败: {e}")

                    token_ele = page.locator('textarea[name="g-recaptcha-response"]')
                    if token_ele.count() > 0:
                        token_val = token_ele.first.input_value()
                        if token_val and len(token_val) > 20:
                            print("✅ [监控通过] 发现 NopeCHA 注入了合法的验证码 Token！")
                            solved_captcha = True
                            break

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
