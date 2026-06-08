import os
import sys
import time
import random
import requests
from xvfbwrapper import Xvfb
from DrissionPage import ChromiumPage, ChromiumOptions

# ==============================================================================
# Telegram 通知模块
# ==============================================================================
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

# ==============================================================================
# 核心续期业务逻辑
# ==============================================================================
def renew_host2play(url, proxy_url=None):
    print("启动 Xvfb 虚拟桌面...")
    vdisplay = Xvfb(width=1280, height=720, colordepth=24)
    vdisplay.start()

    success = False
    msg = ""
    page = None

    try:
        # 1. 初始化 DrissionPage 配置
        co = ChromiumOptions()
        co.set_browser_path('/usr/bin/google-chrome')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-gpu')
        co.headless(False) # 必须保持为 False，插件才能运行
        
        # 挂载 NopeCHA 插件 (使用绝对路径)
        ext_path = os.path.abspath(os.path.join(os.getcwd(), "extensions/nopecha"))
        print(f"🧩 挂载插件路径: {ext_path}")
        co.add_extension(ext_path)

        # 设置代理
        if proxy_url:
            if "://" not in proxy_url:
                proxy_url = f"http://{proxy_url}"
            co.set_proxy(proxy_url)

        page = ChromiumPage(co)
        page.set.window.size(1280, 720)

        # 给 NopeCHA 一点启动和加载规则的时间
        time.sleep(3) 

        print(f"🌐 访问续期目标网址: {url}")
        page.get(url, retry=3)
        time.sleep(random.uniform(5, 8))

        # 2. 清理遮挡与前置交互 (保留你原有的优秀防反爬逻辑)
        print("🧹 清理遮挡元素...")
        page.run_js("""
            const cssSelectors = ['ins.adsbygoogle', 'iframe[src*="ads"]', '.modal-backdrop'];
            cssSelectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });
        """)
        time.sleep(2)

        consent_btn = page.ele('tag:button@@text():Consent', timeout=2)
        if consent_btn:
            consent_btn.click()
            time.sleep(2)

        # 3. 触发续期弹窗
        print("🖱️ 打开续期弹窗...")
        renew_btn1 = page.ele('xpath://button[contains(text(), "Renew server")]', timeout=3)
        if renew_btn1:
            renew_btn1.click(by_js=True)
        else:
            page.run_js("document.querySelectorAll('button').forEach(b => {if(b.textContent.includes('Renew server')) b.click();});")
        time.sleep(3)

        # 等待弹窗完全加载
        for _ in range(8):
            if page.ele('text:Expires in:', timeout=0.5) or page.ele('text:Deletes on:', timeout=0.5):
                break
            time.sleep(1)

        renew_btn2 = page.ele('xpath://button[contains(text(), "Renew server")]', timeout=2)
        if renew_btn2:
            renew_btn2.click(by_js=True)
        
        time.sleep(random.uniform(5, 8))   

        # =========================================================
        # 4. 核心：旁观者模式等待 NopeCHA 破解 (加入调试探针)
        # =========================================================
        solved_captcha = False
        anchor_frame = page.get_frame('xpath://iframe[contains(@src, "recaptcha/api2/anchor")]', timeout=5)

        if anchor_frame:
            print("👁️ 侦测到 reCAPTCHA，开始监控 NopeCHA 工作状态...")
            
            # 【调试探针 1】打印所有标签页，检查是否有 NopeCHA 的欢迎页
            print(f"📑 当前打开的标签页数量: {len(page.tab_ids)}")
            for t_id in page.tab_ids:
                try:
                    t = page.browser.get_tab(t_id)
                    print(f"   -> 标签页 URL: {t.url}")
                except:
                    pass

            max_wait_time = 120 
            check_interval = 2
            
            for i in range(int(max_wait_time / check_interval)):
                # 【调试探针 2】等待 10 秒如果还没反应，手动点一下 checkbox 唤醒插件
                if i == 5: 
                    try:
                        print("👉 10秒未自动执行，尝试手动点击 checkbox 唤醒 NopeCHA...")
                        anchor_box = anchor_frame.ele('#recaptcha-anchor', timeout=1)
                        if anchor_box and anchor_box.attr('aria-checked') != 'true':
                            anchor_box.click(by_js=False) # 尝试真实点击
                    except Exception as e:
                        print(f"⚠️ 手动唤醒点击失败: {e}")

                token_ele = page.ele('@name=g-recaptcha-response', timeout=0.5)
                if token_ele:
                    token_val = token_ele.attr('value')
                    if token_val and len(token_val) > 20:
                        print("✅ [监控通过] 发现 NopeCHA 注入了合法的验证码 Token！")
                        solved_captcha = True
                        break

                try:
                    anchor_box = anchor_frame.ele('#recaptcha-anchor', timeout=0.5)
                    if anchor_box and anchor_box.attr('aria-checked') == 'true':
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
                print("📸 正在保存超时现场截图与源码...")
                # 【调试探针 3】保存真实的屏幕截图，这比 HTML 源码直观 100 倍！
                page.get_screenshot(path="error_timeout.jpg", full_page=True)
                with open("error_timeout.html", "w", encoding="utf-8") as f:
                    f.write(page.html)
                return success, msg

        else:
            print("⚠️ 未侦测到 reCAPTCHA，尝试直接进行最终续期。")
            solved_captcha = True

        # 5. 提交最终续期
        if solved_captcha:
            print("🚀 准备点击最终 Renew 按钮...")
            time.sleep(2) # 给前端动画一点缓冲时间
            final_btn = page.ele('xpath://button[normalize-space(text())="Renew"]', timeout=3)
            if final_btn:
                final_btn.click(by_js=True)
                time.sleep(8)
                msg = "🎉 续期操作成功！(Powered by NopeCHA)"
                success = True
            else:
                msg = "❌ 找不到最终 Renew 按钮"
                with open("error_no_final_btn.html", "w", encoding="utf-8") as f:
                    f.write(page.html)

    except Exception as e:
        msg = f"💥 脚本运行异常: {str(e)[:200]}"
        print(msg)
    finally:
        if page:
            try: page.quit()
            except: pass
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
