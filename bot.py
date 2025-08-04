#!/usr/bin/env python3
"""
UOMI 水龙头自动领取机器人 - 简化版
支持多账户、代理轮换、24小时定时领取
"""

import requests
import time
import random
from datetime import datetime, timedelta
import logging
from colorama import *
from typing import Dict, Optional
import sys

# 版权
def show_copyright():
    """展示版权信息"""
    copyright_info = f"""{Fore.CYAN}
    *****************************************************
    *           X:https://x.com/ariel_sands_dan         *
    *           Tg:https://t.me/sands0x1                *
    *           Copyright (c) 2025                      *
    *           All Rights Reserved                     *
    *****************************************************
    """
    {Style.RESET_ALL}
    print(copyright_info)
    print('=' * 50)
    print(f"{Fore.GREEN}申请key: https://661100.xyz/ {Style.RESET_ALL}")
    print(f"{Fore.RED}联系Dandan: \n QQ:712987787 QQ群:1036105927 \n 电报:sands0x1 电报群:https://t.me/+fjDjBiKrzOw2NmJl \n 微信: dandan0x1{Style.RESET_ALL}")
    print('=' * 50)

# 导入验证码解决器
try:
    from captcha_solver import UomiCaptchaSolverSync
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright 不可用，将跳过验证码处理")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('faucet_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class UomiFaucetBot:
    def __init__(self):
        self.base_url = "https://backend.uomi.ai"
        self.headers = {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,ja;q=0.6,fr;q=0.5,ru;q=0.4,und;q=0.3',
            'content-type': 'application/json',
            'dnt': '1',
            'origin': 'https://app.uomi.ai',
            'priority': 'u=1, i',
            'referer': 'https://app.uomi.ai/',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        }
        
        self.addresses = []
        self.proxies = []
        self.last_claim_times = {}
        
        self.load_addresses()
        self.load_proxies()
        
    def load_addresses(self) -> None:
        """从 address.txt 加载钱包地址"""
        try:
            with open('address.txt', 'r', encoding='utf-8') as f:
                self.addresses = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            logger.info(f"加载了 {len(self.addresses)} 个钱包地址")
        except FileNotFoundError:
            logger.error("address.txt 文件不存在")
            sys.exit(1)
        except Exception as e:
            logger.error(f"加载地址文件失败: {e}")
            sys.exit(1)
    
    def load_proxies(self) -> None:
        """从 proxy.txt 加载代理列表"""
        try:
            with open('proxy.txt', 'r', encoding='utf-8') as f:
                proxy_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                
            self.proxies = []
            for line in proxy_lines:
                # 移除可能存在的 http:// 前缀，然后重新添加
                if line.startswith('http://'):
                    line = line[7:]
                elif line.startswith('https://'):
                    line = line[8:]
                
                # 支持格式: ip:port 或 ip:port:username:password
                parts = line.split(':')
                if len(parts) >= 2:
                    if len(parts) == 2:
                        # 无认证代理
                        proxy_url = f'http://{parts[0]}:{parts[1]}'
                        proxy = {
                            'http': proxy_url,
                            'https': proxy_url
                        }
                    elif len(parts) == 4:
                        # 有认证代理
                        proxy_url = f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                        proxy = {
                            'http': proxy_url,
                            'https': proxy_url
                        }
                    else:
                        logger.warning(f"代理格式不正确: {line}")
                        continue
                    self.proxies.append(proxy)
                    
            logger.info(f"加载了 {len(self.proxies)} 个代理")
        except FileNotFoundError:
            logger.error("proxy.txt 文件不存在")
            sys.exit(1)
        except Exception as e:
            logger.error(f"加载代理文件失败: {e}")
            sys.exit(1)
    
    def get_proxy_for_address(self, address_index: int) -> Optional[Dict]:
        """为指定地址索引获取对应的代理"""
        if not self.proxies:
            return None
        return self.proxies[address_index % len(self.proxies)]
    
    def can_claim(self, address: str) -> bool:
        """检查地址是否可以领取（距离上次领取超过24小时）"""
        if address not in self.last_claim_times:
            return True
        
        last_claim = self.last_claim_times[address]
        now = datetime.now()
        return (now - last_claim) >= timedelta(hours=24)
    
    def get_captcha_token(self, address: str, proxy: Optional[Dict] = None) -> Optional[str]:
        """使用 Playwright 获取验证码 token"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright 不可用，无法获取验证码")
            return None

        try:
            # 转换代理格式
            playwright_proxy = None
            if proxy:
                playwright_proxy = {
                    'http': proxy.get('http', ''),
                    'https': proxy.get('https', '')
                }

            solver = UomiCaptchaSolverSync(headless=True, proxy=playwright_proxy)
            captcha_token = solver.solve_captcha(address)

            if captcha_token:
                logger.info(f"成功获取验证码 token: {captcha_token}")
                return captcha_token
            else:
                logger.error("未能获取验证码 token")
                return None

        except Exception as e:
            logger.error(f"获取验证码 token 时发生错误: {e}")
            return None

    def request_faucet(self, address: str, proxy: Optional[Dict] = None) -> Optional[str]:
        """请求水龙头，获取 Twitter 验证码"""
        try:
            # 获取验证码 token
            captcha_token = self.get_captcha_token(address, proxy)
            if not captcha_token:
                logger.error(f"地址 {address} 无法获取验证码 token")
                return None

            data = {
                "address": address,
                "captcha": captcha_token
            }

            response = requests.post(
                f"{self.base_url}/faucet/request",
                headers=self.headers,
                json=data,
                proxies=proxy,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                twitter_code = result.get('twitterCode')
                if twitter_code:
                    logger.info(f"地址 {address} 获取到 Twitter 验证码: {twitter_code}")
                    return twitter_code
                else:
                    logger.error(f"地址 {address} 响应中没有 twitterCode: {result}")
            else:
                logger.error(f"地址 {address} 请求失败，状态码: {response.status_code}, 响应: {response.text}")

        except Exception as e:
            logger.error(f"地址 {address} 请求水龙头失败: {e}")

        return None

    def claim_faucet(self, address: str, twitter_code: str, proxy: Optional[Dict] = None) -> bool:
        """使用 Twitter 验证码领取水龙头"""
        try:
            data = {
                "address": address,
                "twitterCode": twitter_code
            }

            response = requests.post(
                f"{self.base_url}/faucet/claim",
                headers=self.headers,
                json=data,
                proxies=proxy,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"地址 {address} 成功领取水龙头: {result}")
                self.last_claim_times[address] = datetime.now()
                return True
            else:
                logger.error(f"地址 {address} 领取失败，状态码: {response.status_code}, 响应: {response.text}")

        except Exception as e:
            logger.error(f"地址 {address} 领取水龙头失败: {e}")

        return False
    
    def process_address(self, address: str, address_index: int) -> bool:
        """处理单个地址的水龙头领取流程"""
        if not self.can_claim(address):
            next_claim_time = self.last_claim_times[address] + timedelta(hours=24)
            logger.info(f"地址 {address} 还需等待到 {next_claim_time} 才能再次领取")
            return False

        proxy = self.get_proxy_for_address(address_index)
        proxy_info = f"代理 {proxy['http'] if proxy else '无代理'}"
        logger.info(f"开始处理地址 {address} ({proxy_info})")

        # 步骤1: 请求获取 Twitter 验证码
        twitter_code = self.request_faucet(address, proxy)
        if not twitter_code:
            logger.error(f"地址 {address} 获取 Twitter 验证码失败")
            return False

        # 等待一段时间
        time.sleep(random.uniform(2, 5))

        # 步骤2: 使用验证码领取水龙头
        success = self.claim_faucet(address, twitter_code, proxy)
        if success:
            logger.info(f"地址 {address} 成功完成水龙头领取")
        else:
            logger.error(f"地址 {address} 水龙头领取失败")

        return success
    
    def run_once(self) -> None:
        """执行一轮所有地址的处理"""
        logger.info("开始新一轮水龙头领取")
        
        for i, address in enumerate(self.addresses):
            try:
                self.process_address(address, i)
                # 在处理地址之间添加随机延迟
                time.sleep(random.uniform(5, 15))
            except Exception as e:
                logger.error(f"处理地址 {address} 时发生错误: {e}")
        
        logger.info("本轮水龙头领取完成")
    
    def run_forever(self) -> None:
        """持续运行，每小时检查一次"""
        logger.info("UOMI 水龙头机器人启动")
        
        while True:
            try:
                self.run_once()
                
                # 等待1小时后再次检查
                logger.info("等待1小时后进行下一轮检查...")
                time.sleep(3600)  # 1小时
                
            except KeyboardInterrupt:
                logger.info("收到停止信号，正在退出...")
                break
            except Exception as e:
                logger.error(f"运行过程中发生错误: {e}")
                logger.info("等待5分钟后重试...")
                time.sleep(300)  # 5分钟

def main():
    """主函数"""
    show_copyright()
    time.sleep(10)
    bot = UomiFaucetBot()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # 只运行一次
        bot.run_once()
    else:
        # 持续运行
        bot.run_forever()

if __name__ == "__main__":
    main()
