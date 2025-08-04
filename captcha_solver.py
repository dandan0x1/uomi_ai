#!/usr/bin/env python3
"""
使用 Playwright 自动获取 UOMI 验证码 - 修复版
"""

import asyncio
import logging
import json
from typing import Optional, Dict
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import time
import random

logger = logging.getLogger(__name__)

class UomiCaptchaSolver:
    def __init__(self, headless: bool = True, proxy: Optional[Dict] = None):
        self.headless = headless
        self.proxy = proxy
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
        
    async def start(self):
        """启动浏览器"""
        self.playwright = await async_playwright().start()
        
        # 配置浏览器启动参数
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
        
        # 启动浏览器
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=browser_args
        )
        
        # 创建上下文
        context_options = {
            'viewport': {'width': 1280, 'height': 720},
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        }
        
        if self.proxy:
            context_options['proxy'] = {
                'server': self.proxy.get('http', '').replace('http://', ''),
                'username': self.proxy.get('username'),
                'password': self.proxy.get('password')
            }
            
        self.context = await self.browser.new_context(**context_options)
        
        # 创建页面
        self.page = await self.context.new_page()
        
        # 设置额外的请求头
        await self.page.set_extra_http_headers({
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,ja;q=0.6,fr;q=0.5,ru;q=0.4,und;q=0.3',
            'DNT': '1',
            'Sec-CH-UA': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        })
        
    async def close(self):
        """关闭浏览器"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
            
    async def solve_captcha(self, address: str, max_retries: int = 3) -> Optional[str]:
        """解决验证码并获取 captcha token"""
        for attempt in range(max_retries):
            try:
                logger.info(f"第 {attempt + 1} 次尝试获取验证码 (地址: {address})")

                # 访问 UOMI 水龙头页面
                logger.info("正在访问 UOMI 水龙头页面...")
                await self.page.goto('https://app.uomi.ai/faucet', wait_until='domcontentloaded')

                # 等待页面完全加载
                logger.info("等待页面完全加载...")
                await asyncio.sleep(random.uniform(3, 6))

                # 等待网络空闲
                try:
                    await self.page.wait_for_load_state('networkidle', timeout=10000)
                    logger.info("页面网络空闲")
                except Exception as e:
                    logger.warning(f"等待网络空闲超时: {e}")

                # 额外等待确保所有 JavaScript 执行完成
                await asyncio.sleep(random.uniform(2, 4))

                # 先填写地址，再处理验证码
                captcha_token = await self.fill_address_and_get_captcha(address)

                if captcha_token:
                    logger.info(f"成功获取验证码 token: {captcha_token}")
                    return captcha_token
                else:
                    logger.warning("未能获取验证码 token")

            except Exception as e:
                logger.error(f"第 {attempt + 1} 次尝试失败: {e}")

            # 如果失败，等待一段时间后重试
            if attempt < max_retries - 1:
                wait_time = random.uniform(5, 10)
                logger.info(f"等待 {wait_time:.1f} 秒后重试...")
                await asyncio.sleep(wait_time)

        logger.error("所有尝试都失败了")
        return None

    async def fill_address_and_get_captcha(self, address: str) -> Optional[str]:
        """连接钱包并获取验证码"""
        try:
            # 步骤1: 检查是否需要连接钱包
            logger.info("检查是否需要连接钱包...")

            # 查找连接钱包按钮
            connect_button = await self.find_connect_wallet_button()

            if connect_button:
                logger.info("找到连接钱包按钮，准备连接...")
                await self.connect_wallet(address)
            else:
                logger.info("未找到连接钱包按钮，可能已经连接或不需要连接")

            # 步骤2: 处理验证码和点击按钮
            return await self.find_and_click_captcha()

        except Exception as e:
            logger.error(f"连接钱包和获取验证码时发生错误: {e}")
            return None

    async def find_connect_wallet_button(self) -> Optional[object]:
        """查找连接钱包按钮"""
        try:
            # 尝试多种选择器查找连接钱包按钮
            connect_selectors = [
                'button:has-text("Connect Wallet")',
                'button:has-text("Connect")',
                'button:has-text("连接钱包")',
                'button[class*="connect"]',
                'button[id*="connect"]',
                '[role="button"]:has-text("Connect")',
                '.connect-wallet',
                '.wallet-connect'
            ]

            for selector in connect_selectors:
                try:
                    logger.info(f"尝试连接按钮选择器: {selector}")
                    await self.page.wait_for_selector(selector, timeout=2000)
                    button = await self.page.query_selector(selector)
                    if button:
                        button_text = await button.text_content()
                        logger.info(f"找到按钮，文本: {button_text}")
                        if button_text and any(keyword in button_text.lower() for keyword in ['connect', 'wallet', '连接']):
                            logger.info(f"找到连接钱包按钮: {selector}")
                            return button
                except Exception as e:
                    logger.debug(f"连接按钮选择器 {selector} 未找到: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"查找连接钱包按钮时发生错误: {e}")
            return None

    async def connect_wallet(self, address: str) -> bool:
        """模拟连接钱包"""
        try:
            logger.info("开始模拟钱包连接...")

            # 注入 Web3 和 MetaMask 模拟
            await self.page.add_init_script(f"""
                // 模拟 MetaMask/Web3 钱包
                window.ethereum = {{
                    isMetaMask: true,
                    isConnected: () => true,
                    request: async (params) => {{
                        console.log('Web3 request:', params);

                        if (params.method === 'eth_requestAccounts') {{
                            return ['{address}'];
                        }}

                        if (params.method === 'eth_accounts') {{
                            return ['{address}'];
                        }}

                        if (params.method === 'eth_chainId') {{
                            return '0x1122'; // 4386 in hex
                        }}

                        if (params.method === 'wallet_addEthereumChain') {{
                            return null; // 成功添加网络
                        }}

                        if (params.method === 'wallet_switchEthereumChain') {{
                            return null; // 成功切换网络
                        }}

                        return null;
                    }},
                    on: (event, callback) => {{
                        console.log('Web3 event listener:', event);
                    }},
                    removeListener: (event, callback) => {{
                        console.log('Web3 remove listener:', event);
                    }}
                }};

                // 模拟 web3 对象
                window.web3 = {{
                    currentProvider: window.ethereum,
                    eth: {{
                        accounts: ['{address}'],
                        defaultAccount: '{address}'
                    }}
                }};

                // 触发连接事件
                window.dispatchEvent(new Event('ethereum#initialized'));
            """)

            logger.info("已注入 Web3 钱包模拟代码")

            # 刷新页面以应用注入的代码
            await self.page.reload(wait_until='domcontentloaded')
            await asyncio.sleep(3)

            # 再次查找连接按钮并点击
            connect_button = await self.find_connect_wallet_button()
            if connect_button:
                logger.info("点击连接钱包按钮...")
                await connect_button.click()

                # 等待连接完成
                await asyncio.sleep(3)

                logger.info("钱包连接模拟完成")
                return True
            else:
                logger.info("刷新后未找到连接按钮，可能已经连接")
                return True

        except Exception as e:
            logger.error(f"模拟钱包连接时发生错误: {e}")
            return False
        
    async def find_and_click_captcha(self) -> Optional[str]:
        """查找并点击验证码，然后点击 REQUEST 按钮获取 token"""
        try:
            # 设置网络监听器来捕获验证码请求和响应
            captured_token = None

            async def handle_request(request):
                nonlocal captured_token
                try:
                    url = request.url
                    method = request.method

                    # 监听所有POST请求，特别是包含captcha的请求
                    if method == 'POST' and any(keyword in url.lower() for keyword in ['faucet', 'captcha', 'challenge', 'verify']):
                        logger.info(f"捕获到POST请求: {url}")

                        # 获取请求体
                        try:
                            post_data = request.post_data
                            if post_data:
                                logger.info(f"请求数据: {post_data}")

                                # 尝试解析JSON数据
                                try:
                                    data = json.loads(post_data)
                                    if 'captcha' in data and data['captcha']:
                                        logger.info(f"从请求中找到 captcha: {data['captcha']}")
                                        captured_token = data['captcha']
                                except json.JSONDecodeError:
                                    logger.debug("请求数据不是有效的 JSON")
                        except Exception as e:
                            logger.debug(f"获取请求数据失败: {e}")

                except Exception as e:
                    logger.debug(f"处理请求时出错: {e}")

            async def handle_response(response):
                nonlocal captured_token
                try:
                    url = response.url
                    # 检查是否是水龙头请求的响应
                    if 'faucet/request' in url:
                        logger.info(f"捕获到水龙头请求响应: {url}")
                        if response.status == 200:
                            content_type = response.headers.get('content-type', '')
                            if 'application/json' in content_type:
                                text = await response.text()
                                logger.info(f"水龙头响应内容: {text}")

                                try:
                                    data = json.loads(text)
                                    # 查找 twitterCode 或其他可能的字段
                                    if 'twitterCode' in data:
                                        logger.info(f"找到 twitterCode: {data['twitterCode']}")
                                        captured_token = data['twitterCode']
                                    elif 'captcha' in data:
                                        logger.info(f"找到 captcha: {data['captcha']}")
                                        captured_token = data['captcha']
                                    elif 'token' in data:
                                        logger.info(f"找到 token: {data['token']}")
                                        captured_token = data['token']
                                except json.JSONDecodeError:
                                    logger.debug("响应不是有效的 JSON")
                except Exception as e:
                    logger.debug(f"处理响应时出错: {e}")

            # 注册请求和响应监听器
            self.page.on('request', handle_request)
            self.page.on('response', handle_response)

            # 查找验证码容器和复选框
            logger.info("正在查找验证码元素...")

            # 尝试多个可能的选择器
            selectors_to_try = [
                'div.captcha',  # 验证码容器
                'div.captcha div.checkbox[part="checkbox"]',  # 完整路径
                'div.checkbox[part="checkbox"]',  # 直接选择器
                '[role="button"][aria-label*="verify"]',  # 通过 aria-label 查找
                '.captcha [part="checkbox"]'  # 通过 part 属性查找
            ]

            captcha_element = None
            for selector in selectors_to_try:
                try:
                    logger.info(f"尝试选择器: {selector}")
                    await self.page.wait_for_selector(selector, timeout=5000)
                    captcha_element = await self.page.query_selector(selector)
                    if captcha_element:
                        logger.info(f"找到验证码元素: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"选择器 {selector} 未找到: {e}")
                    continue

            if not captcha_element:
                # 如果都没找到，尝试等待更长时间
                logger.warning("未找到验证码元素，等待页面完全加载...")
                await asyncio.sleep(5)

                # 再次尝试查找
                try:
                    await self.page.wait_for_selector('div.captcha', timeout=10000)
                    captcha_element = await self.page.query_selector('div.captcha')
                    logger.info("找到验证码容器")
                except Exception as e:
                    logger.error(f"最终未找到验证码元素: {e}")
                    return None

            # 步骤1: 点击验证码元素
            if captcha_element:
                logger.info("正在点击验证码...")
                await captcha_element.click()
                logger.info("已点击验证码")
            else:
                # 如果还是没找到，尝试直接点击坐标
                logger.warning("尝试通过坐标点击验证码...")
                await self.page.click('div.captcha', timeout=5000)
                logger.info("通过容器点击了验证码")

            # 等待验证码处理完成
            logger.info("等待验证码处理完成...")
            try:
                await self.page.wait_for_selector('.captcha[data-state="done"]', timeout=15000)
                logger.info("验证码处理完成")
            except Exception as e:
                logger.warning(f"等待验证码完成超时: {e}")

            # 验证码完成后，立即检查是否已经获取到token
            if captured_token:
                logger.info(f"验证码完成后立即获取到 token: {captured_token}")
                # 移除监听器
                self.page.remove_listener('request', handle_request)
                self.page.remove_listener('response', handle_response)
                return captured_token

            # 步骤2: 查找并点击 REQUEST 按钮
            logger.info("查找 REQUEST 按钮...")
            request_button = None

            # 尝试多种选择器来找到 REQUEST 按钮
            button_selectors = [
                'button[type="submit"]',
                'button:has-text("REQUEST")',
                'button:has-text("Request")',
                'button:has-text("request")',
                'button[style*="border-radius: 50px"]',
                'button:has(p:has-text("REQUEST"))'
            ]

            for selector in button_selectors:
                try:
                    logger.info(f"尝试按钮选择器: {selector}")
                    await self.page.wait_for_selector(selector, timeout=3000)
                    request_button = await self.page.query_selector(selector)
                    if request_button:
                        # 检查按钮文本是否包含 REQUEST
                        button_text = await request_button.text_content()
                        if button_text and 'request' in button_text.lower():
                            logger.info(f"找到 REQUEST 按钮: {selector}, 文本: {button_text}")
                            break
                        else:
                            request_button = None
                except Exception as e:
                    logger.debug(f"按钮选择器 {selector} 未找到: {e}")
                    continue

            if not request_button:
                # 如果没找到，尝试通过文本查找
                logger.info("通过文本查找 REQUEST 按钮...")
                try:
                    request_button = await self.page.query_selector('text=REQUEST')
                    if not request_button:
                        request_button = await self.page.query_selector('text=Request')
                    if not request_button:
                        request_button = await self.page.query_selector('text=request')
                except Exception as e:
                    logger.debug(f"通过文本查找按钮失败: {e}")

            if request_button:
                logger.info("找到 REQUEST 按钮，检查是否可点击...")

                # 检查按钮是否启用
                is_enabled = await request_button.is_enabled()
                logger.info(f"按钮是否启用: {is_enabled}")

                if not is_enabled:
                    logger.info("按钮未启用，等待按钮变为可点击状态...")
                    # 等待按钮启用，最多等待30秒
                    try:
                        await self.page.wait_for_function(
                            'button => !button.disabled && button.offsetParent !== null',
                            request_button,
                            timeout=30000
                        )
                        logger.info("按钮现在已启用")
                    except Exception as e:
                        logger.warning(f"等待按钮启用超时: {e}")

                        # 尝试强制启用按钮
                        logger.info("尝试强制启用按钮...")
                        await request_button.evaluate('button => { button.disabled = false; button.removeAttribute("disabled"); }')
                        await asyncio.sleep(1)

                logger.info("准备点击 REQUEST 按钮...")
                try:
                    # 使用 force 选项强制点击
                    await request_button.click(force=True)
                    logger.info("已点击 REQUEST 按钮")
                except Exception as e:
                    logger.warning(f"普通点击失败，尝试 JavaScript 点击: {e}")
                    # 如果普通点击失败，尝试 JavaScript 点击
                    await request_button.evaluate('button => button.click()')
                    logger.info("已通过 JavaScript 点击 REQUEST 按钮")

                # 等待网络请求完成
                logger.info("等待水龙头请求响应...")
                await asyncio.sleep(random.uniform(3, 8))

                # 检查是否获取到了 token
                if captured_token:
                    logger.info(f"从网络请求中获取到 token: {captured_token}")
                    # 移除监听器
                    self.page.remove_listener('request', handle_request)
                    self.page.remove_listener('response', handle_response)
                    return captured_token
                else:
                    logger.warning("点击 REQUEST 按钮后未获取到 token")
            else:
                logger.error("未找到 REQUEST 按钮")

            # 移除监听器
            self.page.remove_listener('request', handle_request)
            self.page.remove_listener('response', handle_response)

            # 如果从网络请求中获取到了 token，直接返回
            if captured_token:
                logger.info(f"从网络请求中获取到 token: {captured_token}")
                return captured_token

            # 否则尝试从页面中提取
            logger.warning("未从网络请求获取到 token，尝试从页面提取...")
            captcha_token = await self.extract_captcha_token()
            return captcha_token

        except Exception as e:
            logger.error(f"查找和点击验证码时发生错误: {e}")
            return None


            
    async def extract_captcha_token(self) -> Optional[str]:
        """从页面中提取验证码 token"""
        try:
            # 等待验证码处理完成，检查状态变化
            logger.info("等待验证码处理完成...")

            # 等待验证码状态变为 done
            try:
                await self.page.wait_for_selector('.captcha[data-state="done"]', timeout=15000)
                logger.info("验证码处理完成，状态为 done")
            except Exception as e:
                logger.warning(f"等待验证码完成状态超时: {e}")

            # 额外等待确保所有处理完成
            await asyncio.sleep(2)

            # 从页面的 JavaScript 变量中提取
            logger.info("尝试从页面变量中提取验证码 token...")
            captcha_token = await self.page.evaluate("""
                () => {
                    // 尝试从各种可能的全局变量中获取 captcha token
                    if (window.captchaToken) return window.captchaToken;
                    if (window.captcha) return window.captcha;
                    if (window.recaptchaToken) return window.recaptchaToken;
                    if (window.capToken) return window.capToken;
                    if (window.cap && window.cap.token) return window.cap.token;

                    // 尝试从验证码元素的属性中获取
                    const captchaEl = document.querySelector('.captcha');
                    if (captchaEl) {
                        // 检查各种可能的属性
                        const attrs = ['data-token', 'data-captcha', 'data-cap-token', 'data-challenge', 'data-response'];
                        for (const attr of attrs) {
                            const value = captchaEl.getAttribute(attr);
                            if (value && value.length > 10) return value;
                        }

                        // 检查dataset
                        if (captchaEl.dataset.token) return captchaEl.dataset.token;
                        if (captchaEl.dataset.captcha) return captchaEl.dataset.captcha;
                        if (captchaEl.dataset.capToken) return captchaEl.dataset.capToken;
                        if (captchaEl.dataset.challenge) return captchaEl.dataset.challenge;
                        if (captchaEl.dataset.response) return captchaEl.dataset.response;
                    }

                    // 尝试从 localStorage 获取
                    const localToken = localStorage.getItem('captchaToken') ||
                                     localStorage.getItem('captcha') ||
                                     localStorage.getItem('recaptchaToken') ||
                                     localStorage.getItem('capToken') ||
                                     localStorage.getItem('cap-token');
                    if (localToken) return localToken;

                    // 尝试从 sessionStorage 获取
                    const sessionToken = sessionStorage.getItem('captchaToken') ||
                                       sessionStorage.getItem('captcha') ||
                                       sessionStorage.getItem('recaptchaToken') ||
                                       sessionStorage.getItem('capToken') ||
                                       sessionStorage.getItem('cap-token');
                    if (sessionToken) return sessionToken;

                    // 尝试从页面元素的属性中获取
                    const captchaEl = document.querySelector('.captcha[data-state="done"]');
                    if (captchaEl) {
                        const token = captchaEl.getAttribute('data-token') ||
                                    captchaEl.getAttribute('data-captcha') ||
                                    captchaEl.getAttribute('data-cap-token') ||
                                    captchaEl.dataset.token ||
                                    captchaEl.dataset.captcha ||
                                    captchaEl.dataset.capToken;
                        if (token) return token;
                    }

                    // 尝试从隐藏的 input 元素获取
                    const hiddenInputs = document.querySelectorAll('input[type="hidden"]');
                    for (const input of hiddenInputs) {
                        if (input.name && input.name.toLowerCase().includes('captcha') && input.value) {
                            return input.value;
                        }
                    }

                    // 尝试从表单数据中获取
                    const forms = document.querySelectorAll('form');
                    for (const form of forms) {
                        const formData = new FormData(form);
                        for (const [key, value] of formData.entries()) {
                            if (key.toLowerCase().includes('captcha') && value) {
                                return value;
                            }
                        }
                    }

                    return null;
                }
            """)

            if captcha_token:
                logger.info(f"从页面变量中找到 token: {captcha_token}")
                return captcha_token

            # 如果没找到，尝试监听网络请求
            logger.info("尝试监听网络请求获取 token...")
            return await self.monitor_network_for_token()

        except Exception as e:
            logger.error(f"提取验证码 token 时发生错误: {e}")
            return None

    async def monitor_network_for_token(self) -> Optional[str]:
        """监听网络请求获取验证码 token"""
        try:
            # 设置网络请求监听
            captured_token = None

            def handle_response(response):
                nonlocal captured_token
                try:
                    url = response.url
                    if any(keyword in url.lower() for keyword in ['captcha', 'cap', 'challenge', 'verify']):
                        logger.info(f"捕获到相关请求: {url}")
                        # 这里可以进一步处理响应内容
                except Exception as e:
                    logger.debug(f"处理响应时出错: {e}")

            self.page.on('response', handle_response)

            # 等待一段时间捕获请求
            await asyncio.sleep(5)

            # 移除监听器
            self.page.remove_listener('response', handle_response)

            return captured_token

        except Exception as e:
            logger.error(f"监听网络请求时发生错误: {e}")
            return None

# 同步包装器
class UomiCaptchaSolverSync:
    def __init__(self, headless: bool = True, proxy: Optional[Dict] = None):
        self.headless = headless
        self.proxy = proxy
        
    def solve_captcha(self, address: str, max_retries: int = 3) -> Optional[str]:
        """同步版本的验证码解决方法"""
        return asyncio.run(self._solve_captcha_async(address, max_retries))
        
    async def _solve_captcha_async(self, address: str, max_retries: int = 3) -> Optional[str]:
        """异步版本的验证码解决方法"""
        async with UomiCaptchaSolver(self.headless, self.proxy) as solver:
            return await solver.solve_captcha(address, max_retries)

# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 同步使用
    solver = UomiCaptchaSolverSync(headless=True)
    token = solver.solve_captcha("0x1234567890123456789012345678901234567890")
    
    if token:
        print(f"获取到验证码 token: {token}")
    else:
        print("未能获取验证码 token")
