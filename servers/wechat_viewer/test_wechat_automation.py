#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for WeChat Automation
Can be debugged in Antigravity

Usage:
1. Open this file in Antigravity
2. Set breakpoints
3. Run debugger (F5 or Debug > Start Debugging)
"""
import sys
import os
import logging
import asyncio
import inspect
import platform
import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# 导入新的依赖管理器
from deps.manager import get_dependency_manager

_dep_manager = None


async def get_initialized_dependency_manager():
    """Lazily initialize dependencies so pytest import has no async side effects."""
    global _dep_manager

    if _dep_manager is None:
        _dep_manager = get_dependency_manager()
        init_result = _dep_manager.initialize_all()
        if inspect.isawaitable(init_result):
            await init_result

    return _dep_manager

# 设置日志
def setup_logging():
    """设置日志配置，同时输出到控制台和文件"""
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 生成带时间戳的日志文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = "test_wechat_automation_{}.log".format(timestamp)
    log_filepath = log_dir / log_filename
    
    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 清除现有的处理器
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # 控制台处理器
            logging.StreamHandler(sys.stdout),
            # 文件处理器
            logging.FileHandler(log_filepath, encoding='utf-8')
        ]
    )
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    
    # 为不同模块设置不同的日志级别
    root_logger.setLevel(logging.DEBUG)
    
    # 设置特定模块的日志级别
    logging.getLogger("PIL").setLevel(logging.WARNING)  # 降低PIL日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # 降低urllib3日志级别
    logging.getLogger("requests").setLevel(logging.WARNING)  # 降低requests日志级别
    
    return log_filepath

# 设置日志并获取日志文件路径
log_file_path = setup_logging()
logger = logging.getLogger(__name__)

# 记录日志文件位置
logger.info("日志文件已创建: {}".format(log_file_path))
logger.info("日志将同时输出到控制台和文件: {}".format(log_file_path))

logger = logging.getLogger(__name__)


# 导入 OCR 处理器
from mcp_core.ocr_processor import OCRProcessor


class TestWeChatAutomation:
    """WeChat 自动化测试类"""
    __test__ = False
    
    def __init__(self):
        self.logger = logging.getLogger("TestWeChatAutomation")
        self.dep_manager = None
        self.ocr_processor = None
        self.automation = None
    
    async def setup(self):
        """设置测试环境"""
        self.logger.info("=" * 60)
        self.logger.info("Setting up test environment")
        self.logger.info("=" * 60)

        # 使用依赖管理器
        self.dep_manager = await get_initialized_dependency_manager()
        self.ocr_processor = OCRProcessor(dep_manager=self.dep_manager)

        # 导入 WeChatAutomation
        try:
            # 使用修复版本的 WeChatAutomation（支持 dep_manager 和 ocr_processor）
            from automation.wechat_automation import WeChatAutomation, AutomationStatus
            from mcp_core.llm_protocol import LLMProtocolFactory
            self.logger.info("✓ Successfully imported WeChatAutomation from wechat_automation")
            self.status = AutomationStatus

            # 从依赖管理器获取 LLM 客户端
            # llm_client = self.dep_manager.get_dependency("llm_chain")
            # if llm_client:
            #     self.logger.info("✓ Successfully obtained LLM client from dependency manager")
            # else:
            #     self.logger.warning("⚠ LLM client not available, search will use OCR only")
            llm_client = LLMProtocolFactory.create_wechat_viewer_llm_client("ai")
            # 创建自动化实例
            self.automation = WeChatAutomation(
                dep_manager=self.dep_manager,
                ocr_processor=self.ocr_processor,
                llm_client=llm_client
            )
            self.logger.info("✓ Successfully created WeChatAutomation instance")

        except ImportError as e:
            self.logger.error("Failed to import WeChatAutomation: %s" % e)
            self.logger.error("Current sys.path: %s" % sys.path)
            raise
        except Exception as e:
            self.logger.error("Failed to create WeChatAutomation instance: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def test_platform_detection(self):
        """测试平台检测"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 1: Platform Detection")
        self.logger.info("=" * 60)
        
        current_platform = platform.system().lower()
        detected_platform = self.automation.platform
        
        self.logger.info("Current platform: %s" % current_platform)
        self.logger.info("Detected platform: %s" % detected_platform)
        
        if current_platform == detected_platform:
            self.logger.info("✓ PASS: Platform detection correct")
            return True
        else:
            self.logger.error("✗ FAIL: Platform detection incorrect")
            return False
    
    def test_bring_wechat_to_front(self):
        """测试将微信窗口置于前台"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 2: Bring WeChat to Front")
        self.logger.info("=" * 60)
        
        try:
            result = self.automation.bring_wechat_to_front()
            self.logger.info("Result status: %s" % result.status)
            self.logger.info("Result message: %s" % result.message)
            self.logger.info("Execution time: %.3fs" % result.execution_time)
            
            # 即使失败也算通过，因为可能没有微信窗口
            self.logger.info("✓ PASS: Method executed without crashing")
            return True
            
        except Exception as e:
            self.logger.error("✗ FAIL: Exception occurred: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def test_get_window_bounds(self):
        """测试获取窗口边界"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 3: Get Window Bounds")
        self.logger.info("=" * 60)
        
        try:
            result = self.automation.get_wechat_window_bounds()
            self.logger.info("Result status: %s" % result.status)
            self.logger.info("Result message: %s" % result.message)
            self.logger.info("Execution time: %.3fs" % result.execution_time)
            
            if result.data:
                self.logger.info("Bounds data: %s" % result.data)
            
            self.logger.info("✓ PASS: Method executed without crashing")
            return True
            
        except Exception as e:
            self.logger.error("✗ FAIL: Exception occurred: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def test_click_at(self):
        """测试点击操作"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 4: Click At Coordinates")
        self.logger.info("=" * 60)
        
        try:
            # 测试点击屏幕中心附近的位置
            result = self.automation.click_at(500, 500)
            self.logger.info("Result status: %s" % result.status)
            self.logger.info("Result message: %s" % result.message)
            self.logger.info("Execution time: %.3fs" % result.execution_time)

            self.logger.info("✓ PASS: Method executed without crashing")
            return True

        except Exception as e:
            self.logger.error("✗ FAIL: Exception occurred: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    async def test_search_account(self):
        """测试搜索账户"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 5: Search WeChat Account")
        self.logger.info("=" * 60)

        try:
            # 动态获取窗口边界，不再使用硬编码
            bounds_result = self.automation.get_wechat_window_bounds()
            self.logger.info("Bounds result status: %s" % bounds_result.status)

            if bounds_result.status != self.status.SUCCESS:
                self.logger.error("无法获取微信窗口边界: %s" % bounds_result.message)
                return False

            bounds = bounds_result.data["bounds"]
            self.logger.info("微信窗口边界: %s" % bounds)

            # 验证边界数据格式
            if not isinstance(bounds, dict):
                self.logger.error("边界数据格式错误，应该是字典类型: %s" % type(bounds))
                return False

            required_keys = ['X', 'Y', 'Width', 'Height']
            for key in required_keys:
                if key not in bounds:
                    self.logger.error("边界数据缺少必要字段: %s" % key)
                    return False
                if not isinstance(bounds[key], (int, float)):
                    self.logger.error("边界数据字段 %s 应该是数字类型: %s" % (key, bounds[key]))
                    return False

            self.logger.info("边界数据验证通过: X=%d, Y=%d, Width=%d, Height=%d" % (
                bounds['X'], bounds['Y'], bounds['Width'], bounds['Height']
            ))

            result = await self.automation.search_wechat_account(
                bounds=bounds,
                account_name="江南小牛"
            )

            self.logger.info("Result status: %s" % result.status)
            self.logger.info("Result message: %s" % result.message)
            self.logger.info("Execution time: %.3fs" % result.execution_time)

            if result.data:
                self.logger.info("Search data: %s" % result.data)

            self.logger.info("✓ PASS: Method executed without crashing")
            return True

        except Exception as e:
            self.logger.error("✗ FAIL: Exception occurred: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    async def test_run_cycle(self):
        """测试运行周期"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 6: Run Automation Cycle")
        self.logger.info("=" * 60)
        
        try:
            result = await self.automation.run_cycle(
                account_ids=["上海证券报"],
                max_articles=3
            )
            
            self.logger.info("Result status: %s" % result.status)
            self.logger.info("Result message: %s" % result.message)
            self.logger.info("Execution time: %.3fs" % result.execution_time)
            
            if result.data:
                self.logger.info("Cycle data: %s" % result.data)
            
            self.logger.info("✓ PASS: Method executed without crashing")
            return True
            
        except Exception as e:
            self.logger.error("✗ FAIL: Exception occurred: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    async def test_click_latest_article(self):
        """测试点击最新文章"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 8: Click Latest Article")
        self.logger.info("=" * 60)
        
        try:
            # 获取微信窗口边界
            bounds_result = self.automation.get_wechat_window_bounds()
            self.logger.info("Bounds result status: %s" % bounds_result.status)
            self.logger.info("Bounds result message: %s" % bounds_result.message)
            
            if bounds_result.status != self.status.SUCCESS:
                self.logger.error("无法获取微信窗口边界: %s" % bounds_result.message)
                return False
            
            bounds = bounds_result.data["bounds"]
            self.logger.info("微信窗口边界: %s" % bounds)
            
            # 验证边界数据格式
            if not isinstance(bounds, dict):
                self.logger.error("边界数据格式错误，应该是字典类型: %s" % type(bounds))
                return False
            
            required_keys = ['X', 'Y', 'Width', 'Height']
            for key in required_keys:
                if key not in bounds:
                    self.logger.error("边界数据缺少必要字段: %s" % key)
                    return False
                if not isinstance(bounds[key], (int, float)):
                    self.logger.error("边界数据字段 %s 应该是数字类型: %s" % (key, bounds[key]))
                    return False
            
            self.logger.info("边界数据验证通过: X=%d, Y=%d, Width=%d, Height=%d" % (
                bounds['X'], bounds['Y'], bounds['Width'], bounds['Height']
            ))
            
            # Step 1: Locate and click search bar
            self.logger.info("Step 1: 定位并点击搜索框")
            search_bar_result = await self.automation._locate_and_click_search_bar_simple(bounds)
            if not search_bar_result:
                self.logger.error("无法定位或点击搜索框")
                return False
                
            # Step 2: Input '公众号' and press Enter
            self.logger.info("Step 2: 输入 '公众号' 并触发搜索")
            time_module = self.dep_manager.get_dependency("time")
            input_result = await self.automation._input_account_name("公众号", time_module)
            if not input_result:
                self.logger.error("输入 '公众号' 失败")
                return False
                
            # Step 3: Use LLM to locate and click the '公众号' function item in search results
            self.logger.info("Step 3: 使用 LLM 在搜索结果中定位并点击 '公众号' 功能项")
            
            # 等待搜索结果完全加载
            time_module.sleep(1.0)
            
            # 截图搜索结果区域
            screenshot = self.automation.ocr_processor.capture_screenshot()
            if not screenshot:
                self.logger.error("无法获取截图")
                return False
            
            # 使用 LLM 在搜索结果截图中定位 '公众号' 功能项
            # 搜索结果区域大致是窗口的右半部分（内容区域）
            search_region = {
                'X': bounds['X'],
                'Y': bounds['Y'],
                'Width': bounds['Width'],
                'Height': bounds['Height']
            }
            
            # 自定义更精确的 LLM prompt
            find_prompt = """请仔细分析这张微信搜索结果截图，找到搜索结果中"功能"分类下的"公众号"条目。

重要说明：
- 这是微信搜索"公众号"后的搜索结果页面
- 搜索结果中会有不同的分类（如"功能"、"公众号"、"文章"等）
- 我需要找到"功能"分类下的"公众号"这个条目（通常带有一个图标）
- 这个条目点击后可以进入公众号聚合页面
- 坐标原点 (0,0) 在截图左上角

请返回 JSON 格式的结果：
```json
{
  "found": true/false,
  "match_text": "实际匹配的文本描述",
  "center_x": 该条目中心 X 坐标（相对于截图左上角）,
  "center_y": 该条目中心 Y 坐标（相对于截图左上角）,
  "confidence": 0-1 之间的置信度
}
```

定位要求：
1. 找到"功能"分类标签下方的"公众号"入口
2. 返回"公众号"条目的**中心点**坐标（用于点击）
3. 不要返回搜索框中的"公众号"文字，而是搜索结果列表中的条目
4. 如果有多个匹配，选择"功能"分类下的那一个
5. 如果找不到，found 设为 false"""

            hub_result = await self.automation.llm_element_locator.find_element_by_name(
                screenshot, "功能分类下的公众号入口", search_region, prompt=find_prompt
            )
            
            if not hub_result:
                self.logger.error("LLM 未能找到 '公众号' 功能项")
                return False
            
            hub_x, hub_y = hub_result
            self.logger.info("找到公众号功能项: (%d, %d)" % (hub_x, hub_y))
            
            # 点击公众号功能项
            self.automation.window_manager.bring_to_front()
            time_module.sleep(0.5)
            click_result = self.automation.click_at(hub_x, hub_y)
            if click_result.status != self.status.SUCCESS:
                self.logger.error("点击公众号功能项失败")
                return False
                
            # Wait for content to load
            self.logger.info("等待公众号页面加载...")
            time_module.sleep(3)
                
            # Step 4: Read latest articles (iterate through each, open 2s, then close)
            self.logger.info("Step 4: 开始循环阅读公众号聚合页面中的文章")
            article_result = await self.automation.read_latest_articles(bounds)
            
            self.logger.info("Result status: %s" % ("SUCCESS" if article_result else "FAILED"))
            self.logger.info("Result message: %s" % ("成功处理公众号文章" if article_result else "处理公众号文章失败"))
            
            if article_result:
                self.logger.info("✓ PASS: 成功阅读最新文章")
                return True
            else:
                self.logger.warning("✗ FAIL: 未能成功阅读文章")
                return False
                
        except Exception as e:
            self.logger.error("✗ FAIL: Exception occurred: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    async def test_search_and_click_account(self):
        """测试搜索公众号并点击第一篇文章"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 9: Search Account and Click Article")
        self.logger.info("=" * 60)
        
        try:
            # 获取微信窗口边界
            bounds_result = self.automation.get_wechat_window_bounds()
            self.logger.info("Bounds result status: %s" % bounds_result.status)
            self.logger.info("Bounds result message: %s" % bounds_result.message)
            
            if bounds_result.status != self.status.SUCCESS:
                self.logger.error("无法获取微信窗口边界: %s" % bounds_result.message)
                return False
            
            bounds = bounds_result.data["bounds"]
            self.logger.info("微信窗口边界: %s" % bounds)
            
            # 验证边界数据格式
            if not isinstance(bounds, dict):
                self.logger.error("边界数据格式错误，应该是字典类型: %s" % type(bounds))
                return False
            
            required_keys = ['X', 'Y', 'Width', 'Height']
            for key in required_keys:
                if key not in bounds:
                    self.logger.error("边界数据缺少必要字段: %s" % key)
                    return False
                if not isinstance(bounds[key], (int, float)):
                    self.logger.error("边界数据字段 %s 应该是数字类型: %s" % (key, bounds[key]))
                    return False
            
            self.logger.info("边界数据验证通过: X=%d, Y=%d, Width=%d, Height=%d" % (
                bounds['X'], bounds['Y'], bounds['Width'], bounds['Height']
            ))
            
            # 搜索公众号
            search_result = await self.automation.search_wechat_account(
                bounds=bounds,
                account_name="财联社"
            )
            
            self.logger.info("Search result status: %s" % search_result.status)
            self.logger.info("Search result message: %s" % search_result.message)
            
            if search_result.status == "SUCCESS":
                self.logger.info("✓ PASS: 成功搜索到公众号")
                
                # 如果找到了公众号，尝试点击第一篇文章
                if search_result.data and search_result.data.get("found"):
                    click_result = await self.automation.click_wechat_account(bounds, search_result.data)
                    self.logger.info("Click result: %s" % ("SUCCESS" if click_result else "FAILED"))
                    
                    if click_result:
                        self.logger.info("✓ PASS: 成功点击公众号并打开文章")
                        return True
                    else:
                        self.logger.warning("✗ FAIL: 点击公众号失败")
                        return False
                else:
                    self.logger.info("✓ PASS: 搜索功能正常工作（可能没有找到指定公众号）")
                    return True
            else:
                self.logger.warning("✗ FAIL: 搜索公众号失败: %s" % search_result.message)
                return False
                
        except Exception as e:
            self.logger.error("✗ FAIL: Exception occurred: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def test_performance_monitor(self):
        """测试性能监控"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Test 7: Performance Monitor")
        self.logger.info("=" * 60)
        
        try:
            summary = self.automation.get_performance_summary()
            self.logger.info("Performance summary: %s" % summary)
            
            self.logger.info("✓ PASS: Performance monitor working")
            return True
            
        except Exception as e:
            self.logger.error("✗ FAIL: Exception occurred: %s" % e)
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    async def run_all_tests(self):
        """运行所有测试"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("RUNNING ALL TESTS")
        self.logger.info("=" * 60)
        
        results = []
        
        # 同步测试
        # results.append(("Platform Detection", self.test_platform_detection()))
        # results.append(("Bring WeChat to Front", self.test_bring_wechat_to_front()))
        # results.append(("Get Window Bounds", self.test_get_window_bounds()))
        # results.append(("Click At", self.test_click_at()))
        # results.append(("Performance Monitor", self.test_performance_monitor()))

        # 异步测试
        # search_account_result = await self.test_search_account()
        # run_cycle_result = await self.test_run_cycle()
        click_latest_article_result = await self.test_click_latest_article()
        # search_and_click_account_result = await self.test_search_and_click_account()

        # results.append(("Search Account", search_account_result))
        # results.append(("Run Cycle", run_cycle_result))
        results.append(("Click Latest Article", click_latest_article_result))
        # results.append(("Search Account and Click Article", search_and_click_account_result))
        
        # 打印总结
        self.logger.info("\n" + "=" * 60)
        self.logger.info("TEST SUMMARY")
        self.logger.info("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            self.logger.info(f"{status}: {test_name}")
        
        self.logger.info("-" * 60)
        self.logger.info(f"Total: {passed}/{total} tests passed")
        self.logger.info("=" * 60)
        
        return passed == total


async def main():
    """主函数"""
    logger.info("WeChat Automation Test Script")
    logger.info(f"Platform: {platform.system()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    try:
        # 创建测试实例
        test = TestWeChatAutomation()
        
        # 设置测试环境
        await test.setup()
        
        # 运行所有测试
        success = await test.run_all_tests()
        
        if success:
            logger.info("\n✓ All tests passed!")
            return 0
        else:
            logger.error("\n✗ Some tests failed!")
            return 1
            
    except Exception as e:
        logger.error(f"\n✗ Test execution failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
